import typing


class BaseAppException(Exception):
    def __init__(
        self,
        message: str = "Произошла ошибка в приложении",
        code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: typing.Optional[dict] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)