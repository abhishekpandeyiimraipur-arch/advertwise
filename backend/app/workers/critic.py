import json
import logging
from prometheus_client import Counter

from app.types.script import Script
from app.types.frameworks import FRAMEWORK_ANGLE_MAP

logger = logging.getLogger(__name__)

CRITIC_TOTAL = Counter(
    'aw_critic_total', 'Scripts scored by WorkerCritic'
)
CRITIC_FALLBACK_TOTAL = Counter(
    'aw_critic_fallback_total',
    'Critic fallbacks to position-based scoring'
)

class WorkerCritic:
    """
    Scores 3 framework-tagged scripts. NO filtering — all 3 passed
    downstream to SAFETY. CRITIC orders by score.
    """

    def __init__(self, gateway, prompt_catalog, gen_id):
        self.gateway = gateway
        self.prompt_catalog = prompt_catalog
        self.gen_id = gen_id

    def _normalize_scores(self, raw_scores: list[int]) -> list[int]:
        """
        Min-max rescale raw LLM scores to [60, 95].
        Preserves relative ranking. Ensures visible spread on HD-3.
        
        If all 3 scores are identical (LLM returned same score for
        all), returns [60, 77, 95] as a forced spread to maintain
        pre-selection signal.
        
        Formula: normalized = 60 + (score - min) / (max - min) * 35
        """
        min_s = min(raw_scores)
        max_s = max(raw_scores)
        
        if max_s == min_s:
            # All scores equal — return equal normalized scores.
            # Angle tie-break in process() determines ranking order.
            # 77 = midpoint of [60, 95] — honest signal to HD-3 UI.
            return [77] * len(raw_scores)
        
        normalized = []
        for s in raw_scores:
            n = 60 + (s - min_s) / (max_s - min_s) * 35
            normalized.append(round(n))
        return normalized

    async def process(self, scripts: list[Script], product_brief: dict) -> dict:
        if len(scripts) != 3:
            raise ValueError(f"CRITIC expects exactly 3 scripts, got {len(scripts)}")

        rendered = self.prompt_catalog.render(
            "script-critic", "1.0.0",
            variables={
                "scripts": [
                    {
                        "index": i + 1,
                        "framework": s.framework,
                        "framework_angle": s.framework_angle,
                        "full_text": s.full_text,
                    }
                    for i, s in enumerate(scripts)
                ],
                "product_brief": product_brief,
            }
        )

        max_tokens = rendered.model_requirements.get("max_tokens", 400) if hasattr(rendered, 'model_requirements') else 400
        assert max_tokens <= 400, f"Max tokens {max_tokens} exceeds 400 limit"

        response = await self.gateway.route(
            capability="llm",
            input_data={
                "system_prompt": getattr(rendered, 'system_prompt', ''),
                "user_prompt": getattr(rendered, 'user_prompt', ''),
                "response_format": {"type": "json_object"},
                "gen_id": self.gen_id,
            },
            max_tokens=max_tokens
        )

        try:
            result = json.loads(response.text)
            scores_data = result.get("scores", [])
            if len(scores_data) != 3:
                raise ValueError("Parsed scores length is not 3")
            
            # Sort by index to maintain original script order
            parsed_scores = sorted(scores_data, key=lambda x: x["index"])
            raw_scores = [item["score"] for item in parsed_scores]
            rationales = [item["rationale"] for item in parsed_scores]
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse CRITIC LLM output, falling back: {e}")
            CRITIC_FALLBACK_TOTAL.inc()
            raw_scores = [75, 70, 65]
            rationales = ["Fallback score", "Fallback score", "Fallback score"]

        normalized_scores = self._normalize_scores(raw_scores)

        for i in range(3):
            scripts[i].critic_score = normalized_scores[i]
            scripts[i].critic_rationale = rationales[i]

        # Tie-break priority: conversion=3, emotion=2, logic=1
        ANGLE_PRIORITY = {"conversion": 3, "emotion": 2, "logic": 1}

        ranked = sorted(
            scripts,
            key=lambda s: (
                s.critic_score,
                ANGLE_PRIORITY.get(s.framework_angle, 0)
            ),
            reverse=True
        )

        CRITIC_TOTAL.inc()

        return {
            "ranked_scripts": ranked,
            "scores_by_framework": {
                s.framework: s.critic_score
                for s in scripts
            }
        }
