"""
L5: ModelGateway — Phase 1 Vision implementation.
Primary: Together AI (Llama Vision) — free tier
Fallback: Gemini 2.0 Flash — paid tier
Fallback 2: OpenAI GPT-4o — most reliable
"""
import os
import base64
import json
import logging
import asyncio
import httpx
from PIL import Image
import io
import time
from dataclasses import dataclass
from decimal import Decimal
from app.core.exceptions import ProviderUnavailableError

logger = logging.getLogger(__name__)

VISION_PROMPT = """You are a product analyst for Indian D2C brands.
Analyze this product image and return a JSON object with exactly these fields:
{
  "product_name": "string — specific product name",
  "category": "one of: d2c_beauty, packaged_food, hard_accessories, electronics, home_kitchen",
  "price_inr": null or number — estimated Indian retail price,
  "key_features": ["list", "of", "3-5", "key", "features"],
  "color_palette": ["#hex1", "#hex2", "#hex3"],
  "shape": "one of: bottle, box, pouch, tube, jar, can, irregular"
}
Return ONLY the JSON object. No markdown, no explanation, no backticks."""


def _parse_json_response(raw: str) -> dict:
    clean = raw.strip()
    if clean.startswith("```"):
        parts = clean.split("```")
        clean = parts[1]
        if clean.startswith("json"):
            clean = clean[4:]
    return json.loads(clean.strip())

@dataclass
class GatewayResponse:
    """Uniform response contract for all gateway capabilities.
    Callers use .text for LLM/moderation output.
    Future callers will use .audio_bytes (TTS) and .video_url (I2V).
    """
    text: str = ""
    cost_inr: Decimal = Decimal("0.00")
    model_used: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    audio_bytes: bytes = None
    video_url: str = None
    embedding: list = None

# Cost in INR per 1000 tokens (input_rate, output_rate)
# Rates as of May 2026 — update here only, never inline
COST_RATES: dict[str, tuple] = {
    "deepseek-v3":        (Decimal("0.022"), Decimal("0.090")),
    "groq-llama-3.3-70b": (Decimal("0.000"), Decimal("0.000")),
    "together-llama-3.3": (Decimal("0.018"), Decimal("0.060")),
    "together-llama-guard-3": (Decimal("0.010"), Decimal("0.010")),
    "groq-llama-guard-3": (Decimal("0.000"), Decimal("0.000")),
}

# Provider pool order defines fallback priority (index 0 = primary)
PROVIDER_POOLS: dict[str, list[str]] = {
    "llm":        ["deepseek-v3", "groq-llama-3.3-70b", "together-llama-3.3"],
    "moderation": ["together-llama-guard-3", "groq-llama-guard-3"],
}

