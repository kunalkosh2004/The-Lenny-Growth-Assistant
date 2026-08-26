from pydantic import BaseModel

from app.db.health import DatabaseHealth


class HealthResponse(BaseModel):
    status: str
    app_env: str


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, DatabaseHealth]
