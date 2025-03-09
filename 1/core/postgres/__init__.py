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
                self._logger.debug("Database connection acquired")
                yield connection
                self._logger.debug("Database connection returned to pool")
            finally:
                await pool.release(connection)
        except Exception as e:
            self._logger.error(f"Error while working with database connection: {str(e)}")
            raise DatabaseConnectionError("Error while working with database connection") from e


def get_db_dependencies(db_client: pool.DatabaseClient, logger: logging.Logger) -> DatabaseDependencies:
    return DatabaseDependencies(db_client, logger)
