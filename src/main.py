from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog
from contextlib import asynccontextmanager

from .api.frameworks import router as frameworks_router
from .api.environments import router as environments_router
from .api.suites import router as suites_router
from .api.results import router as results_router
from .api.artifacts import router as artifacts_router
from .api.auth import router as auth_router
from .services.notification_service import get_notification_service, close_notification_service
from .lib.config import get_settings

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    settings = get_settings()

    # Startup
    logger.info("Starting Test Results Management API", version="0.4.0", env=settings.app.env)

    # Send startup notification
    try:
        notification_service = get_notification_service()
        await notification_service.notify_system_alert(
            title="API Service Started",
            message=f"Test Results Management API v0.4.0 is now running in {settings.app.env} mode",
            severity="info",
            details={
                "Version": "0.4.0",
                "Environment": settings.app.env,
                "Mattermost Enabled": str(settings.mattermost.enabled)
            }
        )
        logger.debug("Service startup notification sent")
    except Exception as e:
        logger.warning("Failed to send startup notification", error=str(e))

    yield

    # Shutdown
    logger.info("Shutting down Test Results Management API")

    # Send shutdown notification
    try:
        notification_service = get_notification_service()
        await notification_service.notify_system_alert(
            title="API Service Shutting Down",
            message="Test Results Management API is shutting down",
            severity="warning"
        )
        logger.debug("Service shutdown notification sent")
    except Exception as e:
        logger.warning("Failed to send shutdown notification", error=str(e))

    # Close notification service
    await close_notification_service()

app = FastAPI(
    title="Test Results Management API",
    description="REST API for managing test execution results from end-to-end testing frameworks",
    version="0.4.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(frameworks_router)
app.include_router(environments_router)
app.include_router(suites_router)
app.include_router(results_router)
app.include_router(artifacts_router)
app.include_router(auth_router)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "test-results-api", "version": "0.4.0"}


@app.get("/")
async def root():
    """API information"""
    return {
        "message": "Test Results Management API",
        "version": "0.4.0",
        "docs_url": "/docs",
        "health_url": "/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)