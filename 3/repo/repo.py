import asyncio
import datetime

import aiochclient
import aiohttp

from core.config.config import get_settings, ClickHouseSettings
from core.config.logger import LoggerAdapter, get_logger


class ClickHouseRepository:

    def __init__(self, client: aiochclient.ChClient, settings: ClickHouseSettings, logger: LoggerAdapter):
        self.client = client
        self.settings = settings
        self.log = logger
        self._batch_queue: dict[str, list[dict]] = {
            "repositories": [],
            "repositories_authors_commits": [],
            "repositories_positions": []
        }
        self._lock = asyncio.Lock()

    async def save_repository(self, repository: 'Repository') -> None:
        now = datetime.datetime.now()
        today = now.date()

        repo_data = {
            "name": repository.name,
            "owner": repository.owner,
            "stars": repository.stars,
            "watchers": repository.watchers,
            "forks": repository.forks,
            "language": repository.language,
            "updated": now
        }

        position_data = {
            "date": today,
            "repo": f"{repository.owner}/{repository.name}",
            "position": repository.position
        }

        author_commits_data = []
        for author_commit in repository.authors_commits_num_today:
            author_commits_data.append({
                "date": today,
                "repo": f"{repository.owner}/{repository.name}",
                "author": author_commit.author,
                "commits_num": author_commit.commits_num
            })

        async with self._lock:
            self._batch_queue["repositories"].append(repo_data)
            self._batch_queue["repositories_positions"].append(position_data)
            self._batch_queue["repositories_authors_commits"].extend(author_commits_data)

            if any(len(batch) >= self.settings.batch_size for batch in self._batch_queue.values()):
                await self._flush_batch()

    async def _flush_batch(self) -> None:
        async with self._lock:
            for table_name, batch in self._batch_queue.items():
                if not batch:
                    continue

                try:
                    current_batch = batch.copy()
                    self._batch_queue[table_name] = []

                    self.log.debug(f"Запись пакета из {len(current_batch)} записей в таблицу {table_name}")
                    await self.client.execute(f"INSERT INTO {table_name} JSON", current_batch)
                    self.log.debug(f"Успешно записано {len(current_batch)} записей в таблицу {table_name}")
                except Exception as e:
                    self.log.error(f"Ошибка при записи в таблицу {table_name}: {e}", exc_info=True)
                    self._batch_queue[table_name].extend(current_batch)

                    if len(self._batch_queue[table_name]) > self.settings.batch_size * 3:
                        dropped_count = len(self._batch_queue[table_name]) - self.settings.batch_size
                        self._batch_queue[table_name] = self._batch_queue[table_name][-self.settings.batch_size:]
                        self.log.error(
                            f"Очередь для таблицы {table_name} переполнена. Отброшено {dropped_count} записей")

    async def flush_all(self) -> None:
        await self._flush_batch()

    @classmethod
    async def create(cls, settings: ClickHouseSettings = None) -> 'ClickHouseRepository':
        app_settings = get_settings()
        log = LoggerAdapter(get_logger(), {"component": "ClickHouseRepository"})

        if settings is None:
            settings = getattr(app_settings, 'clickhouse', ClickHouseSettings())

        log.info(f"Инициализация подключения к ClickHouse: "
                 f"host={settings.host}:{settings.port}, "
                 f"db={settings.database}, "
                 f"batch_size={settings.batch_size}")

        try:
            session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=settings.timeout))
            client = aiochclient.ChClient(
                session,
                url=f"http://{settings.host}:{settings.port}",
                user=settings.user,
                password=settings.password,
                database=settings.database
            )

            await client.execute("SELECT 1")
            log.info("Подключение к ClickHouse успешно установлено")

            return cls(client, settings, log)
        except Exception as e:
            log.error(f"Ошибка при инициализации подключения к ClickHouse: {e}", exc_info=True)
            raise

    async def close(self) -> None:
        try:
            await self.flush_all()

            if hasattr(self.client, 'session') and not self.client.session.closed:
                await self.client.session.close()

            self.log.info("Соединение с ClickHouse закрыто")
        except Exception as e:
            self.log.error(f"Ошибка при закрытии соединения с ClickHouse: {e}", exc_info=True)