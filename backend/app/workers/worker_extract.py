import logging
from rembg import remove, new_session
import numpy as np
import json
import httpx
import asyncio
import io
import os
import base64
from PIL import Image

logger = logging.getLogger(__name__)
logger.info("Warming up BiRefNet model (birefnet-general)...")
GLOBAL_BG_SESSION = new_session("birefnet-general")
logger.info("BiRefNet warm boot complete.")

MAX_SCRAPED_IMAGE_BYTES = 15 * 1024 * 1024   # 15MB — worker-side gate
FIRECRAWL_TIMEOUT_SECONDS = 15

GREEN_ZONE_SET = frozenset({
    "d2c_beauty", "packaged_food", "hard_accessories",
    "electronics", "home_kitchen"
})

MOTION_MAP = {
    "tall_bottle":   "zoom_out",
    "flat_pack":     "slide_in",
    "round":         "spin_reveal",
    "rectangular":   "pan_across",
    "irregular":     "gentle_float",
}
DEFAULT_MOTION = "gentle_float"

def _compute_confidence(isolated_pil: Image.Image) -> float:
    """
    GAP-10: Deterministic isolation quality score from BiRefNet alpha mask.
    Input:  PIL RGBA Image (BiRefNet output).
    Output: float clamped to [0.0, 1.0], rounded to 4 decimal places.
    NO LLM call. NO external API.
    """
    alpha = np.array(isolated_pil.getchannel("A"))
    foreground_ratio = float((alpha > 128).mean())
    soft_edge_ratio  = float(((alpha > 10) & (alpha < 245)).mean())
    raw = foreground_ratio * (1.0 - soft_edge_ratio * 0.4)
    return round(min(max(raw, 0.0), 1.0), 4)

def _suggest_motion(shape: str) -> str:
    """Deterministic shape → motion lookup. No LLM. No external call."""
    return MOTION_MAP.get(shape.lower().strip(), DEFAULT_MOTION)

async def _push_sse(redis_db0, gen_id: str, payload: dict) -> None:
    """LPUSH SSE event to Redis DB0. TTL 300s. Fire-and-forget friendly."""
    key = f"sse:{gen_id}"
    await redis_db0.lpush(key, json.dumps(payload))
    await redis_db0.expire(key, 300)

