import logging
import typing

import asyncpg

from core.config.logger import LoggerAdapter
from core.exception.db_exception import DatabaseConnectionError
from core.postgres import pool


class DatabaseDependencies:

    def __init__(self, db_client: pool.DatabaseClient, logger: logging.Logger):

        self._db_client = db_client
        self._logger = LoggerAdapter(logger, {"component": "DatabaseDependencies"})

    async def get_pg_connection(self) -> typing.AsyncGenerator[asyncpg.Connection, None]:
        try:
            pool = self._db_client.get_pool()
            connection = await pool.acquire()
            try:
                self._logger.debug("Получено соединение с базой данных")
                yield connection
                self._logger.debug("Соединение с базой данных возвращено в пул")
            finally:
                await pool.release(connection)
        except Exception as e:
            self._logger.error(f"Ошибка при работе с подключением к базе данных: {str(e)}")
            raise DatabaseConnectionError("Ошибка при работе с подключением к базе данных") from e


def get_db_dependencies(db_client: pool.DatabaseClient, logger: logging.Logger) -> DatabaseDependencies:
    return DatabaseDependencies(db_client, logger)