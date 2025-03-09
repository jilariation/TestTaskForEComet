import asyncio
from typing import Annotated

import asyncpg
import uvicorn
from fastapi import APIRouter, FastAPI, Depends, Request
from fastapi.responses import JSONResponse

from core.config.config import get_settings
from core.config.logger import get_logger, setup_logging
from core.exception.base_exception import BaseAppException
from core.exception.db_exception import DatabaseConnectionError
from core.postgres import get_db_dependencies
from core.postgres.pool import DatabaseClient


def get_db_version(
        conn: Annotated[asyncpg.Connection, Depends]
):
    try:
        logger = get_logger()
        logger.info("Requesting database version")
        return conn.fetchval("SELECT version()")
    except Exception as e:
        logger = get_logger()
        logger.error(f"Error while getting database version: {str(e)}")
        raise DatabaseConnectionError("Failed to get database version") from e


def register_routes(app: FastAPI, db_dependencies) -> None:
    logger = get_logger()
    router = APIRouter(prefix="/api")

    @router.get("/db_version")
    async def db_version_endpoint(
            conn: Annotated[asyncpg.Connection, Depends(db_dependencies.get_pg_connection)]
    ):
        return await get_db_version(conn)

    app.include_router(router)
    logger.info("API routes registered")


def register_exception_handlers(app: FastAPI) -> None:
    logger = get_logger()

    @app.exception_handler(BaseAppException)
    async def base_exception_handler(request: Request, exc: BaseAppException):
        logger.error(f"Handled exception: {exc.code} - {exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.message, "code": exc.code, "details": exc.details},
        )

    logger.info("Exception handlers registered")


async def handle_startup(settings, logger, db_client):
    logger.info(f"Starting application {settings.project_name}")
    await db_client.connect()


async def handle_shutdown(settings, logger, db_client):
    logger.info(f"Stopping application {settings.project_name}")
    await db_client.disconnect()


def register_lifecycle_events(app: FastAPI, db_client: DatabaseClient) -> None:
    settings = get_settings()
    logger = get_logger()

    def run_startup():
        loop = asyncio.get_event_loop()
        loop.create_task(handle_startup(settings, logger, db_client))

    def run_shutdown():
        loop = asyncio.get_event_loop()
        loop.create_task(handle_shutdown(settings, logger, db_client))

    app.add_event_handler("startup", run_startup)
    app.add_event_handler("shutdown", run_shutdown)


def create_app() -> FastAPI:
    settings = get_settings()
    logger = setup_logging(settings.logging)
    db_client = DatabaseClient(settings, logger)
    db_dependencies = get_db_dependencies(db_client, logger)

    app = FastAPI(
        title=settings.project_name,
        debug=settings.debug
    )

    register_routes(app, db_dependencies)
    register_exception_handlers(app)
    register_lifecycle_events(app, db_client)

    logger.info(f"Application {settings.project_name} successfully created")
    return app


if __name__ == "__main__":
    uvicorn.run("main:create_app", factory=True)
