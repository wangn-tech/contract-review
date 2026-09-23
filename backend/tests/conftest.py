"""Test fixtures: SQLite in-memory DB + fakeredis + app dependency overrides."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-0123456789abcdef")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("UPLOAD_DIR", "/tmp/contract-review-uploads")
os.environ.setdefault("OSS_BUCKET_DIR", "/tmp/contract-review-parsed")

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

import app.core.redis as redis_mod
import app.main as main_mod
from app.core.db import Base, engine, get_db
from app.main import app


@pytest.fixture()
def client():
    # in-memory SQLite: create schema per test
    Base.metadata.create_all(bind=engine)

    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    redis_mod.redis_client = fake_redis

    async def _noop() -> None:
        return None

    # 跳过 lifespan 中的真实 Redis 初始化
    main_mod.init_redis = _noop  # type: ignore[assignment]
    main_mod.close_redis = _noop  # type: ignore[assignment]

    def override_get_db():
        from app.core.db import SessionLocal

        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    redis_mod.redis_client = None
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def auth_headers(client):
    """注册并登录，返回带 Authorization 的请求头。"""
    resp = client.post("/api/users", json={"username": "tester", "password": "secret123"})
    assert resp.status_code == 200, resp.text
    login = client.post(
        "/api/auth/login", json={"identifier": "tester", "password": "secret123"}
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
