from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings


@dataclass(frozen=True)
class DatabaseHealth:
    ok: bool
    message: str


def check_database() -> DatabaseHealth:
    settings = get_settings()
    try:
        engine = create_engine(
            settings.database_url,
            connect_args={"connect_timeout": 3},
            pool_pre_ping=True,
        )
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        return DatabaseHealth(ok=False, message=f"Database unavailable: {exc.__class__.__name__}")
    except OSError as exc:
        return DatabaseHealth(
            ok=False,
            message=f"Database connection failed: {exc.__class__.__name__}",
        )

    return DatabaseHealth(ok=True, message="Database connection succeeded")
