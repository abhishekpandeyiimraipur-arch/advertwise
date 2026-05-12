import json
import uuid
import logging
from dataclasses import asdict

from app.types.script import Script
from app.broll.planner import (
    BRollPlanner,
    MOTION_NAMES,
    ENV_NAMES,
    COLD_START_DEFAULTS,
    DEFAULT_STYLE_FALLBACK,
)

logger = logging.getLogger(__name__)

TTS_LANGUAGE_MAP: dict[str, str] = {
    "hindi":    "sarvam",
    "hinglish": "sarvam",
    "marathi":  "sarvam",
    "punjabi":  "sarvam",
    "bengali":  "sarvam",
    "tamil":    "sarvam",
    "telugu":   "sarvam",
    "english":  "elevenlabs",
}

class WorkerStrategist:
    def __init__(self, db_pool, redis_db3=None):
        self.db = db_pool
        self.redis_db3 = redis_db3
        self.broll_planner = BRollPlanner(db_pool)

    async def _get_best_i2v_provider(
        self, redis_db3, plan_tier: str
    ) -> str:
        """
        Reads health:{capability}:{provider} from Redis DB3.
        Returns provider with highest health score.
        Falls back to 'fal_ai' if Redis is unavailable.
        """
        providers = ["fal_ai", "minimax"]
        if redis_db3 is None:
            return providers[0]
        try:
            best = providers[0]
            best_score = -1
            for p in providers:
                score_str = await redis_db3.get(f"health:i2v:{p}")
                score = int(score_str) if score_str else 70
                if score > best_score:
                    best_score = score
                    best = p
            return best
        except Exception as e:
            logger.warning(f"Redis DB3 health read failed: {e}. Using fal_ai.")
            return "fal_ai"

    async def process(self, gen_id: str) -> dict:
        async with self.db.acquire() as conn:
            gen = await conn.fetchrow(
                """SELECT safe_scripts, selected_script_id,
                          motion_archetype_id, environment_preset_id,
                          tts_language, plan_tier, chat_turns_used,
                          cogs_total, product_brief, confidence_score,
                          routed_frameworks, routing_rationale
                   FROM generations
                   WHERE gen_id = $1 AND status IN ('scripts_ready'::job_status, 'strategy_preview'::job_status)""",
                uuid.UUID(gen_id)
            )
        if gen is None:
            raise ValueError(
                f"Generation {gen_id} not found or not in scripts_ready state"
            )

        safe_scripts_list = json.loads(gen["safe_scripts"])
        idx = (gen["selected_script_id"] or 1) - 1
        idx = max(0, min(idx, len(safe_scripts_list) - 1))
        selected_script = Script(**safe_scripts_list[idx])

        product_brief = gen["product_brief"]
        if isinstance(product_brief, str):
            product_brief = json.loads(product_brief)
        category = product_brief.get("category", "packaged_food")
        motion_id = gen["motion_archetype_id"]
        env_id = gen["environment_preset_id"]
        if motion_id is None or env_id is None:
            defaults = COLD_START_DEFAULTS.get(category, DEFAULT_STYLE_FALLBACK)
            motion_id = motion_id or defaults["motion_archetype_id"]
            env_id = env_id or defaults["environment_preset_id"]

        tts_language = gen["tts_language"] or "hindi"
        tts_provider = TTS_LANGUAGE_MAP.get(tts_language, "sarvam")

        i2v_provider = await self._get_best_i2v_provider(
            self.redis_db3, gen["plan_tier"]
        )

        framework_angle = selected_script.framework_angle
        b_roll_clips = await self.broll_planner.plan(
            framework_angle=framework_angle,
            category=category,
        )
        b_roll_available = len(b_roll_clips) > 0

        chat_cost = float(gen["chat_turns_used"] or 0) * 0.08
        cogs_so_far = float(gen["cogs_total"] or 0)
        phase4_estimate = 0.50
        total_estimate = cogs_so_far + chat_cost + phase4_estimate

        strategy_card = {
            "product_summary": {
                "name": product_brief.get("product_name", ""),
                "category": category,
                "confidence": float(gen["confidence_score"] or 0),
            },
            "script_summary": {
                "text": selected_script.full_text[:120],
                "hook": selected_script.hook,
                "cta": selected_script.cta,
                "score": selected_script.critic_score,
                "framework": selected_script.framework,
                "framework_angle": selected_script.framework_angle,
            },
            "frameworks_considered": {
                "selected": gen["routed_frameworks"] or [],
                "rationale": gen["routing_rationale"] or {},
            },
            "voice": {
                "language": tts_language,
                "provider": tts_provider,
            },
            "motion": {
                "archetype_id": motion_id,
                "name": MOTION_NAMES.get(motion_id, "Drift"),
            },
            "environment": {
                "preset_id": env_id,
                "name": ENV_NAMES.get(env_id, "Clean White"),
            },
            "provider": {
                "i2v_primary": i2v_provider,
            },
            "cost_estimate": {
                "cogs_so_far_inr": round(cogs_so_far, 4),
                "chat_cost_inr": round(chat_cost, 4),
                "phase4_estimate_inr": phase4_estimate,
                "total_estimate_inr": round(total_estimate, 4),
            },
            "compliance": {
                "sgi": True,
                "c2pa": True,
                "it_rules_2026": True,
            },
            "chat_turns_used": gen["chat_turns_used"] or 0,
            "b_roll_plan": b_roll_clips,
            "b_roll_available": b_roll_available,
        }

        b_roll_json = json.dumps(b_roll_clips)
        strategy_card_json = json.dumps(strategy_card)
        async with self.db.acquire() as conn:
            updated = await conn.execute(
                """UPDATE generations
                   SET strategy_card = $2::jsonb,
                       b_roll_plan = $3::jsonb,
                       status = 'strategy_preview',
                       updated_at = NOW()
                   WHERE gen_id = $1
                     AND status IN ('scripts_ready'::job_status, 'strategy_preview'::job_status)""",
                uuid.UUID(gen_id),
                strategy_card_json,
                b_roll_json,
            )
        if updated == "UPDATE 0":
            raise ValueError(
                f"State drift: gen_id={gen_id} not in scripts_ready state"
            )

        return strategy_card
