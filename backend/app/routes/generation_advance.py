import os
import uuid
import asyncio
import json
import logging
from typing import Optional, Dict, Any, List, Annotated
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["generations"])

def _generate_presigned_url_sync(url_or_key: str) -> str:
    """Synchronous helper to generate an R2 presigned URL."""
    r2_endpoint = os.getenv("R2_ENDPOINT_URL")
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    bucket = os.getenv("R2_BUCKET_NAME")
    
    if not all([r2_endpoint, access_key, secret_key, bucket]):
        logger.warning("R2 env vars missing, cannot generate presigned url.")
        raise ValueError("Missing R2 configuration")

    s3_client = boto3.client(
        's3',
        endpoint_url=r2_endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version='s3v4'),
        region_name='auto'
    )
    
    # Extract path portion in case it's a full URL
    parsed = urlparse(url_or_key)
    key = parsed.path.lstrip('/') if parsed.scheme else url_or_key
    
    return s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket, 'Key': key},
        ExpiresIn=600
    )


@router.get("/generations/{gen_id}")
async def get_generation(
    gen_id: uuid.UUID,
    request: Request,
    user = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    GET /api/generations/{gen_id}
    HD-2 mount call. Returns everything the frontend needs to render the isolation review screen.
    """
    db = request.app.state.db
    user_id = user.id

    # Step 1: DB fetch with mandatory user ownership check
    query = """
        SELECT gen_id, status, confidence_score, isolated_png_url,
               source_url, product_brief, agent_motion_suggestion, user_id
        FROM generations
        WHERE gen_id = $1 AND user_id = $2
    """
    row = await db.fetchrow(query, gen_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Generation not found")

    # Step 2: Confidence band computation
    confidence_score = row["confidence_score"]
    if confidence_score is None:
        band = "unknown"
    elif confidence_score >= 0.90:
        band = "green"
    elif 0.85 <= confidence_score < 0.90:
        band = "yellow"
    else:
        band = "red"

    # Step 3: R2 presigned URL for isolated image
    isolated_png_url = row["isolated_png_url"]
    isolated_png_presigned = None
    if isolated_png_url is not None:
        try:
            isolated_png_presigned = await asyncio.to_thread(_generate_presigned_url_sync, isolated_png_url)
        except Exception as e:
            logger.warning(f"Failed to generate presigned URL: {e}", exc_info=True)
            isolated_png_presigned = isolated_png_url

    # Step 4: Director tips fetch
    product_brief = row["product_brief"]
    category = None
    if product_brief and isinstance(product_brief, dict):
        category = product_brief.get("category")

    director_tips = []
    if category:
        try:
            tips_query = """
                SELECT tip_type, copy_en
                FROM director_tips
                WHERE category = $1
                  AND is_active = TRUE
                  AND min_confidence <= $2
                ORDER BY tip_type
            """
            conf_val = float(confidence_score) if confidence_score is not None else 0.0
            tips_records = await db.fetch(tips_query, category, conf_val)
            director_tips = [{"tip_type": t["tip_type"], "copy_en": t["copy_en"]} for t in tips_records]
        except Exception as e:
            logger.warning(f"Failed to fetch director tips: {e}", exc_info=True)
            director_tips = []

    # Step 5: Return 200 JSON
    return {
        "gen_id": str(row["gen_id"]),
        "status": str(row["status"]),
        "confidence_score": confidence_score,
        "confidence_band": band,
        "isolated_png_url": isolated_png_presigned,
        "source_url": row["source_url"],
        "product_brief": product_brief,
        "agent_motion_suggestion": row["agent_motion_suggestion"],
        "director_tips": director_tips
    }

# -------------------------------------------------------------------------
# -------------------------------------------------------------------------
# Part 2 / Part 3 Placeholders

async def sse_event_generator(redis_db0, gen_id: str):
    """
    Polls Redis key "sse:{gen_id}" and yields SSE-formatted strings.
    - RPOP from right = oldest event first (FIFO, worker used LPUSH)
    - Yields heartbeat comment every 500ms if no event (keeps connection alive)
    - Stops after 10 minutes (1200 iterations x 0.5s)
    """
    key = f"sse:{gen_id}"
    iterations = 0
    max_iterations = 1200  # 10 minutes

    while iterations < max_iterations:
        try:
            event = await redis_db0.rpop(key)
            if event:
                yield f"data: {event}\n\n"
            else:
                yield ": heartbeat\n\n"
        except Exception:
            yield ": error heartbeat\n\n"

        await asyncio.sleep(0.5)
        iterations += 1

    yield f"data: {json.dumps({'type': 'stream_timeout'})}\n\n"


@router.get("/sse/{gen_id}")
async def get_sse(
    gen_id: str,
    request: Request,
    user: Annotated[Any, Depends(get_current_user)],
):
    user_id = user.id  # adjust to user.user_id if auth uses dataclass

    # Use db instead of db_pool since db is attached to app state as seen in other routes
    db = request.app.state.db
    row = await db.fetchrow(
        "SELECT gen_id FROM generations WHERE gen_id = $1 AND user_id = $2",
        uuid.UUID(gen_id), user_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Generation not found")

    redis_db0 = request.app.state.redis_mgr.db0

    return StreamingResponse(
        sse_event_generator(redis_db0, gen_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/generations/{gen_id}/advance")
async def advance_generation(
    gen_id: str,
    request: Request,
    user: Annotated[Any, Depends(get_current_user)],
):
    user_id = user.id   # extracted from AuthUser dataclass

    # Use .db if .db_pool is not present, to prevent runtime crashes based on our previous routes
    db_pool   = getattr(request.app.state, "db_pool", getattr(request.app.state, "db", None))
    redis_mgr = request.app.state.redis_mgr
    redis_db0 = redis_mgr.db0
    redis_db5 = redis_mgr.db5   # actlock lives on DB5

    # ── STEP 1: actlock fence (double-click defense) ──────────────────
    # Prevents same user clicking advance twice simultaneously
    lock_key = f"actlock:{gen_id}:advance_brief_ready"
    acquired = await redis_db5.set(lock_key, "1", nx=True, ex=10)
    if not acquired:
        raise HTTPException(
            status_code=409,
            detail={"error": "request already in progress", "error_code": "ECM-012"}
        )

    try:
        # ── STEP 2: Fetch and validate row ────────────────────────────
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT gen_id, status, confidence_score,
                          product_brief, user_id
                   FROM generations
                   WHERE gen_id = $1 AND user_id = $2""",
                uuid.UUID(gen_id), user_id
            )

        if not row:
            raise HTTPException(status_code=404, detail="Generation not found")

        if row["status"] != "brief_ready":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "generation not in brief_ready state",
                    "current_status": row["status"]
                }
            )

        # ── STEP 3: Director tips (static DB read, ZERO LLM) ─────────
        director_tips = []
        try:
            category = None
            if row["product_brief"]:
                brief = row["product_brief"]
                if isinstance(brief, str):
                    import json
                    brief = json.loads(brief)
                category = brief.get("category")

            confidence = float(row["confidence_score"]) if row["confidence_score"] else 0.0

            if category:
                async with db_pool.acquire() as conn:
                    tips = await conn.fetch(
                        """SELECT tip_type, copy_en, copy_hi
                           FROM director_tips
                           WHERE category = $1
                             AND is_active = TRUE
                             AND min_confidence <= $2
                           ORDER BY tip_type""",
                        category, confidence
                    )
                director_tips = [dict(t) for t in tips]
        except Exception as e:
            # Silent degradation — tips table may not exist yet
            import logging
            logging.getLogger(__name__).warning(f"director_tips fetch failed: {e}")
            director_tips = []

        # ── STEP 4: State-guarded UPDATE (optimistic concurrency) ─────
        # WHERE status = 'brief_ready' ensures no double-transition
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                """UPDATE generations
                   SET status = 'scripting', updated_at = NOW()
                   WHERE gen_id = $1 AND status = 'brief_ready'""",
                uuid.UUID(gen_id)
            )

        if result == "UPDATE 0":
            raise HTTPException(
                status_code=409,
                detail={"error": "concurrent state change detected"}
            )

        # ── STEP 5: ARQ enqueue phase2_chain ─────────────────────────
        # phase2_chain not yet implemented — enqueue by name string.
        # ARQ will hold it in queue until the function is registered.
        try:
            import os
            from arq import create_pool
            from arq.connections import RedisSettings
            arq_redis = await create_pool(
                RedisSettings.from_dsn(
                    os.environ.get("REDIS_URL", "redis://localhost:6379/1")
                )
            )
            await arq_redis.enqueue_job(
                "phase2_chain",
                gen_id=gen_id,
                _queue_name="phase1_to_3_workers",
            )
            await arq_redis.aclose()
        except Exception as e:
            # Log but do not fail the request — state is already scripting
            # Phase 2 can be manually re-triggered if needed
            import logging
            logging.getLogger(__name__).error(
                f"advance: ARQ enqueue failed for gen_id={gen_id}: {e}"
            )

        # ── STEP 6: SSE push ──────────────────────────────────────────
        import json
        sse_key = f"sse:{gen_id}"
        await redis_db0.lpush(
            sse_key,
            json.dumps({"type": "state_change", "status": "scripting"})
        )
        await redis_db0.expire(sse_key, 300)

        # ── STEP 7: Compute confidence band for response ──────────────
        score = float(row["confidence_score"]) if row["confidence_score"] else None
        if score is None:
            band = "unknown"
        elif score >= 0.90:
            band = "green"
        elif score >= 0.85:
            band = "yellow"
        else:
            band = "red"

        return {
            "gen_id": gen_id,
            "status": "scripting",
            "confidence_band": band,
            "director_tips": director_tips,
        }

    finally:
        # ALWAYS release the actlock, even if something raised above
        await redis_db5.delete(lock_key)

# -------------------------------------------------------------------------