class ModelGateway:
    def __init__(self, redis_client=None):
        self.together_key = os.environ.get("TOGETHER_API_KEY", "")
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")
        self.openai_key = os.environ.get("OPEN_AI_API_KEY", "")
        self.redis_client = redis_client
        self.last_call_cost = Decimal("0.00")
        self.last_model_used = ""

    def _calculate_cost(
        self, model: str, tokens_in: int, tokens_out: int
    ) -> Decimal:
        """Calculate INR cost using COST_RATES.
        Returns Decimal("0.00") for unknown models (e.g., free tier).
        """
        rates = COST_RATES.get(model, (Decimal("0.00"), Decimal("0.00")))
        input_cost  = rates[0] * Decimal(tokens_in)  / Decimal(1000)
        output_cost = rates[1] * Decimal(tokens_out) / Decimal(1000)
        return (input_cost + output_cost).quantize(Decimal("0.000001"))

    async def _record_health(
        self, provider: str, capability: str, success: bool
    ) -> None:
        """Write provider health score to Redis DB3.
        Health is 0-100. Success: +10 (capped at 100).
        Failure: -30 (floored at 0).
        STRATEGIST reads health:{capability}:{provider} from Redis DB3.
        No-ops silently if redis_client is None (test/dev mode).
        """
        if self.redis_client is None:
            return
        key = f"health:{capability}:{provider}"
        try:
            current = int(await self.redis_client.get(key) or 70)
            if success:
                new_score = min(current + 10, 100)
            else:
                new_score = max(current - 30, 0)
            await self.redis_client.set(key, new_score, ex=3600)
        except Exception as e:
            logger.warning(f"Health score update failed for {provider}: {e}")

    async def route(
        self,
        capability: str,
        input_data: dict,
        max_tokens: int = 1024,
    ) -> GatewayResponse:
        """Single entry point for all AI provider calls.
        Dispatches by capability. Returns GatewayResponse.
        Updates self.last_call_cost and self.last_model_used
        after every successful call.
        """
        start = time.monotonic()

        if capability == "vision":
            # Vision returns a dict (existing contract).
            # Wrap it in GatewayResponse for uniform interface.
            raw = await self._vision_with_fallback(input_data)
            response = GatewayResponse(
                text=json.dumps(raw),
                model_used="vision-pool",
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        elif capability == "llm":
            response = await self._route_llm(input_data, max_tokens)
            response.latency_ms = int((time.monotonic() - start) * 1000)

        elif capability == "moderation":
            response = await self._route_moderation(input_data)
            response.latency_ms = int((time.monotonic() - start) * 1000)

        elif capability in ("tts", "i2v", "embedding"):
            raise NotImplementedError(
                f"Capability '{capability}' is not yet implemented. "
                f"Scheduled for Micro-phase 4 (tts, i2v) and "
                f"Micro-phase 5 (embedding)."
            )

        else:
            raise ValueError(f"Unknown gateway capability: '{capability}'")

        # Update instance state for TDD-required last_call_cost pattern.
        # WARNING: These are unsafe under concurrent requests (race condition).
        # Callers should prefer response.cost_inr over gateway.last_call_cost
        # when both are available. This pattern exists for TDD-API-C compliance.
        self.last_call_cost = response.cost_inr
        self.last_model_used = response.model_used

        return response

    async def _route_llm(self, input_data: dict, max_tokens: int) -> GatewayResponse:
        providers = PROVIDER_POOLS["llm"]
        capability = "llm"

        # Build ordered try-list: healthy first, all if none healthy
        if self.redis_client:
            try:
                healthy, degraded = [], []
                for p in providers:
                    h = int(await self.redis_client.get(
                        f"health:{capability}:{p}") or 70)
                    (healthy if h >= 20 else degraded).append(p)
                ordered = healthy if healthy else providers
            except Exception:
                ordered = providers
        else:
            ordered = providers

        last_error = None
        for provider in ordered:
            try:
                if provider == "deepseek-v3":
                    response = await self._call_deepseek_llm(input_data, max_tokens)
                elif provider == "groq-llama-3.3-70b":
                    response = await self._call_groq_llm(input_data, max_tokens)
                elif provider == "together-llama-3.3":
                    response = await self._call_together_llm(input_data, max_tokens)
                else:
                    raise ValueError(f"Unknown LLM provider: {provider}")
                
                await self._record_health(provider, capability, True)
                return response
            except Exception as e:
                logger.warning(f"{capability} provider {provider} failed: {e}")
                last_error = e
                await self._record_health(provider, capability, False)
                continue
                
        raise ProviderUnavailableError(f"All {capability} providers failed. Last error: {last_error}")

    async def _call_deepseek_llm(self, input_data: dict, max_tokens: int) -> GatewayResponse:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": input_data.get("system_prompt", "")},
                {"role": "user", "content": input_data.get("user_prompt", "")},
            ],
            "response_format": input_data.get("response_format", {"type": "text"}),
            "max_tokens": max_tokens,
            "temperature": 0.3
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            tokens_in = usage.get("prompt_tokens", 0)
            tokens_out = usage.get("completion_tokens", 0)
            cost = self._calculate_cost("deepseek-v3", tokens_in, tokens_out)
            
            return GatewayResponse(
                text=text,
                cost_inr=cost,
                model_used="deepseek-v3",
                tokens_in=tokens_in,
                tokens_out=tokens_out
            )

    async def _call_groq_llm(self, input_data: dict, max_tokens: int) -> GatewayResponse:
        api_key = os.environ.get("GROQ_API_KEY", "")
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": input_data.get("system_prompt", "")},
                {"role": "user", "content": input_data.get("user_prompt", "")},
            ],
            "response_format": input_data.get("response_format", {"type": "text"}),
            "max_tokens": max_tokens,
            "temperature": 0.3
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            tokens_in = usage.get("prompt_tokens", 0)
            tokens_out = usage.get("completion_tokens", 0)
            cost = self._calculate_cost("groq-llama-3.3-70b", tokens_in, tokens_out)
            
            return GatewayResponse(
                text=text,
                cost_inr=cost,
                model_used="groq-llama-3.3-70b",
                tokens_in=tokens_in,
                tokens_out=tokens_out
            )

    async def _call_together_llm(self, input_data: dict, max_tokens: int) -> GatewayResponse:
        api_key = self.together_key
        payload = {
            "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "messages": [
                {"role": "system", "content": input_data.get("system_prompt", "")},
                {"role": "user", "content": input_data.get("user_prompt", "")},
            ],
            "response_format": input_data.get("response_format", {"type": "text"}),
            "max_tokens": max_tokens,
            "temperature": 0.3
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.together.xyz/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            tokens_in = usage.get("prompt_tokens", 0)
            tokens_out = usage.get("completion_tokens", 0)
            cost = self._calculate_cost("together-llama-3.3", tokens_in, tokens_out)
            
            return GatewayResponse(
                text=text,
                cost_inr=cost,
                model_used="together-llama-3.3",
                tokens_in=tokens_in,
                tokens_out=tokens_out
            )

    async def _route_moderation(self, input_data: dict) -> GatewayResponse:
        providers = PROVIDER_POOLS["moderation"]
        capability = "moderation"
        
        # Build ordered try-list: healthy first, all if none healthy
        if self.redis_client:
            try:
                healthy, degraded = [], []
                for p in providers:
                    h = int(await self.redis_client.get(
                        f"health:{capability}:{p}") or 70)
                    (healthy if h >= 20 else degraded).append(p)
                ordered = healthy if healthy else providers
            except Exception:
                ordered = providers
        else:
            ordered = providers

        last_error = None
        for provider in ordered:
            try:
                if provider == "together-llama-guard-3":
                    response = await self._call_together_moderation(input_data)
                elif provider == "groq-llama-guard-3":
                    response = await self._call_groq_moderation(input_data)
                else:
                    raise ValueError(f"Unknown moderation provider: {provider}")
                
                await self._record_health(provider, capability, True)
                return response
            except Exception as e:
                logger.warning(f"{capability} provider {provider} failed: {e}")
                last_error = e
                await self._record_health(provider, capability, False)
                continue
                
        raise ProviderUnavailableError(f"All {capability} providers failed. Last error: {last_error}")

    async def _call_together_moderation(self, input_data: dict) -> GatewayResponse:
        api_key = self.together_key
        payload = {
            "model": "meta-llama/Llama-Guard-3-8B",
            "messages": [
                {"role": "user", "content": input_data.get("text", "")}
            ],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.together.xyz/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            tokens_in = usage.get("prompt_tokens", 0)
            tokens_out = usage.get("completion_tokens", 0)
            cost = self._calculate_cost("together-llama-guard-3", tokens_in, tokens_out)
            
            return GatewayResponse(
                text=text,
                cost_inr=cost,
                model_used="together-llama-guard-3",
                tokens_in=tokens_in,
                tokens_out=tokens_out
            )

    async def _call_groq_moderation(self, input_data: dict) -> GatewayResponse:
        api_key = os.environ.get("GROQ_API_KEY", "")
        payload = {
            "model": "llama-guard-3-8b",
            "messages": [
                {"role": "user", "content": input_data.get("text", "")}
            ],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            tokens_in = usage.get("prompt_tokens", 0)
            tokens_out = usage.get("completion_tokens", 0)
            cost = self._calculate_cost("groq-llama-guard-3", tokens_in, tokens_out)
            
            return GatewayResponse(
                text=text,
                cost_inr=cost,
                model_used="groq-llama-guard-3",
                tokens_in=tokens_in,
                tokens_out=tokens_out
            )

    async def _vision_with_fallback(self, input_data: dict) -> dict:
        gen_id = input_data.get("gen_id", "unknown")
        image_b64 = input_data["image_b64"]
        
        providers = [
            ("openai",      self._call_openai_vision),
            ("gemini",      self._call_gemini_vision),
        ]
        
        last_error = None
        for name, fn in providers:
            try:
                logger.info(f"Vision attempt via {name} for gen_id={gen_id}")
                result = await fn(image_b64, gen_id)
                logger.info(f"Vision success via {name} for gen_id={gen_id}")
                return result
            except Exception as e:
                logger.warning(f"Vision provider {name} failed for gen_id={gen_id}: {e}")
                last_error = e
                continue
        
        raise Exception(f"All vision providers failed for gen_id={gen_id}. Last error: {last_error}")

    async def _call_together_vision(self, image_b64: str, gen_id: str) -> dict:
        payload = {
            "model": "meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": VISION_PROMPT
                        }
                    ]
                }
            ],
            "max_tokens": 512,
            "temperature": 0.1
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.together.xyz/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.together_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"]
            return _parse_json_response(raw)

    async def _call_gemini_vision(self, image_b64: str, gen_id: str) -> dict:
        import google.generativeai as genai
        from PIL import Image as PILImage
        genai.configure(api_key=self.gemini_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        image = PILImage.open(io.BytesIO(base64.b64decode(image_b64)))
        
        def call():
            return model.generate_content([VISION_PROMPT, image]).text
        
        raw = await asyncio.to_thread(call)
        return _parse_json_response(raw)

    async def _call_openai_vision(self, image_b64: str, gen_id: str) -> dict:
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": VISION_PROMPT
                        }
                    ]
                }
            ],
            "max_tokens": 512,
            "temperature": 0.1
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_key}",
                    "Content-Type": "application/json"
                },
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"]
            return _parse_json_response(raw)


_gateway_instance = None

def get_gateway(redis_client=None) -> ModelGateway:
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = ModelGateway(redis_client=redis_client)
    return _gateway_instance


class StubGateway:
    async def route(self, capability: str, input_data: dict, max_tokens: int = None) -> GatewayResponse:
        raise NotImplementedError(
            f"StubGateway called with capability='{capability}' "
            f"for gen_id={input_data.get('gen_id')}."
        )
