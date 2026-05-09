import sys
import uuid
import json
import os
import psycopg2
import asyncpg
import asyncio
from dataclasses import dataclass
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from dotenv import load_dotenv
import pytest

load_dotenv(os.path.join(os.path.dirname(__file__), '../../..', '.env'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

DATABASE_URL = os.environ["DATABASE_URL"]

TEST_USER_STARTER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TEST_USER_PAID_ID    = uuid.UUID("00000000-0000-0000-0000-000000000002")
TEST_USER_BROKE_ID   = uuid.UUID("00000000-0000-0000-0000-000000000003")

@dataclass
class MockUser:
    id: uuid.UUID
    email: str


def get_sync_conn():
    """Synchronous psycopg2 connection — no event loop issues."""
    return psycopg2.connect(DATABASE_URL)


def seed_test_users_sync():
    """Seed test users synchronously."""
    conn = get_sync_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO users (user_id, google_id, email, name, plan_tier, credits_remaining, session_version)
            VALUES (%s, 'test-google-paid', 'paid@advertwise.in', 'Paid Test User', 'essential', 5, 1)
            ON CONFLICT (user_id) DO UPDATE SET plan_tier='essential', credits_remaining=5
        """, (str(TEST_USER_PAID_ID),))
        cur.execute("""
            INSERT INTO users (user_id, google_id, email, name, plan_tier, credits_remaining, session_version)
            VALUES (%s, 'test-google-broke', 'broke@advertwise.in', 'Broke Test User', 'essential', 0, 1)
            ON CONFLICT (user_id) DO UPDATE SET plan_tier='essential', credits_remaining=0
        """, (str(TEST_USER_BROKE_ID),))
        conn.commit()
        print("[SETUP] Test users seeded OK")
    finally:
        cur.close()
        conn.close()


def cleanup_test_data_sync():
    """Delete test data synchronously in FK-safe order."""
    conn = get_sync_conn()
    cur = conn.cursor()
    try:
        user_ids = (str(TEST_USER_STARTER_ID), str(TEST_USER_PAID_ID), str(TEST_USER_BROKE_ID))
        cur.execute("""
            DELETE FROM status_history WHERE gen_id IN (
                SELECT gen_id FROM generations WHERE user_id IN %s
            )
        """, (user_ids,))
        cur.execute("DELETE FROM generations WHERE user_id IN %s", (user_ids,))
        cur.execute("DELETE FROM wallet_transactions WHERE user_id IN %s",
                    ((str(TEST_USER_PAID_ID), str(TEST_USER_BROKE_ID)),))
        cur.execute("DELETE FROM users WHERE user_id IN %s",
                    ((str(TEST_USER_PAID_ID), str(TEST_USER_BROKE_ID)),))
        conn.commit()
        print("[TEARDOWN] Cleanup done OK")
    finally:
        cur.close()
        conn.close()


def seed_generation_sync(user_id: uuid.UUID, status: str,
                          chat_turns_used: int = 3) -> str:
    """Insert a test generation row synchronously."""
    gen_id = uuid.uuid4()
    scripts = json.dumps([{
        "hook": "Test hook", "body": "Test body", "cta": "Buy now",
        "full_text": "Test hook. Test body. Buy now.", "word_count": 6,
        "language_mix": "en", "framework": "pas_micro",
        "framework_angle": "problem_agitation",
        "framework_rationale": "Test rationale",
        "evidence_note": "test", "suggested_tone": "energetic",
        "critic_score": 85, "critic_rationale": "Good script"
    }] * 3)
    brief = json.dumps({
        "category": "skincare",
        "product_name": "Test Product",
        "key_features": ["feature1", "feature2"]
    })
    conn = get_sync_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO generations (
                gen_id, user_id, status, chat_turns_used,
                safe_scripts, selected_script_id, product_brief,
                tts_language, plan_tier, source_url
            ) VALUES (%s, %s, %s::job_status, %s, %s::jsonb, 1,
                      %s::jsonb, 'en', 'essential', 'https://test.com')
        """, (str(gen_id), str(user_id), status, chat_turns_used, scripts, brief))
        conn.commit()
    finally:
        cur.close()
        conn.close()
    return str(gen_id)


def set_regenerate_count_sync(gen_id: str, count: int):
    conn = get_sync_conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE generations SET regenerate_count=%s WHERE gen_id=%s",
                    (count, gen_id))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_generation_row_sync(gen_id: str) -> dict:
    conn = get_sync_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT status, safe_scripts, refined_script FROM generations WHERE gen_id=%s",
                    (gen_id,))
        row = cur.fetchone()
        if row:
            return {"status": row[0], "safe_scripts": row[1], "refined_script": row[2]}
        return {}
    finally:
        cur.close()
        conn.close()


@pytest.fixture(scope="session", autouse=True)
def setup_users():
    """Session-scoped SYNC fixture — no event loop conflict."""
    seed_test_users_sync()
    yield
    cleanup_test_data_sync()


def setup_app_state_mock():
    """Mock app.state so routes don't crash on missing Redis/DB."""
    from app.main import app
    import asyncpg as _asyncpg

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=True)
    mock_redis.lpush = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock(return_value=True)

    mock_redis_mgr = MagicMock()
    mock_redis_mgr.db0 = mock_redis
    mock_redis_mgr.db2 = mock_redis
    mock_redis_mgr.db5 = mock_redis

    app.state.redis_db0 = mock_redis
    app.state.redis_db2 = mock_redis
    app.state.redis_db5 = mock_redis
    app.state.redis_mgr = mock_redis_mgr
    app.state.r2_client = MagicMock()
    app.state.arq_pool = AsyncMock()

    # Real DB pool — routes need actual DB
    if not hasattr(app.state, 'db_pool') or app.state.db_pool is None:
        pool = asyncio.get_event_loop().run_until_complete(
            _asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)
        )
        app.state.db_pool = pool
        app.state.db = pool


def make_client(user_id: uuid.UUID, email: str) -> AsyncClient:
    from app.main import app
    from app.api.dependencies import get_current_user
    import app.api.dependencies as _deps
    import functools

    # Passthrough @idempotent — no Redis actlock in tests
    def _passthrough(ttl=300, action_key="default", cache_only_2xx=True):
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    _deps.idempotent = _passthrough

    setup_app_state_mock()

    mock_user = MockUser(id=user_id, email=email)
    async def override():
        return mock_user
    app.dependency_overrides[get_current_user] = override

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# Expose sync helpers to tests
seed_generation = seed_generation_sync
set_regenerate_count = set_regenerate_count_sync
get_generation_row = get_generation_row_sync
