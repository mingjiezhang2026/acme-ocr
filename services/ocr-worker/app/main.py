from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.database import Database
from app.services.bootstrap_service import BootstrapService
from app.services.export_service import ExportService
from app.services.job_service import JobService


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.worker_log_file)
    logger = get_logger(__name__)
    settings.ensure_directories()

    database = Database(settings.database_path)
    database.initialize()

    bootstrap_service = BootstrapService(settings)
    export_service = ExportService(settings, database)
    job_service = JobService(settings, database, bootstrap_service)

    app.state.database = database
    app.state.bootstrap_service = bootstrap_service
    app.state.export_service = export_service
    app.state.job_service = job_service

    logger.info("AcmeOCR worker started")
    try:
        yield
    finally:
        await job_service.shutdown()
        database.close()
        logger.info("AcmeOCR worker stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AcmeOCR Local Worker",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app

