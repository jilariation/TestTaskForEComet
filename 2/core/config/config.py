from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.config import logger


class GithubSettings(BaseModel):
    access_token: str = Field("", description="GitHub API access token")
    max_concurrent_requests: int = Field(10, description="Maximum number of concurrent requests")
    requests_per_second: int = Field(5, description="Rate limit for requests per second")
    top_repos_limit: int = Field(100, description="Limit for top repositories")
    commits_since_days: int = Field(1, description="Search for commits from how many days ago")


class Settings(BaseSettings):
    project_name: str = Field("e-Comet", description="Project name")
    debug: bool = Field(False, description="Debug mode")
    logging: logger.LoggingSettings = Field(default_factory=logger.LoggingSettings)

    github: GithubSettings = Field(default_factory=GithubSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__"
    )


def get_settings() -> Settings:
    return Settings()
