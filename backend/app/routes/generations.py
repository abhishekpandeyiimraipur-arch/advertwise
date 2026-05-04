import os
import re
import uuid
import asyncio
import logging
from typing import Optional, Union

from fastapi import APIRouter, Request, Header, UploadFile, Depends

# Use absolute import as per the project's standard
from app.infra_gateway import idempotent, AdvertWiseException
from app.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

class InputScrubber:
    """
    Inline scrubber to strictly enforce safety constraints before processing.
    """
    PROMPT_INJECTION_PATTERN = re.compile(r"(ignore previous|system:|<\||]]>)", re.IGNORECASE)
    # Control characters (\x00–\x1f) except \t (0x09), \n (0x0a), \r (0x0d)
    CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

    @classmethod
    def check(cls, payload: dict):
        for val in payload.values():
            if isinstance(val, str):
                if cls.PROMPT_INJECTION_PATTERN.search(val):
                    raise AdvertWiseException(code="ECM-002")
                if cls.CONTROL_CHAR_PATTERN.search(val):
                    raise AdvertWiseException(code="ECM-002")


@router.post("/api/generations", status_code=202)
@idempotent(ttl=300, action_key="create", cache_only_2xx=True)
async def create_generation(
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user = Depends(get_current_user)
):
    """
    POST /api/generations
    HD-1 ingestion route.
    """
    # 1. File size gate (check before reading body to save bandwidth/memory)
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 10 * 1024 * 1024:
        raise AdvertWiseException(code="ECM-014", status_code=413)

    content_type = request.headers.get("content-type", "")
    
    # 2. Accept two payload shapes (Union discriminated by presence)
    source_url: Optional[str] = None
    source_image: Optional[UploadFile] = None
    
    payload_to_scrub = {}

    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            raise AdvertWiseException(code="ECM-002")
            
        if "source_url" not in body:
            raise AdvertWiseException(code="ECM-002")
            
        source_url = body["source_url"]
        if not isinstance(source_url, str):
            raise AdvertWiseException(code="ECM-002")
            
        payload_to_scrub = {"source_url": source_url}

    elif "multipart/form-data" in content_type:
        form = await request.form()
        if "source_image" not in form:
            raise AdvertWiseException(code="ECM-002")
            
        source_image = form["source_image"]
        if not isinstance(source_image, UploadFile):
            raise AdvertWiseException(code="ECM-002")
            
        payload_to_scrub = {"filename": source_image.filename or ""}

    else:
        raise AdvertWiseException(code="ECM-002")

    # 3. Scrub input BEFORE doing any insertions
    InputScrubber.check(payload_to_scrub)

    # 4. Process the upload
    user_id = user.id
    new_gen_id = uuid.uuid4()
    source_image_r2_key: Optional[str] = None
    
    if source_image:
        filename = source_image.filename or "image.bin"
        ext = filename.split(".")[-1] if "." in filename else "bin"
        source_image_r2_key = f"{user_id}/{new_gen_id}/source.{ext}"
        
        r2_client = request.app.state.r2_client
        r2_bucket = os.getenv("R2_BUCKET", "advertwise-uploads")
        
        file_bytes = await source_image.read()
        if len(file_bytes) > 10 * 1024 * 1024:
            raise AdvertWiseException(code="ECM-014", status_code=413)
        await asyncio.to_thread(
            r2_client.put_object,
            Bucket=r2_bucket,
            Key=source_image_r2_key,
            Body=file_bytes,
            ContentType=source_image.content_type or "application/octet-stream"
        )

    # 5. DB Insert
    db = request.app.state.db

    insert_query = """
        INSERT INTO generations (gen_id, user_id, source_url, source_image_url, plan_tier, status)
        VALUES ($1, $2, $3, $4, 'starter', 'queued')
    """
    
    try:
        await db.execute(
            insert_query,
            new_gen_id,
            user_id,
            source_url,
            source_image_r2_key
        )
    except Exception as e:
        logger.error(f"DB insert failed: {e}", exc_info=True)
        # Enforce Hard Invariant: No raw exceptions leak to client
        raise AdvertWiseException(code="ECM-013", status_code=500)

    # 6. ARQ enqueue string reference "phase1_extract"
    arq_pool = request.app.state.arq_pool
    await arq_pool.enqueue_job(
        "phase1_extract",
        gen_id=str(new_gen_id),
        _queue_name="phase1_to_3_workers"
    )

    # 7. Return 202 response (Returns dict to ensure `@idempotent` caching is hit)
    return {
        "gen_id": str(new_gen_id),
        "status": "queued"
    }
