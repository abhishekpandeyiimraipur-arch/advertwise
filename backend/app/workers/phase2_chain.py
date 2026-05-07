import asyncio
import json
import logging
import uuid
from dataclasses import asdict

from app.types.script import Script
from app.types.frameworks import SAFE_TRIO
from app.workers.copy import WorkerCopy
from app.workers.critic import WorkerCritic
from app.workers.safety import WorkerSafety
from app.core.exceptions import ProviderUnavailableError, SafetyError

logger = logging.getLogger(__name__)

async def _push_sse(redis_db0, gen_id: str, payload: dict) -> None:
    """Push SSE event to Redis. TTL 300s. Fire-and-forget."""
    key = f"sse:{gen_id}"
    await redis_db0.lpush(key, json.dumps(payload))
    await redis_db0.expire(key, 300)

async def phase2_chain(ctx: dict, gen_id: str) -> None:
    db_pool       = ctx["db_pool"]
    redis_db0     = ctx["redis_db0"]
    gateway       = ctx["gateway"]
    prompt_catalog = ctx["prompt_catalog"]

    async def _mark_failed(db_pool, gen_id: str, status: str, error_code: str, redis_db0=None) -> None:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """UPDATE generations
                   SET status = $2, error_code = $3, updated_at = NOW()
                   WHERE gen_id = $1""",
                uuid.UUID(gen_id), status, error_code
            )
        if redis_db0:
            await _push_sse(redis_db0, gen_id, {
                "type": "state_change",
                "state": status,
                "error_code": error_code,
            })

    async with db_pool.acquire() as conn:
        checkpoint = await conn.fetchrow(
            """SELECT routed_frameworks, raw_scripts,
                      critic_scores, safe_scripts, status,
                      product_brief, campaign_brief, plan_tier
               FROM generations WHERE gen_id = $1""",
            uuid.UUID(gen_id)
        )

    if not checkpoint:
        logger.warning(f"phase2_chain: gen_id={gen_id} not found. Aborting.")
        return

    # Resume-from-checkpoint logic (TDD-C1 — prevents double COGS)
    skip_router    = checkpoint["routed_frameworks"] is not None
    skip_generate  = checkpoint["raw_scripts"] is not None
    skip_critic    = checkpoint["critic_scores"] is not None
    already_done   = checkpoint["safe_scripts"] is not None

    if already_done:
        # Job already completed — idempotent return
        logger.info(f"phase2_chain: gen_id={gen_id} already complete.")
        return

    product_brief = checkpoint["product_brief"]
    campaign_brief = checkpoint["campaign_brief"]

    # STAGE 1 — Framework Router
    if not skip_router:
        try:
            selected, rationale, fallback_triggered = await WorkerCopy(gateway, prompt_catalog, gen_id).framework_router(product_brief, campaign_brief)
        except ProviderUnavailableError:
            await _mark_failed(db_pool, gen_id, "failed_generation", "ECM-013", redis_db0)
            return
        except ValueError:
            selected = list(SAFE_TRIO)
            rationale = {}
            fallback_triggered = True

        async with db_pool.acquire() as conn:
            updated = await conn.execute(
                """UPDATE generations
                   SET routed_frameworks=$2, routing_rationale=$3::jsonb,
                       fallback_triggered=$4, updated_at=NOW()
                   WHERE gen_id=$1 AND status='scripting'""",
                uuid.UUID(gen_id),
                [f.value for f in selected],
                json.dumps(rationale),
                fallback_triggered
            )
        if updated == "UPDATE 0":
            logger.warning(f"phase2_chain: gen_id={gen_id} state drifted at routing. Aborting.")
            return

        await _push_sse(redis_db0, gen_id, {
            "type": "state_change", "state": "scripting",
            "stage": "routing_complete"
        })
    else:
        from app.schemas.enums import AdFramework
        selected = [AdFramework(f) for f in checkpoint["routed_frameworks"]]

    # STAGE 2 — Generate per framework
    if not skip_generate:
        try:
            scripts = await WorkerCopy(gateway, prompt_catalog, gen_id).generate_per_framework(product_brief, campaign_brief, selected)
        except ProviderUnavailableError:
            await _mark_failed(db_pool, gen_id, "failed_generation", "ECM-013", redis_db0)
            return
        
        raw_scripts_json = json.dumps([asdict(s) for s in scripts])

        async with db_pool.acquire() as conn:
            updated = await conn.execute(
                """UPDATE generations
                   SET raw_scripts=$2::jsonb, status='critiquing', updated_at=NOW()
                   WHERE gen_id=$1 AND status='scripting'""",
                uuid.UUID(gen_id), raw_scripts_json
            )
        if updated == "UPDATE 0":
            logger.warning(f"phase2_chain: gen_id={gen_id} state drifted at generate. Aborting.")
            return

        await _push_sse(redis_db0, gen_id, {
            "type": "state_change", "state": "critiquing"
        })
    else:
        scripts = [Script(**s) for s in json.loads(checkpoint["raw_scripts"])]

    # STAGE 3 — Critic
    if not skip_critic:
        critic_result = await WorkerCritic(gateway, prompt_catalog, gen_id).process(scripts, product_brief)
        ranked_scripts = critic_result["ranked_scripts"]
        critic_scores_json = json.dumps(critic_result["scores_by_framework"])
        
        async with db_pool.acquire() as conn:
            updated = await conn.execute(
                """UPDATE generations
                   SET critic_scores=$2::jsonb, status='safety_checking',
                       updated_at=NOW()
                   WHERE gen_id=$1 AND status='critiquing'""",
                uuid.UUID(gen_id), critic_scores_json
            )
        if updated == "UPDATE 0":
            logger.warning(f"phase2_chain: gen_id={gen_id} state drifted at critic. Aborting.")
            return

        await _push_sse(redis_db0, gen_id, {
            "type": "state_change", "state": "safety_checking"
        })
    else:
        # Reconstruct ranked_scripts
        scores = json.loads(checkpoint["critic_scores"])
        # In WorkerCritic, process() returns `scores_by_framework` as a dict
        
        ranked_scripts = []
        for script in scripts:
            if script.framework in scores:
                script.critic_score = scores[script.framework]
            ranked_scripts.append(script)
            
        ranked_scripts.sort(key=lambda s: s.critic_score or 0, reverse=True)


    # STAGE 4 — Safety
    try:
        safety_result = await WorkerSafety(gateway, gen_id).process(ranked_scripts)
    except SafetyError:
        try:
            new_scripts = await WorkerCopy(gateway, prompt_catalog, gen_id).generate_per_framework(product_brief, campaign_brief, list(SAFE_TRIO))
            critic_retry = await WorkerCritic(gateway, prompt_catalog, gen_id).process(new_scripts, product_brief)
            safety_result = await WorkerSafety(gateway, gen_id).process(critic_retry["ranked_scripts"])
        except (SafetyError, ProviderUnavailableError):
            await _mark_failed(db_pool, gen_id, "failed_safety", "ECM-003", redis_db0)
            return
            
    safe_scripts_json = json.dumps([asdict(s) for s in safety_result["safe_scripts"]])
    safety_flags_json = json.dumps(safety_result["safety_flags"])

    async with db_pool.acquire() as conn:
        updated = await conn.execute(
            """UPDATE generations
               SET safe_scripts=$2::jsonb,
                   safety_flags=$3::jsonb,
                   scripts_available=$4,
                   selected_script_id=1,
                   status='scripts_ready',
                   updated_at=NOW()
               WHERE gen_id=$1 AND status='safety_checking'""",
            uuid.UUID(gen_id), safe_scripts_json, safety_flags_json, safety_result["scripts_available"]
        )
        
    if updated == "UPDATE 0":
        logger.warning(f"phase2_chain: gen_id={gen_id} state drifted at safety. Aborting.")
        return

    await _push_sse(redis_db0, gen_id, {
        "type": "state_change",
        "state": "scripts_ready",
        "scripts_available": safety_result["scripts_available"],
        "rejected_frameworks": safety_result["rejected_frameworks"]
    })
