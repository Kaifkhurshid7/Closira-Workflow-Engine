"""
Closira Enquiry Engine — Application Entry Point
─────────────────────────────────────────────────
FastAPI app with lifespan management and global error handling.

Run with:
    uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.config import settings
from src.database import init_db
from src.logger import logger
from src.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB. Shutdown: log graceful exit."""
    logger.info("Starting Closira Enquiry Engine — initialising database...")
    await init_db()
    logger.info("Database ready.")
    yield
    logger.info("Closira Enquiry Engine shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "REST API powering Closira's inbound customer enquiry-handling pipeline. "
        "Handles enquiry creation, async SOP matching, follow-ups, escalations, "
        "and full conversation history retrieval.\n\n"
        "**Channels supported:** WhatsApp · Email · Call\n\n"
        "**Async processing:** FastAPI BackgroundTasks (see README for rationale)\n\n"
        "**Database:** SQLite via aiosqlite (see README for rationale)"
    ),
    version=settings.APP_VERSION,
    contact={"name": "Closira Engineering", "email": "eng@closira.com"},
    lifespan=lifespan,
)

app.include_router(router)


# ── Global Exception Handler ─────────────────────────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all for unhandled exceptions.
    Logs full context for debugging, returns safe message to client.
    No stack traces leak to the outside.
    """
    logger.error(
        "Unhandled exception",
        extra={
            "path": request.url.path,
            "method": request.method,
            "error": str(exc),
            "event": "unhandled_exception",
        },
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again later."},
    )
