"""
phase4_coordinator — ARQ job for the Phase 4 render pipeline.
[TDD-WORKERS]-J

State path:
  funds_locked → rendering → reflecting → composing → preview_ready

Orchestrates: TTS + I2V (attempt 1) + REFLECT → (attempt 2 if needed)
              + COMPOSE → preview_ready.

STOPS at preview_ready. NEVER enqueues the export job.
CI check_banned_patterns.py enforces the no-arq.enqueue constraint.
"""
import asyncio
import json
import logging
import os
from decimal import Decimal

from app.workers.tts import WorkerTTS
from app.workers.i2v import WorkerI2V
from app.workers.reflect import WorkerReflect
from app.workers.compose import WorkerCompose
from app.core.exceptions import (
    ReflectError, ComposeError, ComposeDurationError,
    TTSError, I2VError
)

logger = logging.getLogger(__name__)


# ── SSE helper (canonical pattern — matches phase2_chain) ─────────

async def _push_sse(redis_db0, gen_id: str, payload: dict) -> None:
    """Fire-and-forget SSE event via Redis list. TTL 300s."""
    try:
        key = f"sse:{gen_id}"
        await redis_db0.lpush(key, json.dumps(payload))
        await redis_db0.expire(key, 300)
    except Exception as e:
        logger.warning(f"SSE push failed gen={gen_id}: {e}")


# ── FSM transition helper ─────────────────────────────────────────

async def _transition(
    conn, gen_id: str, from_status: str, to_status: str
) -> bool:
    """
    Atomic FSM transition. Returns True if transition succeeded.
    Returns False if gen is no longer in expected state (state drift).
    Never raises — caller decides how to handle False.
    """
    result = await conn.execute(
        """UPDATE generations
           SET status = $3, updated_at = NOW()
           WHERE gen_id = $1 AND status = $2""",
        gen_id, from_status, to_status,
    )
    return result != "UPDATE 0"


# ── Main coordinator ──────────────────────────────────────────────

