from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.config import logger


class GithubSettings(BaseModel):
    access_token: str = Field("", description="Токен доступа к GitHub API")
    max_concurrent_requests: int = Field(10, description="Максимальное количество одновременных запросов")
    requests_per_second: int = Field(5, description="Ограничение запросов в секунду")
    top_repos_limit: int = Field(100, description="Лимит топовых репозиториев")
    commits_since_days: int = Field(1, description="За сколько дней назад искать коммиты")


class Settings(BaseSettings):
    project_name: str = Field("e-Comet", description="Название проекта")
    debug: bool = Field(False, description="Режим отладки")
    logging: logger.LoggingSettings = Field(default_factory=logger.LoggingSettings)

    github: GithubSettings = Field(default_factory=GithubSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__"
    )


def get_settings() -> Settings:
    return Settings()