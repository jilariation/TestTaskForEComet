import asyncio
import logging
import typing

import asyncpg

from core.config.config import Settings, PostgresSettings
from core.config.logger import LoggerAdapter
from core.exception.db_exception import DatabaseConnectionError


class MultiLoopPool:

    def __init__(self, logger: logging.Logger, **kwargs):
        self.kwargs = kwargs
        self._pools: typing.Dict[asyncio.AbstractEventLoop, asyncpg.Pool] = {}
        self._logger = LoggerAdapter(logger, {"component": "MultiLoopPool"})

    def __await__(self):
        async def _get_pool():
            await self._get_pool()
            return self

        return _get_pool().__await__()

    @property
    def pool(self) -> asyncpg.Pool:
        return self._pools[asyncio.get_event_loop()]

    async def connect(self) -> asyncpg.Pool:
        self._logger.info("Connecting to the database")
        return await self._get_pool()

    async def acquire(self, *, timeout=None):
        pool = await self._get_pool()
        self._logger.debug("Acquiring connection from pool")
        return await pool.acquire(timeout=timeout)

    async def release(self, conn):
        pool = await self._get_pool()
        self._logger.debug("Releasing connection back to pool")
        await pool.release(conn)

    async def close(self):
        self._logger.info("Closing all connection pools")
        pools = list(self._pools.values())
        self._pools.clear()
        for pool in pools:
            await pool.close()

    async def _get_pool(self):
        loop = asyncio.get_event_loop()
        rv = self._pools.get(loop)
        if rv is None:
            try:
                self._logger.debug(f"Creating new pool for loop {id(loop)}")
                rv = self._pools[loop] = await asyncpg.create_pool(**self.kwargs)
            except Exception as e:
                self._logger.error(f"Pool creation error: {str(e)}")
                raise DatabaseConnectionError(
                    message=f"Failed to create connection pool: {str(e)}",
                    details={"host": self.kwargs.get("host"), "db": self.kwargs.get("database")}
                ) from e
        return rv

    async def close_for_thread(self):
        self._logger.info("Closing pool for current thread")
        await (await self._get_pool()).close()


class DatabaseClient:

    def __init__(self, settings: Settings, logger: logging.Logger):
        self._settings = settings
        self._logger = LoggerAdapter(logger, {"component": "DatabaseClient"})
        self._pool: typing.Optional[MultiLoopPool] = None

    def _create_pool_kwargs(self, postgres_settings: PostgresSettings, is_scheduler: bool = False) -> typing.Dict[str, typing.Any]:
        min_size = postgres_settings.bg_min_pool_size if is_scheduler else postgres_settings.min_pool_size
        max_size = postgres_settings.bg_max_pool_size if is_scheduler else postgres_settings.max_pool_size

        return {
            "host": postgres_settings.host,
            "port": postgres_settings.port,
            "user": postgres_settings.username,
            "password": postgres_settings.password.get_secret_value(),
            "database": postgres_settings.db,
            "min_size": min_size,
            "max_size": max_size,
            "max_inactive_connection_lifetime": postgres_settings.max_inactive_connection_lifetime,
            "max_cached_statement_lifetime": postgres_settings.max_cached_statement_lifetime,
            "server_settings": {'application_name': postgres_settings.application_name}
        }

    def get_pool(self) -> MultiLoopPool:
        if not self._pool:
            postgres_settings = self._settings.database.postgres
            self._pool = MultiLoopPool(
                logger=self._logger.logger,
                **self._create_pool_kwargs(postgres_settings)
            )
        return self._pool

    async def connect(self, is_scheduler: bool = False) -> None:
        try:
            if is_scheduler and self._pool:
                postgres_settings = self._settings.database.postgres
                self._pool.kwargs.update({
                    "min_size": postgres_settings.bg_min_pool_size,
                    "max_size": postgres_settings.bg_max_pool_size
                })

            pool = self.get_pool()
            await pool.connect()
            self._logger.info(
                f"Successfully connected to the database {self._settings.database.postgres.host}:{self._settings.database.postgres.port}/{self._settings.database.postgres.db}")
        except Exception as e:
            self._logger.error(f"Database connection error: {str(e)}")
            raise DatabaseConnectionError(
                message="Database connection error",
                details={"error": str(e)}
            ) from e

    async def disconnect(self) -> None:
        try:
            if self._pool:
                await self._pool.close()
                self._logger.info("Successfully disconnected from the database")
        except Exception as e:
            self._logger.error(f"Database disconnection error: {str(e)}")
            raise DatabaseConnectionError(
                message="Database disconnection error",
                details={"error": str(e)}
            ) from e
