"""
Pytest configuration and fixtures
"""
import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import app and database
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.main import app
from api.database.models import Base
from api.database.session import get_db


# Test database URL (in-memory SQLite)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def test_db():
    """Create test database"""
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield engine

    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(test_db):
    """Create test client"""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_image_bytes():
    """Generate a simple test image"""
    from PIL import Image
    import io

    # Create a simple RGB image
    img = Image.new('RGB', (224, 224), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)

    return img_bytes.getvalue()


@pytest.fixture
def auth_headers():
    """Mock authentication headers"""
    return {
        "Authorization": "Bearer test_token",
        "X-User-ID": "test_user_123",
        "X-Tenant-ID": "test_tenant_123"
    }


@pytest.fixture
def mock_redis(monkeypatch):
    """Mock Redis client"""
    class MockRedis:
        def __init__(self):
            self.store = {}

        async def get(self, key):
            return self.store.get(key)

        async def set(self, key, value, expire=None):
            self.store[key] = value
            return True

        async def delete(self, key):
            self.store.pop(key, None)
            return True

        def is_connected(self):
            return True

    mock_redis_instance = MockRedis()

    from api.utils import redis_client
    monkeypatch.setattr(redis_client, "get", mock_redis_instance.get)
    monkeypatch.setattr(redis_client, "set", mock_redis_instance.set)
    monkeypatch.setattr(redis_client, "delete", mock_redis_instance.delete)
    monkeypatch.setattr(redis_client, "is_connected", mock_redis_instance.is_connected)

    return mock_redis_instance
