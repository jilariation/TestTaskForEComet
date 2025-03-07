from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.config import logger


class PostgresSettings(BaseModel):
    host: str = Field("localhost", description="Хост базы данных")
    port: int = Field(5432, description="Порт базы данных")
    username: str = Field("postgres", description="Имя пользователя")
    password: SecretStr = Field("postgres", description="Пароль")
    db: str = Field("postgres", description="Имя базы данных")
    min_pool_size: int = Field(5, description="Минимальный размер пула подключений")
    max_pool_size: int = Field(20, description="Максимальный размер пула подключений")
    bg_min_pool_size: int = Field(2, description="Минимальный размер пула для фоновых задач")
    bg_max_pool_size: int = Field(10, description="Максимальный размер пула для фоновых задач")
    application_name: str = Field("e-Comet", description="Имя приложения в БД")
    max_inactive_connection_lifetime: int = Field(1800, description="Максимальное время жизни неактивного соединения")
    max_cached_statement_lifetime: int = Field(0, description="Максимальное время жизни кешированного запроса")

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.username}:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.db}"


class DatabaseSettings(BaseModel):
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)


class Settings(BaseSettings):
    project_name: str = Field("e-Comet", description="Название проекта")
    debug: bool = Field(False, description="Режим отладки")
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    logging: logger.LoggingSettings = Field(default_factory=logger.LoggingSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__"
    )


def get_settings() -> Settings:
    return Settings()