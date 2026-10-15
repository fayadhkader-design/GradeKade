import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import routes
from app.db import Base, get_db
from app.main import app
from app.services.storage import LocalStorage


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine, expire_on_commit=False)
    with session_factory() as db:
        routes.ensure_demo_identity(db)

    def override():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(routes, "storage", LocalStorage(tmp_path))
    # No lifespan: test database has its own identity, not the development database.
    yield TestClient(app), session_factory
    app.dependency_overrides.clear()
    engine.dispose()
