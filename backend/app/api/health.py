from fastapi import APIRouter

from app.core.config import get_settings
from app.db.health import check_database
from app.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", app_env=settings.app_env)


@router.get("/health/ready", response_model=ReadinessResponse)
def readiness() -> ReadinessResponse:
    database = check_database()
    status = "ready" if database.ok else "degraded"
    return ReadinessResponse(status=status, checks={"database": database})
