from core.exception import base_exception


class DatabaseConnectionError(base_exception.BaseAppException):
    def __init__(
        self,
        message: str = "Database connection error",
        details: dict = None
    ):
        super().__init__(
            message=message,
            code="DATABASE_CONNECTION_ERROR",
            status_code=503,
            details=details
        )
