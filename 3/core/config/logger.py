
import logging
import sys
import typing

from pydantic import field_validator
from pydantic_settings import BaseSettings


class LoggingSettings(BaseSettings):
    LEVEL: str = "INFO"
    FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    @field_validator("LEVEL")
    @classmethod
    def validate_level(cls, v: str) -> str:
        if v not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError(f"Invalid logging level: {v}")
        return v


def setup_logging(settings: LoggingSettings = None) -> logging.Logger:
    if settings is None:
        settings = LoggingSettings()

    logger = logging.getLogger("e-comet")
    logger.setLevel(getattr(logging, settings.LEVEL))
    logger.handlers = []

    formatter = logging.Formatter(settings.FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("e-comet")


class LoggerAdapter(logging.LoggerAdapter):

    def __init__(self, logger: logging.Logger, extra: typing.Optional[typing.Dict[str, typing.Any]] = None):
        super().__init__(logger, extra or {})

    def process(self, msg: str, kwargs: typing.Dict[str, typing.Any]) -> tuple:
        extra = kwargs.get("extra", {})

        if self.extra:
            if extra:
                extra.update(self.extra)
            else:
                kwargs["extra"] = self.extra

        context = " ".join([f"[{k}={v}]" for k, v in self.extra.items()]) if self.extra else ""
        if context:
            msg = f"{msg} {context}"

        return msg, kwargs