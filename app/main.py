"""Main FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.routes import router as api_router
from app.config import settings
from app.core.logging_config import setup_logging

# Set up structured logging
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    yield
    # Shutdown
    logger.info(f"Shutting down {settings.app_name}")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="FastAPI backend for pytest test analysis using hybrid rule engine + LLM approach",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware
# NOTE: Configure allowed origins properly for production!
# Current configuration allows all origins for development.
# For production, replace with specific origins:
# allow_origins=["https://yourdomain.com", "https://app.yourdomain.com"]
allowed_origins = settings.cors_origins if hasattr(settings, "cors_origins") else ["*"]

if "*" in allowed_origins:
    logger.warning(
        "CORS is configured to allow all origins. "
        "This is acceptable for development but should be restricted in production."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "FastAPI backend for pytest test analysis",
    }


# Include API routes
app.include_router(api_router, prefix="/api/v1")
