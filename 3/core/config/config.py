from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.config import logger


class GithubSettings(BaseModel):
    access_token: str = Field("", description="GitHub API access token")
    max_concurrent_requests: int = Field(10, description="Maximum number of concurrent requests")
    requests_per_second: int = Field(5, description="Rate limit for requests per second")
    top_repos_limit: int = Field(100, description="Top repositories limit")
    commits_since_days: int = Field(1, description="Number of days ago to search for commits")


class ClickHouseSettings(BaseModel):
    host: str = Field("localhost", description="ClickHouse server host")
    port: int = Field(8123, description="ClickHouse HTTP interface port")
    user: str = Field("default", description="ClickHouse username")
    password: SecretStr = Field(default="", description="ClickHouse user's password")
    database: str = Field("test", description="Database name")
    batch_size: int = Field(100, description="Batch size for inserting records")
    timeout: float = Field(10.0, description="Connection timeout in seconds")

    def get_password(self) -> str:
        return self.password.get_secret_value() if self.password else ""


class Settings(BaseSettings):
    project_name: str = Field("e-Comet", description="Project name")
    debug: bool = Field(False, description="Debug mode")
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
