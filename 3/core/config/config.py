from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.config import logger


class GithubSettings(BaseModel):
    access_token: str = Field("", description="Токен доступа к GitHub API")
    max_concurrent_requests: int = Field(10, description="Максимальное количество одновременных запросов")
    requests_per_second: int = Field(5, description="Ограничение запросов в секунду")
    top_repos_limit: int = Field(100, description="Лимит топовых репозиториев")
    commits_since_days: int = Field(1, description="За сколько дней назад искать коммиты")


class ClickHouseSettings(BaseModel):
    host: str = Field("localhost", description="Хост сервера ClickHouse")
    port: int = Field(8123, description="Порт HTTP интерфейса ClickHouse")
    user: str = Field("default", description="Имя пользователя ClickHouse")
    password: SecretStr = Field(default="", description="Пароль пользователя ClickHouse")
    database: str = Field("test", description="Название базы данных")
    batch_size: int = Field(100, description="Размер пакета записей для вставки")
    timeout: float = Field(10.0, description="Таймаут соединения в секундах")

    def get_password(self) -> str:
        return self.password.get_secret_value() if self.password else ""


class Settings(BaseSettings):
    project_name: str = Field("e-Comet", description="Название проекта")
    debug: bool = Field(False, description="Режим отладки")
    logging: logger.LoggingSettings = Field(default_factory=logger.LoggingSettings)

    github: GithubSettings = Field(default_factory=GithubSettings)
    clickhouse: ClickHouseSettings = Field(default_factory=ClickHouseSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__"
    )


def get_settings() -> Settings:
    return Settings()