async def phase4_coordinator(ctx: dict, gen_id: str) -> None:
    """
    ARQ job. Orchestrates Phase 4 pipeline.
    Stops at preview_ready. Never enqueues the export job.

    State path:
    funds_locked → rendering → reflecting → composing → preview_ready

    ctx keys used:
        ctx["db_pool"]   — asyncpg pool
        ctx["r2_client"] — boto3 S3 client for R2
        ctx["gateway"]   — ModelGateway (StubGateway in dev)
        ctx["redis_db0"] — SSE push
        ctx["redis_mgr"] — acquire redis_db2 for CostGuard
    """
    db_pool   = ctx["db_pool"]
    redis_db0 = ctx.get("redis_db0")
    redis_mgr = ctx.get("redis_mgr")
    try:
        r2_client = ctx["r2_client"]
        gateway   = ctx["gateway"]
        redis_db0 = ctx["redis_db0"]
    
        # ── Step 1: Read generation row ──────────────────────────────
        async with db_pool.acquire() as conn:
            gen = await conn.fetchrow(
                """SELECT g.gen_id, g.isolated_png_url, g.refined_script,
                          g.safe_scripts, g.selected_script_id,
                          g.motion_archetype_id, g.environment_preset_id,
                          g.tts_language, g.product_brief, g.plan_tier,
                          g.b_roll_plan, g.strategy_card,
                          u.brand_profile
                   FROM generations g
                   JOIN users u ON u.user_id = g.user_id
                   WHERE g.gen_id = $1 AND g.status = 'funds_locked'""",
                gen_id,
            )
    
        if not gen:
            logger.warning(
                f"phase4_coordinator: gen={gen_id} not in "
                f"funds_locked state — skipping (idempotent)"
            )
            return
    
        # ── Step 2: Transition funds_locked → rendering ───────────────
        async with db_pool.acquire() as conn:
            ok = await _transition(
                conn, gen_id, "funds_locked", "rendering"
            )
        if not ok:
            logger.warning(
                f"phase4_coordinator: state drift gen={gen_id} "
                f"could not transition to rendering"
            )
            return
    
        await _push_sse(redis_db0, gen_id, {
            "type": "state_change",
            "state": "rendering",
        })
        logger.info(f"phase4_coordinator: rendering gen={gen_id}")
    
        # ── Step 3: Resolve script text ──────────────────────────────
        # Use refined_script if available (copilot-edited).
        # Fall back to the selected safe_script.
        safe_scripts = json.loads(gen["safe_scripts"] or "[]")
        selected_idx = (gen["selected_script_id"] or 1) - 1
        selected_idx = max(0, min(selected_idx, len(safe_scripts) - 1))
    
        if gen["refined_script"]:
            script_data = json.loads(gen["refined_script"])
        elif safe_scripts:
            script_data = safe_scripts[selected_idx]
        else:
            raise ValueError(f"No script available for gen={gen_id}")
    
        script_text  = script_data.get("full_text", "")
        tts_language = gen["tts_language"] or "hindi"
    
        # ── Step 4: Parse product brief ──────────────────────────────
        product_brief         = json.loads(gen["product_brief"] or "{}")
        category              = product_brief.get("category", "packaged_food")
        benefit               = product_brief.get("benefit", "natural")
        framework             = product_brief.get("framework_angle", "emotion")
        plan_tier             = gen["plan_tier"] or "starter"
        b_roll_plan           = json.loads(gen["b_roll_plan"] or "[]")
        motion_archetype_id   = gen["motion_archetype_id"] or 2
        environment_preset_id = gen["environment_preset_id"] or 1
        strategy_card         = json.loads(gen["strategy_card"] or "{}")
        brand_profile         = json.loads(gen["brand_profile"] or "{}")
        isolated_png_url      = gen["isolated_png_url"]
    
        # Derive R2 key from public URL for WorkerReflect.
        # Reflect downloads via credentialed boto3 — needs key, not URL.
        r2_public_url = os.environ.get(
            "R2_PUBLIC_URL",
            "https://pub-dfacf0a5eece46e4ac8e5aaaf5da5368.r2.dev"
        )
        isolated_png_r2_key = isolated_png_url.replace(
            f"{r2_public_url}/", ""
        )
    
        # ── Step 5: PARALLEL — TTS + LLM prompt preflight ────────────
        # TTS converts script to voiceover audio.
        # LLM preflight builds an optimized cinematic prompt for Fal.ai.
        tts_worker = WorkerTTS(gateway=gateway, r2_client=r2_client)
    
        tts_task = asyncio.create_task(
            tts_worker.process(
                gen_id=gen_id,
                script_text=script_text,
                language=tts_language,
                context={
                    "framework_angle": framework,
                    "category": category,
                },
            )
        )
    
        preflight_task = asyncio.create_task(
            gateway.route(
                capability="llm",
                input_data={
                    "system_prompt": (
                        "You are a master cinematographer. "
                        "Convert the inputs into a highly dense, "
                        "comma-separated camera and lighting prompt "
                        "optimized for AI video models. Max 30 words."
                    ),
                    "user_prompt": (
                        f"Product: {product_brief.get('product_name', '')}. "
                        f"Category: {category}. "
                        f"Benefit: {benefit}. "
                        f"Motion: {motion_archetype_id}."
                    ),
                    "gen_id": gen_id,
                },
            )
        )
    
        try:
            tts_r2_key, preflight_resp = await asyncio.gather(
                tts_task, preflight_task
            )
            optimized_prompt = preflight_resp.text or ""
            logger.info(
                f"phase4_coordinator: TTS+preflight done gen={gen_id} "
                f"tts_key={tts_r2_key}"
            )
        except Exception as e:
            logger.error(
                f"phase4_coordinator: TTS/preflight failed "
                f"gen={gen_id}: {e}"
            )
            raise
    
        # ── Step 6: I2V Attempt 1 ────────────────────────────────────
        i2v_worker     = WorkerI2V(gateway=gateway, r2_client=r2_client)
        reflect_worker = WorkerReflect(gateway=gateway, r2_client=r2_client)
    
        i2v_key_1 = await i2v_worker.process(
            gen_id=gen_id,
            isolated_png_url=isolated_png_url,
            motion_archetype_id=motion_archetype_id,
            environment_preset_id=environment_preset_id,
            optimized_prompt=optimized_prompt,
            attempt=1,
        )
        logger.info(
            f"phase4_coordinator: I2V attempt 1 done "
            f"gen={gen_id} key={i2v_key_1}"
        )
    
        # ── Step 7: Transition rendering → reflecting ─────────────────
        async with db_pool.acquire() as conn:
            await _transition(conn, gen_id, "rendering", "reflecting")
    
        await _push_sse(redis_db0, gen_id, {
            "type": "state_change",
            "state": "reflecting",
        })
    
        # ── Step 8: REFLECT — sequential early-exit ───────────────────
        i2v_candidates = [i2v_key_1]
        selected_i2v   = i2v_key_1  # fallback if both attempts fail
    
        try:
            selected_i2v = await reflect_worker.process(
                gen_id=gen_id,
                candidate_r2_keys=[i2v_key_1],
                source_png_r2_key=isolated_png_r2_key,
            )
            logger.info(
                f"phase4_coordinator: REFLECT passed attempt 1 "
                f"gen={gen_id}"
            )
    
        except ReflectError:
            # Attempt 1 failed quality gates — run attempt 2
            logger.warning(
                f"phase4_coordinator: REFLECT failed attempt 1 "
                f"gen={gen_id} — running I2V attempt 2"
            )
    
            i2v_key_2 = await i2v_worker.process(
                gen_id=gen_id,
                isolated_png_url=isolated_png_url,
                motion_archetype_id=motion_archetype_id,
                environment_preset_id=environment_preset_id,
                optimized_prompt=optimized_prompt,
                attempt=2,
            )
            i2v_candidates.append(i2v_key_2)
    
            try:
                selected_i2v = await reflect_worker.process(
                    gen_id=gen_id,
                    candidate_r2_keys=[i2v_key_2],
                    source_png_r2_key=isolated_png_r2_key,
                )
                logger.info(
                    f"phase4_coordinator: REFLECT passed attempt 2 "
                    f"gen={gen_id}"
                )
            except ReflectError:
                # Both attempts failed quality gates.
                # Use attempt 2 directly — better than failing entire gen.
                selected_i2v = i2v_key_2
                logger.warning(
                    f"phase4_coordinator: both REFLECT attempts failed "
                    f"gen={gen_id} — using attempt 2 as fallback"
                )
    
        # ── Step 9: Persist I2V results ───────────────────────────────
        async with db_pool.acquire() as conn:
            await conn.execute(
                """UPDATE generations
                   SET tts_audio_url    = $2,
                       i2v_candidates   = $3::jsonb,
                       selected_i2v_url = $4,
                       updated_at       = NOW()
                   WHERE gen_id = $1""",
                gen_id,
                tts_r2_key,
                json.dumps(i2v_candidates),
                selected_i2v,
            )
    
        # ── Step 10: Transition reflecting → composing ────────────────
        async with db_pool.acquire() as conn:
            await _transition(conn, gen_id, "reflecting", "composing")
    
        await _push_sse(redis_db0, gen_id, {
            "type": "state_change",
            "state": "composing",
        })
        logger.info(
            f"phase4_coordinator: composing gen={gen_id} "
            f"selected_i2v={selected_i2v}"
        )
    
        # ── Step 11: COMPOSE ──────────────────────────────────────────
        compose_worker = WorkerCompose(r2_client=r2_client)
    
        preview_r2_key = await compose_worker.process(
            gen_id=gen_id,
            i2v_r2_key=selected_i2v,
            tts_r2_key=tts_r2_key,
            strategy_card=strategy_card,
            b_roll_plan=b_roll_plan,
            brand_profile=brand_profile,
            plan_tier=plan_tier,
        )
        logger.info(
            f"phase4_coordinator: compose done gen={gen_id} "
            f"preview={preview_r2_key}"
        )
    
        # ── Step 12: Persist preview + transition → preview_ready ─────
        preview_public_url = f"{r2_public_url}/{preview_r2_key}"
    
        async with db_pool.acquire() as conn:
            await conn.execute(
                """UPDATE generations
                   SET preview_url = $2,
                       status      = 'preview_ready',
                       updated_at  = NOW()
                   WHERE gen_id = $1""",
                gen_id,
                preview_public_url,
            )
    
        # ── Step 13: Post-hoc COGS check (best-effort, non-blocking) ──
        try:
            from app.services.cost_guard import CostGuard
            redis_mgr = ctx.get("redis_mgr")
            if redis_mgr and hasattr(redis_mgr, "db2"):
                cost_guard = CostGuard(
                    redis_db2=redis_mgr.db2,
                    db_pool=db_pool,
                )
                await cost_guard.check_post_hoc(gen_id)
        except Exception as e:
            # Non-blocking — never fail the generation over COGS check
            logger.warning(
                f"phase4_coordinator: cost_guard check failed "
                f"gen={gen_id}: {e}"
            )
    
        # ── Step 14: SSE push preview_ready ──────────────────────────
        await _push_sse(redis_db0, gen_id, {
            "type":        "state_change",
            "state":       "preview_ready",
            "preview_url": preview_public_url,
        })
    
        logger.info(
            f"phase4_coordinator: DONE gen={gen_id} "
            f"preview_url={preview_public_url}"
        )
    except Exception as e:
        import uuid, json
        logger.error(f"phase4_coordinator FAILED gen={gen_id}: {e}", exc_info=True)
        # DLQ: refund + failed_render + SSE
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT user_id FROM generations WHERE gen_id=$1",
                    uuid.UUID(gen_id)
                )
            if row:
                user_id = str(row["user_id"])
                if redis_mgr:
                    await redis_mgr.execute_wallet_refund(user_id, gen_id)
                async with db_pool.acquire() as conn:
                    await conn.execute(
                        """UPDATE generations SET status='failed_render',
                           error_code='ECM-013', updated_at=NOW()
                           WHERE gen_id=$1 AND status NOT IN
                           ('failed_render','export_ready')""",
                        uuid.UUID(gen_id)
                    )
                    await conn.execute(
                        """INSERT INTO audit_log (user_id, gen_id, action, payload)
                           VALUES ($1, $2, 'dlq_failure', $3::jsonb)""",
                        uuid.UUID(user_id), uuid.UUID(gen_id),
                        json.dumps({"worker": "phase4_coordinator", "error": str(e)})
                    )
                if redis_db0:
                    await redis_db0.lpush(f"sse:{gen_id}", json.dumps({
                        "type": "state_change", "state": "failed_render",
                        "error_code": "ECM-013"
                    }))
                    await redis_db0.expire(f"sse:{gen_id}", 300)
        except Exception as inner_e:
            logger.error(f"DLQ handler failed gen={gen_id}: {inner_e}", exc_info=True)
        raise