async def phase1_extract(ctx: dict, *, gen_id: str) -> None:
    """
    ARQ job — registered on phase1_to_3_workers queue.
    ctx keys used: db_pool, redis_db0, r2_client, gateway
    """
    db_pool   = ctx["db_pool"]
    redis_db0 = ctx["redis_db0"]
    r2_client = ctx["r2_client"]
    gateway   = ctx["gateway"]

    async def _fail(ecm: str) -> None:
        """Set terminal failed_category state + SSE. Called on any recoverable error."""
        async with db_pool.acquire() as conn:
            await conn.execute(
                """UPDATE generations
                   SET status = 'failed_category', error_code = $1, updated_at = NOW()
                   WHERE gen_id = $2""",
                ecm, gen_id
            )
        await _push_sse(redis_db0, gen_id, {
            "type": "state_change",
            "status": "failed_category",
            "ecm": ecm
        })

    try:
        # ── STEP 1: Fetch row ──────────────────────────────────────────
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT gen_id, status, source_url, source_image_url, user_id
                   FROM generations WHERE gen_id = $1""",
                gen_id
            )

        if not row:
            logger.error(f"phase1_extract: gen_id={gen_id} not found in DB. Skipping.")
            return

        if row["status"] != "queued":
            logger.warning(
                f"phase1_extract: gen_id={gen_id} has status={row['status']}, "
                f"expected 'queued'. Skipping (idempotency guard)."
            )
            return

        # ── STEP 2: queued → extracting ───────────────────────────────
        async with db_pool.acquire() as conn:
            updated = await conn.execute(
                """UPDATE generations SET status = 'extracting', updated_at = NOW()
                   WHERE gen_id = $1 AND status = 'queued'""",
                gen_id
            )
        # State-guarded UPDATE: if updated == "UPDATE 0", another worker got here first
        if updated == "UPDATE 0":
            logger.warning(f"phase1_extract: gen_id={gen_id} state guard miss. Skipping.")
            return

        await _push_sse(redis_db0, gen_id, {
            "type": "status_update",
            "status": "extracting"
        })

        # ── STEP 3: Acquire image bytes ────────────────────────────────
        source_url         = row["source_url"]
        source_image_url = row["source_image_url"]

        if source_url:
            # Branch A — Firecrawl scrape
            try:
                async with asyncio.timeout(FIRECRAWL_TIMEOUT_SECONDS):
                    from firecrawl import FirecrawlApp
                    fc = FirecrawlApp(api_key=os.environ["FIRECRAWLER_API_TOKEN"])
                    # firecrawl-py is sync — run in thread to keep event loop free
                    scrape_result = await asyncio.to_thread(
                        fc.scrape,
                        source_url,
                        formats=["markdown"]
                    )
                    # firecrawl v4 returns Pydantic Document object
                    metadata = scrape_result.metadata or {}
                    og_image_url = (
                        getattr(metadata, 'og_image', None)
                        or getattr(metadata, 'ogImage', None)
                        or (metadata.get('og:image') if hasattr(metadata, 'get') else None)
                    )
                    if not og_image_url:
                        logger.error(f"phase1_extract: no og:image from Firecrawl for {source_url}")
                        await _fail("ECM-001")
                        return

                    async with httpx.AsyncClient(timeout=FIRECRAWL_TIMEOUT_SECONDS) as client:
                        img_resp = await client.get(og_image_url)
                        img_resp.raise_for_status()
                        image_bytes = img_resp.content

            except asyncio.TimeoutError:
                logger.warning(f"phase1_extract: Firecrawl timeout for gen_id={gen_id}")
                await _fail("ECM-015")
                return

        elif source_image_url:
            # Branch B — download from R2 (already <10MB, gated at L2)
            r2_obj = await asyncio.to_thread(
                r2_client.get_object,
                Bucket=os.environ["R2_BUCKET_NAME"],
                Key=source_image_url
            )
            image_bytes = r2_obj["Body"].read()

        else:
            logger.error(f"phase1_extract: gen_id={gen_id} has neither source_url nor source_image_url")
            await _fail("ECM-001")
            return

        # ── 15MB scraped image gate ────────────────────────────────────
        if len(image_bytes) > MAX_SCRAPED_IMAGE_BYTES:
            logger.warning(f"phase1_extract: gen_id={gen_id} image {len(image_bytes)} bytes > 15MB")
            await _fail("ECM-001")
            return

        # ── STEP 4: BiRefNet background removal ───────────────────────
        from PIL import Image as PILImage
        import io
        _pre_img = PILImage.open(io.BytesIO(image_bytes))
        _w, _h = _pre_img.size
        if max(_w, _h) > 1024:
            _scale = 1024 / max(_w, _h)
            _pre_img = _pre_img.resize((int(_w * _scale), int(_h * _scale)), PILImage.LANCZOS)
        _buf = io.BytesIO()
        _pre_img.save(_buf, format="PNG")
        image_bytes_resized = _buf.getvalue()

        isolated_bytes: bytes = await asyncio.to_thread(
            remove, image_bytes_resized, session=GLOBAL_BG_SESSION
        )
        isolated_pil: Image.Image = Image.open(io.BytesIO(isolated_bytes)).convert("RGBA")

        # ── STEP 5: Upload isolated PNG to R2 ─────────────────────────
        png_buffer = io.BytesIO()
        isolated_pil.save(png_buffer, format="PNG")
        png_bytes = png_buffer.getvalue()

        r2_key = f"isolated/{gen_id}/product.png"
        await asyncio.to_thread(
            r2_client.put_object,
            Bucket=os.environ["R2_BUCKET_NAME"],
            Key=r2_key,
            Body=png_bytes,
            ContentType="image/png"
        )
        r2_base_url = os.environ.get("R2_PUBLIC_URL", "")
        isolated_png_url = f"{r2_base_url}/{r2_key}"

        # ── STEP 6: Gemini Vision — product_brief ONLY ────────────────
        vision_result = await gateway.route(
            capability="vision",
            input_data={
                "image_b64": base64.b64encode(png_bytes).decode(),
                "task": "product_analysis",
                "gen_id": gen_id,
            }
        )

        # vision_result must contain these keys. If gateway raises, outer try/except handles.
        vision_data = json.loads(vision_result.text)
        product_brief = {
            "product_name":  vision_data["product_name"],
            "category":      str(vision_data["category"]).lower().strip(),
            "price_inr":     vision_data.get("price_inr"),
            "key_features":  vision_data.get("key_features", []),
            "color_palette": vision_data.get("color_palette", []),
            "shape":         str(vision_data.get("shape", "irregular")).lower().strip(),
        }

        # ── STEP 7: Confidence score (GAP-10, deterministic) ──────────
        confidence_score = _compute_confidence(isolated_pil)

        # ── STEP 8: GreenZone gate ────────────────────────────────────
        if product_brief["category"] not in GREEN_ZONE_SET:
            logger.warning(
                f"phase1_extract: gen_id={gen_id} Red Zone category={product_brief['category']}"
            )
            await _fail("ECM-001")
            return

        # ── STEP 9: Optional motion suggestion ────────────────────────
        agent_motion_suggestion = (
            _suggest_motion(product_brief["shape"])
            if confidence_score >= 0.90
            else None
        )

        # ── STEP 10: Final UPDATE → brief_ready ───────────────────────
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                """UPDATE generations SET
                     status                  = 'brief_ready',
                     isolated_png_url        = $1,
                     confidence_score        = $2,
                     product_brief           = $3::jsonb,
                     agent_motion_suggestion = $4,
                     updated_at              = NOW()
                   WHERE gen_id = $5 AND status = 'extracting'""",
                isolated_png_url,
                confidence_score,
                json.dumps(product_brief),
                agent_motion_suggestion,
                gen_id
            )

        if result == "UPDATE 0":
            logger.error(
                f"phase1_extract: gen_id={gen_id} final UPDATE missed state guard. "
                f"Row may have been modified concurrently."
            )
            return

        # ── STEP 11: SSE phase_complete ───────────────────────────────
        await _push_sse(redis_db0, gen_id, {
            "type":             "phase_complete",
            "status":           "brief_ready",
            "confidence_score": confidence_score,
        })

        logger.info(
            f"phase1_extract: gen_id={gen_id} complete. "
            f"confidence={confidence_score} category={product_brief['category']}"
        )

    except Exception as exc:
        logger.exception(f"phase1_extract: unhandled exception for gen_id={gen_id}: {exc}")
        # Do NOT re-raise — ARQ must not treat Phase 1 as a dead job
        await _fail("ECM-001")
