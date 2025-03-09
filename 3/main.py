import asyncio
import datetime
import sys
import typing
from dataclasses import dataclass

import aiohttp

from core.config.config import GithubSettings, get_settings
from core.config.logger import LoggerAdapter, get_logger
from repo.repo import ClickHouseRepository

GITHUB_API_BASE_URL: typing.Final[str] = "https://api.github.com"


@dataclass
class RepositoryAuthorCommitsNum:
    author: str
    commits_num: int


@dataclass
class Repository:
    name: str
    owner: str
    position: int
    stars: int
    watchers: int
    forks: int
    language: str
    authors_commits_num_today: list[RepositoryAuthorCommitsNum]


class RateLimiter:

    def __init__(self, requests_per_second: int):
        self.requests_per_second = requests_per_second
        self.interval = 1.0 / requests_per_second if requests_per_second > 0 else 0
        self.last_request_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self.last_request_time

            if time_since_last < self.interval:
                await asyncio.sleep(self.interval - time_since_last)

            self.last_request_time = asyncio.get_event_loop().time()


class GithubReposScrapper:
    def __init__(self, access_token: str, settings: typing.Optional[GithubSettings] = None):
        self.app_settings = get_settings()

        self.log = LoggerAdapter(get_logger(), {"component": "GithubScraper"})

        if settings is None:
            settings = GithubSettings(access_token=access_token)

        self.settings = settings

        self._session = aiohttp.ClientSession(
            headers={
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"Bearer {access_token}",
            }
        )

        self._rate_limiter = RateLimiter(self.settings.requests_per_second)
        self._semaphore = asyncio.Semaphore(self.settings.max_concurrent_requests)

        self.log.info(f"Инициализирован GithubReposScrapper с настройками: "
                      f"MCR={self.settings.max_concurrent_requests}, "
                      f"RPS={self.settings.requests_per_second}, "
                      f"limit={self.settings.top_repos_limit}, "
                      f"days={self.settings.commits_since_days}")

    async def _make_request(self, endpoint: str, method: str = "GET",
                            params: dict[str, typing.Any] | None = None) -> typing.Any:
        await self._rate_limiter.acquire()

        async with self._semaphore:
            try:
                url = f"{GITHUB_API_BASE_URL}/{endpoint}"
                self.log.debug(f"Выполнение запроса: {method} {url} с параметрами: {params}")

                async with self._session.request(method, url, params=params) as response:
                    if response.status >= 400:
                        error_text = await response.text()
                        self.log.error(f"Ошибка API GitHub: {response.status} - {error_text}")
                        response.raise_for_status()

                    return await response.json()
            except aiohttp.ClientResponseError as e:
                if e.status == 403:
                    reset_time = int(e.headers.get("X-RateLimit-Reset", 0))
                    current_time = datetime.datetime.now().timestamp()
                    wait_time = max(0, reset_time - current_time) + 1

                    if wait_time > 0 and wait_time < 3600:
                        self.log.warning(f"Превышен лимит запросов к GitHub API. Ожидание {wait_time} секунд.")
                        await asyncio.sleep(wait_time)
                        return await self._make_request(endpoint, method, params)

                self.log.error(f"Ошибка запроса: {e}", exc_info=True)
                raise
            except aiohttp.ClientError as e:
                self.log.error(f"Ошибка клиента: {e}", exc_info=True)
                raise
            except asyncio.CancelledError:
                self.log.warning("Запрос отменен")
                raise
            except Exception as e:
                self.log.error(f"Неожиданная ошибка при выполнении запроса: {e}", exc_info=True)
                raise

    async def _get_top_repositories(self, limit: int = 100) -> list[dict[str, typing.Any]]:
        """GitHub REST API: https://docs.github.com/en/rest/search/search?apiVersion=2022-11-28#search-repositories"""
        try:
            data = await self._make_request(
                endpoint="search/repositories",
                params={"q": "stars:>1", "sort": "stars", "order": "desc", "per_page": limit},
            )
            return data.get("items", [])
        except Exception as e:
            self.log.error(f"Не удалось получить список топовых репозиториев: {e}")
            return []

    async def _get_repository_commits(self, owner: str, repo: str) -> list[dict[str, typing.Any]]:
        """GitHub REST API: https://docs.github.com/en/rest/commits/commits?apiVersion=2022-11-28#list-commits"""
        since_date = (datetime.datetime.now() - datetime.timedelta(days=self.settings.commits_since_days)).isoformat()

        try:
            return await self._make_request(
                endpoint=f"repos/{owner}/{repo}/commits",
                params={"since": since_date, "per_page": 100}
            )
        except Exception as e:
            self.log.warning(f"Не удалось получить коммиты для репозитория {owner}/{repo}: {e}")
            return []

    async def _process_repository(self, repo_data: dict[str, typing.Any], position: int) -> Repository:
        owner = repo_data.get("owner", {}).get("login", "")
        name = repo_data.get("name", "")

        log_context = LoggerAdapter(self.log.logger, {**self.log.extra, "repo": f"{owner}/{name}"})
        log_context.debug(f"Обработка репозитория #{position}")

        commits = await self._get_repository_commits(owner, name)

        author_commits: typing.Dict[str, int] = {}
        for commit in commits:
            author = commit.get("author", {})
            if not author:
                commit_data = commit.get("commit", {})
                author_name = commit_data.get("author", {}).get("name", "Unknown")
            else:
                author_name = author.get("login", "Unknown")

            author_commits[author_name] = author_commits.get(author_name, 0) + 1

        authors_commits_list = [
            RepositoryAuthorCommitsNum(author=author, commits_num=count)
            for author, count in author_commits.items()
        ]

        log_context.debug(f"Найдено {len(authors_commits_list)} авторов с коммитами")

        return Repository(
            name=name,
            owner=owner,
            position=position,
            stars=repo_data.get("stargazers_count", 0),
            watchers=repo_data.get("watchers_count", 0),
            forks=repo_data.get("forks_count", 0),
            language=repo_data.get("language", "") or "Unknown",
            authors_commits_num_today=authors_commits_list
        )

    async def get_repositories(self) -> list[Repository]:
        try:
            top_repos = await self._get_top_repositories(limit=self.settings.top_repos_limit)

            if not top_repos:
                self.log.warning("Не найдено репозиториев")
                return []

            self.log.info(f"Получено {len(top_repos)} топовых репозиториев. Обработка...")

            tasks = [
                self._process_repository(repo, position)
                for position, repo in enumerate(top_repos, 1)
            ]

            repositories = await asyncio.gather(*tasks, return_exceptions=True)

            valid_repositories = []
            for i, result in enumerate(repositories):
                if isinstance(result, Exception):
                    self.log.error(f"Ошибка при обработке репозитория {i + 1}: {result}", exc_info=True)
                else:
                    valid_repositories.append(result)

            self.log.info(f"Успешно обработано {len(valid_repositories)} из {len(top_repos)} репозиториев")
            return valid_repositories

        except Exception as e:
            self.log.error(f"Произошла ошибка при получении репозиториев: {e}", exc_info=True)
            return []

    async def close(self):
        try:
            await self._session.close()
            self.log.info("Сессия HTTP закрыта")
        except Exception as e:
            self.log.error(f"Ошибка при закрытии сессии: {e}", exc_info=True)


