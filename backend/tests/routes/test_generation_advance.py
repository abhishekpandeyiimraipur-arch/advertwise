import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID
from fastapi.testclient import TestClient

from app.main import app
from app.auth import get_current_user, User

# SSE endpoint tested in E2E tests

def override_get_current_user():
    return User(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        email="test@test.com"
    )

app.dependency_overrides[get_current_user] = override_get_current_user

# Helper row builder
def _gen_row(status="brief_ready", confidence=0.92):
    return {
        "gen_id": "00000000-0000-0000-0000-000000000123",
        "status": status,
        "confidence_score": confidence,
        "isolated_png_url": "isolated/test-gen-123/product.png",
        "source_url": "http://example.com",
        "product_brief": {"category": "d2c_beauty", "product_name": "Test"},
        "agent_motion_suggestion": "zoom_out",
        "user_id": "00000000-0000-0000-0000-000000000001",
    }

class MockConn:
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        pass
    async def fetchrow(self, *args, **kwargs):
        pass
    async def fetch(self, *args, **kwargs):
        pass
    async def execute(self, *args, **kwargs):
        pass

class MockPool:
    def __init__(self, conn):
        self.conn = conn
    def acquire(self):
        return self.conn

@pytest.fixture
def mock_db_pool():
    conn = MockConn()
    pool = MockPool(conn)
    return pool, conn

@pytest.fixture
def mock_db():
    db = AsyncMock()
    return db

import sys
sys.modules["arq"] = MagicMock()
sys.modules["arq.connections"] = MagicMock()

@pytest.fixture
def mock_redis_mgr():
    mgr = MagicMock()
    mgr.connect = AsyncMock()
    mgr.disconnect = AsyncMock()
    mgr.db0 = AsyncMock()
    mgr.db5 = AsyncMock()
    return mgr

@pytest.fixture
def client(mock_db_pool, mock_db, mock_redis_mgr):
    pool, conn = mock_db_pool
    app.state.db = mock_db
    app.state.db_pool = pool
    app.state.redis_mgr = mock_redis_mgr
    
    with patch("app.main.redis_mgr", mock_redis_mgr):
        with TestClient(app) as c:
            yield c, conn, mock_db, mock_redis_mgr


# TEST 1 — test_get_generation_returns_confidence_band_green
@patch("app.routes.generation_advance.boto3.client")
def test_get_generation_returns_confidence_band_green(mock_boto_client, client):
    c, conn, db, redis_mgr = client
    
    db.fetchrow.return_value = _gen_row(confidence=0.92)
    db.fetch.return_value = []
    
    mock_s3 = MagicMock()
    mock_s3.generate_presigned_url.return_value = "https://r2.example.com/presigned"
    mock_boto_client.return_value = mock_s3
    
    with patch.dict("os.environ", {"R2_ENDPOINT_URL": "http://mock", "R2_ACCESS_KEY_ID": "mock", "R2_SECRET_ACCESS_KEY": "mock", "R2_BUCKET_NAME": "mock"}):
        response = c.get("/api/generations/00000000-0000-0000-0000-000000000123")
        
    assert response.status_code == 200
    data = response.json()
    assert data["confidence_band"] == "green"
    assert data["confidence_score"] == 0.92
    assert "isolated_png_url" in data

# TEST 2 — test_get_generation_confidence_band_yellow
@patch("app.routes.generation_advance.boto3.client")
def test_get_generation_confidence_band_yellow(mock_boto_client, client):
    c, conn, db, redis_mgr = client
    db.fetchrow.return_value = _gen_row(confidence=0.87)
    db.fetch.return_value = []
    
    with patch.dict("os.environ", {"R2_ENDPOINT_URL": "http://mock", "R2_ACCESS_KEY_ID": "mock", "R2_SECRET_ACCESS_KEY": "mock", "R2_BUCKET_NAME": "mock"}):
        response = c.get("/api/generations/00000000-0000-0000-0000-000000000123")
    
    assert response.status_code == 200
    assert response.json()["confidence_band"] == "yellow"

# TEST 3 — test_get_generation_confidence_band_red
@patch("app.routes.generation_advance.boto3.client")
def test_get_generation_confidence_band_red(mock_boto_client, client):
    c, conn, db, redis_mgr = client
    db.fetchrow.return_value = _gen_row(confidence=0.80)
    db.fetch.return_value = []
    
    with patch.dict("os.environ", {"R2_ENDPOINT_URL": "http://mock", "R2_ACCESS_KEY_ID": "mock", "R2_SECRET_ACCESS_KEY": "mock", "R2_BUCKET_NAME": "mock"}):
        response = c.get("/api/generations/00000000-0000-0000-0000-000000000123")
    
    assert response.status_code == 200
    assert response.json()["confidence_band"] == "red"

