import asyncio
import json
from prometheus_client import Counter

from app.schemas.enums import AdFramework
from app.core.exceptions import ProviderUnavailableError
from app.types.script import Script  # shared type — see app/types/script.py
from app.types.frameworks import SAFE_TRIO, FRAMEWORK_ANGLE_MAP

TOKEN_BUDGET: dict[str, int] = {
    "framework_router": 600,
    "generate_per_framework": 500,
    "refine": 400,
}

FRAMEWORK_COPY_TOTAL = Counter(
    'aw_framework_copy_total', 'Scripts generated', ['framework'])
COPY_REFINE_TOTAL    = Counter(
    'aw_copy_refine_total', 'Refinement turns executed')
COPY_FALLBACK_TOTAL  = Counter(
    'aw_copy_fallback_total', 'Router fallback to SAFE_TRIO')

class WorkerCopy:
    def __init__(self, gateway, prompt_catalog, gen_id):
        self.gateway = gateway
        self.prompt_catalog = prompt_catalog
        self.gen_id = gen_id

    async def _generate_one(
        self, product_brief: dict, campaign_brief: dict, framework: AdFramework
    ) -> Script:
        rendered = self.prompt_catalog.render(
            "script-generate", 
            "1.0.0", 
            variables={
                "product_brief": product_brief,
                "campaign_brief": campaign_brief,
                "framework": framework.value,
            }
        )
        
        max_tokens = rendered.model_requirements.get("max_tokens", 0)
        if max_tokens > TOKEN_BUDGET["generate_per_framework"]:
            raise ValueError(
                f"Token budget exceeded: {max_tokens} > {TOKEN_BUDGET['generate_per_framework']}"
            )
            
        response = await self.gateway.route(
            capability="llm",
            input_data={
                "system_prompt": rendered.system_prompt,
                "user_prompt": rendered.user_prompt,
                "response_format": {"type": "json_object"},
                "gen_id": self.gen_id,
            },
            max_tokens=max_tokens
        )
        
        output = json.loads(response.text)
        return Script(
            hook=output["hook"],
            body=output["body"],
            cta=output["cta"],
            full_text=output["full_text"],
            word_count=output.get("word_count",
                                  len(output["full_text"].split())),
            language_mix=output.get("language_mix", "hinglish"),
            framework=output["framework"],
            framework_angle=output.get("framework_angle", "logic"),
            framework_rationale=output.get("framework_rationale", ""),
            evidence_note=output.get("evidence_note", ""),
            suggested_tone=output.get("suggested_tone", "neutral"),
        )

    async def framework_router(self, product_brief: dict, campaign_brief: dict) -> tuple:
        # Detect weak evidence
        confidence_score = product_brief.get("confidence_score", 1.0)
        evidence_strength = product_brief.get("evidence_assessment", {}).get("strength", "strong")
        
        if confidence_score < 0.4 or evidence_strength == "weak":
            COPY_FALLBACK_TOTAL.inc()
            return list(SAFE_TRIO), {}, True

        rendered = self.prompt_catalog.render(
            "framework-router", 
            "1.0.0", 
            variables={"product_brief": product_brief, "campaign_brief": campaign_brief}
        )
        
        max_tokens = rendered.model_requirements.get("max_tokens", 0)
        if max_tokens > TOKEN_BUDGET["framework_router"]:
            raise ValueError(
                f"Token budget exceeded: {max_tokens} > {TOKEN_BUDGET['framework_router']}"
            )

        response = await self.gateway.route(
            capability="llm",
            input_data={
                "system_prompt": rendered.system_prompt,
                "user_prompt": rendered.user_prompt,
                "response_format": {"type": "json_object"},
                "gen_id": self.gen_id,
            },
            max_tokens=max_tokens
        )

        output = json.loads(response.text)
        raw_frameworks = output.get("selected", [])
        rationale = output.get("rationale", {})
        fallback_triggered = output.get("fallback_triggered", False)

        try:
            selected = [AdFramework(f) for f in raw_frameworks]
        except ValueError as e:
            raise ValueError(
                f"Router returned invalid AdFramework value: {e}. "
                f"Raw output: {raw_frameworks}"
            )

        if len(selected) != 3:
            raise ValueError(
                f"Router must return exactly 3 frameworks, got {len(selected)}"
            )

        if len(set(selected)) != 3:
            raise ValueError(
                f"Router returned duplicate frameworks: {selected}"
            )
            
        if fallback_triggered:
            COPY_FALLBACK_TOTAL.inc()

        return selected, rationale, fallback_triggered

    async def generate_per_framework(
        self,
        product_brief: dict,
        campaign_brief: dict,
        frameworks: list[AdFramework],
    ) -> list[Script]:

        # First attempt — all 3 in parallel
        results = await asyncio.gather(
            *[self._generate_one(product_brief, campaign_brief, fw)
              for fw in frameworks],
            return_exceptions=True,
        )

        # Identify failed slots
        scripts: list[Script | None] = []
        retry_indices: list[int] = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                retry_indices.append(i)
                scripts.append(None)
            else:
                scripts.append(result)

        # Retry failed slots once individually
        if retry_indices:
            retry_results = await asyncio.gather(
                *[self._generate_one(
                    product_brief, campaign_brief, frameworks[i])
                  for i in retry_indices],
                return_exceptions=True,
            )
            for slot, retry_result in zip(retry_indices, retry_results):
                if isinstance(retry_result, Exception):
                    # Still failing after retry → raise to trigger
                    # SAFE_TRIO reset in phase2_chain
                    raise ProviderUnavailableError(
                        f"Framework {frameworks[slot]} failed after retry: "
                        f"{retry_result}"
                    )
                scripts[slot] = retry_result

        # Increment counter per framework
        for script in scripts:
            FRAMEWORK_COPY_TOTAL.labels(
                framework=script.framework).inc()

        return scripts

    async def refine(
        self, current_script: dict, instruction: str, product_brief: dict, language: str
    ) -> Script:
        rendered = self.prompt_catalog.render(
            "script-refine", 
            "1.0.0", 
            variables={
                "current_script": current_script,
                "user_instruction": instruction,
                "product_brief": product_brief,
                "language": language,
            }
        )
        
        max_tokens = rendered.model_requirements.get("max_tokens", 0)
        if max_tokens > TOKEN_BUDGET["refine"]:
            raise ValueError(
                f"Token budget exceeded: {max_tokens} > {TOKEN_BUDGET['refine']}"
            )

        response = await self.gateway.route(
            capability="llm",
            input_data={
                "system_prompt": rendered.system_prompt,
                "user_prompt": rendered.user_prompt,
                "response_format": {"type": "json_object"},
                "gen_id": self.gen_id,
            },
            max_tokens=max_tokens
        )
        
        output = json.loads(response.text)
        
        # Merge updated content into a Script object
        updated_script = Script(
            framework=current_script.get("framework", "pas_micro"),
            framework_angle=current_script.get("framework_angle", "logic"),
            full_text=output.get("full_text", ""),
            evidence_note=current_script.get("evidence_note", ""),
            suggested_tone=current_script.get("suggested_tone", ""),
            critic_score=current_script.get("critic_score", 0),
            critic_rationale=current_script.get("critic_rationale", "")
        )
        
        COPY_REFINE_TOTAL.inc()
        return updated_script
