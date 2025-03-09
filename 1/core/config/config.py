from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.config import logger


class PostgresSettings(BaseModel):
    host: str = Field("localhost", description="Database host")
    port: int = Field(5432, description="Database port")
    username: str = Field("postgres", description="Username")
    password: SecretStr = Field("postgres", description="Password")
    db: str = Field("postgres", description="Database name")
    min_pool_size: int = Field(5, description="Minimum connection pool size")
    max_pool_size: int = Field(20, description="Maximum connection pool size")
    bg_min_pool_size: int = Field(2, description="Minimum background task pool size")
    bg_max_pool_size: int = Field(10, description="Maximum background task pool size")
    application_name: str = Field("e-Comet", description="Application name in the database")
    max_inactive_connection_lifetime: int = Field(1800, description="Maximum lifetime of an inactive connection")
    max_cached_statement_lifetime: int = Field(0, description="Maximum lifetime of a cached query")

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.username}:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.db}"


class DatabaseSettings(BaseModel):
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)


class Settings(BaseSettings):
    project_name: str = Field("e-Comet", description="Project name")
    debug: bool = Field(False, description="Debug mode")
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    logging: logger.LoggingSettings = Field(default_factory=logger.LoggingSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__"
    )


def get_settings() -> Settings:
    return Settings()