# TEST 4 — test_get_generation_not_found
def test_get_generation_not_found(client):
    c, conn, db, redis_mgr = client
    db.fetchrow.return_value = None
    response = c.get("/api/generations/00000000-0000-0000-0000-000000000999")
    assert response.status_code == 404

# TEST 5 — test_get_generation_director_tips_failure_silent
@patch("app.routes.generation_advance.boto3.client")
def test_get_generation_director_tips_failure_silent(mock_boto_client, client):
    c, conn, db, redis_mgr = client
    db.fetchrow.return_value = _gen_row(confidence=0.92)
    db.fetch.side_effect = Exception("table not found")
    
    with patch.dict("os.environ", {"R2_ENDPOINT_URL": "http://mock", "R2_ACCESS_KEY_ID": "mock", "R2_SECRET_ACCESS_KEY": "mock", "R2_BUCKET_NAME": "mock"}):
        response = c.get("/api/generations/00000000-0000-0000-0000-000000000123")
    
    assert response.status_code == 200
    assert response.json()["director_tips"] == []

# TEST 6 — test_advance_happy_path
def test_advance_happy_path(client):
    c, conn, db, redis_mgr = client
    conn.fetchrow = AsyncMock(return_value=_gen_row(status="brief_ready", confidence=0.92))
    redis_mgr.db5.set = AsyncMock(return_value=True)
    redis_mgr.db5.delete = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    conn.fetch = AsyncMock(return_value=[])
    redis_mgr.db0.lpush = AsyncMock()
    redis_mgr.db0.expire = AsyncMock()
    
    mock_arq_pool = AsyncMock()
    sys.modules["arq"].create_pool = AsyncMock(return_value=mock_arq_pool)
    
    response = c.post("/api/generations/00000000-0000-0000-0000-000000000123/advance")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "scripting"
    assert data["confidence_band"] == "green"
    
    redis_mgr.db5.delete.assert_called_once()
    mock_arq_pool.enqueue_job.assert_called_once_with("phase2_chain", gen_id="00000000-0000-0000-0000-000000000123", _queue_name="phase1_to_3_workers")

# TEST 7 — test_advance_wrong_status_returns_409
def test_advance_wrong_status_returns_409(client):
    c, conn, db, redis_mgr = client
    conn.fetchrow = AsyncMock(return_value=_gen_row(status="scripting"))
    redis_mgr.db5.set = AsyncMock(return_value=True)
    redis_mgr.db5.delete = AsyncMock()
    
    response = c.post("/api/generations/00000000-0000-0000-0000-000000000123/advance")
    
    assert response.status_code == 409
    assert "current_status" in response.json()["detail"]
    redis_mgr.db5.delete.assert_called_once()

# TEST 8 — test_advance_actlock_conflict_returns_409
def test_advance_actlock_conflict_returns_409(client):
    c, conn, db, redis_mgr = client
    redis_mgr.db5.set = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    
    response = c.post("/api/generations/00000000-0000-0000-0000-000000000123/advance")
    
    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == "ECM-012"
    conn.execute.assert_not_called()

# TEST 9 — test_advance_arq_failure_does_not_fail_request
def test_advance_arq_failure_does_not_fail_request(client):
    c, conn, db, redis_mgr = client
    conn.fetchrow = AsyncMock(return_value=_gen_row(status="brief_ready", confidence=0.92))
    redis_mgr.db5.set = AsyncMock(return_value=True)
    redis_mgr.db5.delete = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    conn.fetch = AsyncMock(return_value=[])
    redis_mgr.db0.lpush = AsyncMock()
    redis_mgr.db0.expire = AsyncMock()
    
    sys.modules["arq"].create_pool = AsyncMock(side_effect=ConnectionError("Redis down"))
    
    response = c.post("/api/generations/00000000-0000-0000-0000-000000000123/advance")
    
    assert response.status_code == 200
    assert response.json()["status"] == "scripting"

# TEST 10 — test_advance_state_guard_concurrent_update
def test_advance_state_guard_concurrent_update(client):
    c, conn, db, redis_mgr = client
    conn.fetchrow = AsyncMock(return_value=_gen_row(status="brief_ready", confidence=0.92))
    redis_mgr.db5.set = AsyncMock(return_value=True)
    redis_mgr.db5.delete = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 0")
    conn.fetch = AsyncMock(return_value=[])
    
    response = c.post("/api/generations/00000000-0000-0000-0000-000000000123/advance")
    
    assert response.status_code == 409
    assert "concurrent" in response.json()["detail"]["error"]
    redis_mgr.db5.delete.assert_called_once()
