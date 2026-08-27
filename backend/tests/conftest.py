import os
from collections.abc import Generator

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.core.config import Settings, get_settings
from app.db.session import get_db, reset_session_state
from app.main import app

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _database_available(database_url: str) -> bool:
    try:
        engine = create_engine(database_url, connect_args={"connect_timeout": 3})
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except OperationalError:
        return False


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    database_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://lenny:lenny_dev_password@localhost:5434/lenny_growth_assistant",
    )
    return Settings(
        database_url=database_url,
        app_env="test",
        log_level="WARNING",
    )


@pytest.fixture(scope="session")
def migrated_database(test_settings: Settings) -> Generator[str, None, None]:
    if not _database_available(test_settings.database_url):
        pytest.skip("PostgreSQL is not available for persistence tests.")

    get_settings.cache_clear()
    reset_session_state()
    os.environ["DATABASE_URL"] = test_settings.database_url

    alembic_cfg = Config(os.path.join(BACKEND_ROOT, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(BACKEND_ROOT, "alembic"))
    command.upgrade(alembic_cfg, "head")

    yield test_settings.database_url

    get_settings.cache_clear()
    reset_session_state()


@pytest.fixture()
def db_session(migrated_database: str) -> Generator[Session, None, None]:
    get_settings.cache_clear()
    reset_session_state()
    os.environ["DATABASE_URL"] = migrated_database

    engine = create_engine(migrated_database)
    connection = engine.connect()
    transaction = connection.begin()

    # Start each test from a clean slate so real/manual usage data on the
    # shared dev database cannot leak into assertions. This DELETE happens
    # inside the transaction below and is rolled back afterwards, so it
    # never touches persisted data.
    for table in ("messages", "chat_sessions", "users"):
        connection.execute(text(f"DELETE FROM {table}"))

    session = sessionmaker(bind=connection, autoflush=False, autocommit=False)()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()
        get_settings.cache_clear()
        reset_session_state()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