async def process_repositories(
        repositories: typing.List[Repository],
        ch_repo: ClickHouseRepository,
        log: LoggerAdapter
) -> None:
    log.info(f"Обработка и сохранение {len(repositories)} репозиториев")

    total_saved = 0
    try:
        for repo in repositories:
            try:
                await ch_repo.save_repository(repo)
                total_saved += 1

                # Логируем только каждый десятый репозиторий, чтобы не перегружать логи
                if total_saved % 10 == 0 or total_saved == 1:
                    log.info(f"Сохранено {total_saved} из {len(repositories)} репозиториев")
            except Exception as e:
                log.error(f"Ошибка при сохранении репозитория {repo.owner}/{repo.name}: {e}", exc_info=True)

        await ch_repo.flush_all()
        log.info(f"Всего успешно сохранено {total_saved} из {len(repositories)} репозиториев")

    except Exception as e:
        log.error(f"Произошла ошибка при обработке репозиториев: {e}", exc_info=True)


async def main() -> None:
    settings = get_settings()

    root_logger = get_logger()
    log = LoggerAdapter(root_logger, {"component": "main"})

    log.info(f"Запуск приложения {settings.project_name} в режиме {'отладки' if settings.debug else 'продакшн'}")

    try:
        github_token = settings.github.access_token
        if not github_token:
            log.error("Токен доступа GitHub не найден. Добавьте GITHUB__ACCESS_TOKEN в файл .env")
            return

        async with aiohttp.AsyncExitStack() as stack:
            scrapper = GithubReposScrapper(
                access_token=github_token,
                settings=settings.github
            )
            stack.push_async_callback(scrapper.close)

            try:
                ch_repo = await ClickHouseRepository.create(settings.clickhouse)
                stack.push_async_callback(ch_repo.close)
            except Exception as e:
                log.error(f"Не удалось инициализировать соединение с ClickHouse: {e}")
                return

            log.info("Получение списка репозиториев из GitHub...")
            repositories = await scrapper.get_repositories()

            if not repositories:
                log.warning("Не удалось получить репозитории")
                return

            log.info(f"Успешно получено {len(repositories)} репозиториев")

            await process_repositories(repositories, ch_repo, log)

    except Exception as e:
        log.exception(f"Произошла ошибка: {e}")
        sys.exit(1)

    log.info("Завершение работы приложения")


if __name__ == "__main__":
    asyncio.run(main())