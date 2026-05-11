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
  "category": "one of: d2c_beauty | packaged_food | hard_accessories | electronics | home_kitchen | d2c_fashion. Use d2c_fashion for clothing, kurta, saree, lehenga, ethnic wear, western wear, fashion, apparel, footwear, bags",
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
    "llm":        ["groq-llama-3.3-70b", "together-llama-3.3"],
    "moderation": ["together-llama-guard-3", "groq-llama-guard-3"],
}

# ── TTS Provider Registry ─────────────────────────────────────────
# Adding a new TTS provider = add one entry here. Zero other changes.
TTS_PROVIDERS: dict = {
    "sarvam": {
        "url": "https://api.sarvam.ai/text-to-speech",
        "key_env": "SARVAM_API_KEY",
        "cost_inr": Decimal("1.50"),
        "lang_map": {
            "hindi":    "hi-IN",
            "hinglish": "hi-IN",
            "marathi":  "mr-IN",
            "punjabi":  "pa-IN",
            "bengali":  "bn-IN",
            "tamil":    "ta-IN",
            "telugu":   "te-IN",
            "english":  "en-IN",
        },
    },
    "elevenlabs": {
        "url": "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM",
        "key_env": "ELEVENLABS_API_KEY",
        "cost_inr": Decimal("3.00"),
    },
    "google": {
        "url": "https://texttospeech.googleapis.com/v1/text:synthesize",
        "key_env": "GOOGLE_APPLICATION_CREDENTIALS",
        "cost_inr": Decimal("1.00"),
    },
}

# ── I2V Provider Registry ─────────────────────────────────────────
# All Fal.ai models use identical queue pattern.
# Adding a new model = add one entry here.
FAL_QUEUE_BASE = "https://queue.fal.run"
I2V_MODELS: dict = {
    "fal-ai/wan-i2v": {
        "key_env": "FAL_KEY",
        "cost_inr": Decimal("13.00"),
    },
    "fal-ai/kling-video/v1.6/standard/image-to-video": {
        "key_env": "FAL_KEY",
        "cost_inr": Decimal("25.00"),
    },
    "fal-ai/minimax-video/image-to-video": {
        "key_env": "FAL_KEY",
        "cost_inr": Decimal("18.00"),
    },
}
# Fallback model if requested model not in registry
I2V_DEFAULT_MODEL = "fal-ai/wan-i2v"

# Replicate models (fallback when Fal.ai exhausted)
REPLICATE_API_BASE = "https://api.replicate.com/v1"
REPLICATE_MODELS: dict = {
    "replicate/wan-2.1-i2v": {
        "version": "e2870aa4965fd9ddfd87c16a3c8ab952c18e745e63f3f3b123c2dc8b538ad2b5",
        "key_env": "REPLICATE_API_TOKEN",
        "cost_inr": Decimal("12.00"),
    },
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

        elif capability == "tts":
            response = await self._route_tts(input_data)
            response.latency_ms = int((time.monotonic() - start) * 1000)
        elif capability == "i2v":
            response = await self._route_i2v(input_data)
            response.latency_ms = int((time.monotonic() - start) * 1000)
        elif capability == "embedding":
            raise NotImplementedError("Embedding: Micro-phase 5.")

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


    async def _call_replicate_i2v(self, input_data: dict) -> GatewayResponse:
        """
        Replicate I2V fallback via raw HTTP.
        Pattern: POST /predictions → poll GET /predictions/{id}
        """
        import httpx, asyncio

        image_url = input_data.get("image_url", "")
        prompt    = input_data.get("prompt", "")
        duration  = input_data.get("duration", 9)
        seed      = input_data.get("seed", 42)
        gen_id    = input_data.get("gen_id", "")

        model_cfg = REPLICATE_MODELS["replicate/wan-2.1-i2v"]
        api_key   = os.environ.get(model_cfg["key_env"], "") or os.environ.get("REPLICATE_API_TOKEN", "")
        if not api_key:
            raise ProviderUnavailableError("REPLICATE_API_TOKEN not set")
        headers   = {
            "Authorization": f"Token {api_key}",
            "Content-Type":  "application/json",
        }

        logger.info(f"Replicate I2V submit gen={gen_id}")

        async with httpx.AsyncClient(timeout=30.0) as client:

            # Step 1: Submit
            submit_resp = await client.post(
                f"{REPLICATE_API_BASE}/predictions",
                json={
                    "version": model_cfg["version"],
                    "input": {
                        "image":  image_url,
                        "prompt": prompt,
                        "seed":   seed,
                    },
                },
                headers=headers,
            )

            if submit_resp.status_code not in (200, 201):
                await self._record_health("replicate", "i2v", False)
                raise ProviderUnavailableError(
                    f"Replicate submit failed {submit_resp.status_code}: "
                    f"{submit_resp.text[:300]}"
                )

            prediction_id = submit_resp.json().get("id", "")
            logger.info(f"Replicate I2V queued gen={gen_id} id={prediction_id}")

            # Step 2: Poll every 5s (max 200s)
            for attempt in range(40):
                await asyncio.sleep(5)
                poll_resp = await client.get(
                    f"{REPLICATE_API_BASE}/predictions/{prediction_id}",
                    headers=headers,
                    timeout=10.0,
                )
                if poll_resp.status_code != 200:
                    continue

                poll_data = poll_resp.json()
                status    = poll_data.get("status", "")
                logger.info(
                    f"Replicate poll gen={gen_id} "
                    f"attempt={attempt+1} status={status}"
                )

                if status == "succeeded":
                    output = poll_data.get("output", [])
                    video_url = output[0] if output else ""
                    if not video_url:
                        raise ProviderUnavailableError(
                            f"Replicate succeeded but no output gen={gen_id}"
                        )
                    await self._record_health("replicate", "i2v", True)
                    logger.info(
                        f"Replicate I2V done gen={gen_id} "
                        f"url={video_url[:60]}..."
                    )
                    return GatewayResponse(
                        video_url=video_url,
                        model_used="replicate/wan-2.1-i2v",
                        cost_inr=model_cfg["cost_inr"],
                    )
                elif status in ("failed", "canceled"):
                    await self._record_health("replicate", "i2v", False)
                    error = poll_data.get("error", "unknown")
                    raise ProviderUnavailableError(
                        f"Replicate {status} gen={gen_id}: {error}"
                    )

            await self._record_health("replicate", "i2v", False)
            raise ProviderUnavailableError(
                f"Replicate timeout after 200s gen={gen_id}"
            )


    async def _call_minimax_i2v(self, input_data: dict) -> GatewayResponse:
        import httpx, asyncio
        image_url = input_data.get("image_url", "")
        prompt    = input_data.get("prompt", "")
        gen_id    = input_data.get("gen_id", "")
        api_key   = os.environ.get("MINIMAX_API_KEY", "")
        headers   = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        logger.info(f"Minimax I2V submit gen={gen_id}")
        async with httpx.AsyncClient(timeout=30.0) as client:
            submit_resp = await client.post(
                "https://api.minimax.io/v1/video_generation",
                json={"model": "MiniMax-Hailuo-2.3", "prompt": prompt,
                      "first_frame_image": image_url, "duration": 6, "resolution": "768P"},
                headers=headers,
            )
            if submit_resp.status_code not in (200, 201):
                await self._record_health("minimax", "i2v", False)
                raise ProviderUnavailableError(f"Minimax submit failed {submit_resp.status_code}: {submit_resp.text[:300]}")
            task_id = submit_resp.json().get("task_id", "")
            if not task_id:
                raise ProviderUnavailableError(f"Minimax no task_id gen={gen_id}: {submit_resp.text[:200]}")
            logger.info(f"Minimax I2V queued gen={gen_id} task_id={task_id}")
            for attempt in range(40):
                await asyncio.sleep(5)
                poll_resp = await client.get("https://api.minimax.io/v1/query/video_generation",
                    params={"task_id": task_id}, headers=headers, timeout=10.0)
                if poll_resp.status_code != 200:
                    continue
                poll_data = poll_resp.json()
                status = poll_data.get("status", "")
                logger.info(f"Minimax poll gen={gen_id} attempt={attempt+1} status={status}")
                if status == "Success":
                    file_id = poll_data.get("file_id", "")
                    break
                elif status in ("Fail", "Failed", "Cancelled"):
                    await self._record_health("minimax", "i2v", False)
                    raise ProviderUnavailableError(f"Minimax {status} gen={gen_id}")
            else:
                await self._record_health("minimax", "i2v", False)
                raise ProviderUnavailableError(f"Minimax timeout 200s gen={gen_id}")
            file_resp = await client.get("https://api.minimax.io/v1/files/retrieve",
                params={"file_id": file_id}, headers=headers, timeout=10.0)
            if file_resp.status_code != 200:
                raise ProviderUnavailableError(f"Minimax file retrieve failed {file_resp.status_code} gen={gen_id}")
            video_url = file_resp.json().get("file", {}).get("download_url", "")
            if not video_url:
                raise ProviderUnavailableError(f"Minimax no download_url gen={gen_id}")
        await self._record_health("minimax", "i2v", True)
        logger.info(f"Minimax I2V done gen={gen_id} url={video_url[:60]}...")
        return GatewayResponse(video_url=video_url, model_used="MiniMax-Hailuo-2.3", cost_inr=Decimal("18.00"))

    # ══════════════════════════════════════════════════════
    # TTS ROUTING
    # ══════════════════════════════════════════════════════

    async def _route_tts(self, input_data: dict) -> GatewayResponse:
        """
        Routes TTS request to correct provider via registry.
        input_data: {text, language, provider, gen_id}
        Returns GatewayResponse(audio_bytes=bytes)
        """
        provider = input_data.get("provider", "sarvam")
        text     = input_data.get("text", "")
        language = input_data.get("language", "hindi")
        gen_id   = input_data.get("gen_id", "")

        if provider not in TTS_PROVIDERS:
            logger.warning(
                f"TTS provider '{provider}' not in registry, "
                f"falling back to sarvam"
            )
            provider = "sarvam"

        config  = TTS_PROVIDERS[provider]
        api_key = os.environ.get(config["key_env"], "")

        if provider == "sarvam":
            return await self._call_sarvam_tts(
                text, language, gen_id, config, api_key
            )
        elif provider == "elevenlabs":
            return await self._call_elevenlabs_tts(
                text, gen_id, config, api_key
            )
        else:
            # Generic fallback — try sarvam
            return await self._call_sarvam_tts(
                text, language, gen_id,
                TTS_PROVIDERS["sarvam"],
                os.environ.get("SARVAM_API_KEY", "")
            )

    async def _call_sarvam_tts(
        self,
        text: str,
        language: str,
        gen_id: str,
        config: dict,
        api_key: str,
    ) -> GatewayResponse:
        """
        Calls Sarvam AI TTS. Returns GatewayResponse(audio_bytes).
        Sarvam returns base64-encoded WAV audio.
        """
        import httpx, base64

        lang_map  = config.get("lang_map", {})
        lang_code = lang_map.get(language, "hi-IN")

        payload = {
            "inputs":               [text],
            "target_language_code": lang_code,
            "speaker":              "anushka",
            "pitch":                0,
            "pace":                 1.0,
            "loudness":             1.5,
            "speech_sample_rate":   22050,
            "enable_preprocessing": True,
            "model":                "bulbul:v2",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                config["url"],
                json=payload,
                headers={
                    "api-subscription-key": api_key,
                    "Content-Type": "application/json",
                },
            )

        if resp.status_code != 200:
            await self._record_health("sarvam-bulbul", "tts", False)
            raise ProviderUnavailableError(
                f"Sarvam TTS {resp.status_code}: {resp.text[:200]}"
            )

        data       = resp.json()
        audio_b64  = data.get("audios", [""])[0]
        audio_bytes = base64.b64decode(audio_b64)

        await self._record_health("sarvam-bulbul", "tts", True)
        logger.info(
            f"Sarvam TTS done gen={gen_id} lang={lang_code} "
            f"bytes={len(audio_bytes)}"
        )
        return GatewayResponse(
            audio_bytes=audio_bytes,
            model_used="sarvam-bulbul:v1",
            cost_inr=config["cost_inr"],
        )

    async def _call_elevenlabs_tts(
        self,
        text: str,
        gen_id: str,
        config: dict,
        api_key: str,
    ) -> GatewayResponse:
        """
        Calls ElevenLabs TTS. Returns GatewayResponse(audio_bytes).
        ElevenLabs returns raw MP3 bytes directly.
        """
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                config["url"],
                json={
                    "text":     text,
                    "model_id": "eleven_monolingual_v1",
                    "voice_settings": {
                        "stability":        0.5,
                        "similarity_boost": 0.75,
                    },
                },
                headers={
                    "xi-api-key":   api_key,
                    "Content-Type": "application/json",
                    "Accept":       "audio/mpeg",
                },
            )

        if resp.status_code != 200:
            await self._record_health("elevenlabs", "tts", False)
            raise ProviderUnavailableError(
                f"ElevenLabs TTS {resp.status_code}: {resp.text[:200]}"
            )

        audio_bytes = resp.content
        await self._record_health("elevenlabs", "tts", True)
        logger.info(
            f"ElevenLabs TTS done gen={gen_id} bytes={len(audio_bytes)}"
        )
        return GatewayResponse(
            audio_bytes=audio_bytes,
            model_used="elevenlabs-rachel",
            cost_inr=config["cost_inr"],
        )

    # ══════════════════════════════════════════════════════
    # I2V ROUTING — Fal.ai Queue Pattern (model-agnostic)
    # ══════════════════════════════════════════════════════

    async def _route_i2v(self, input_data: dict) -> GatewayResponse:
        """
        I2V with 3-provider fallback chain:
        1. Fal.ai → 2. Replicate → 3. Minimax
        Moves to next provider on 402/403/credit errors.
        """
        gen_id = input_data.get("gen_id", "")

        try:
            return await self._call_fal_i2v(input_data)
        except ProviderUnavailableError as e:
            if any(x in str(e) for x in ["403", "402", "Exhausted", "locked", "credit", "balance"]):
                logger.warning(f"Fal.ai exhausted gen={gen_id} — trying Replicate")
            else:
                raise

        try:
            return await self._call_replicate_i2v(input_data)
        except ProviderUnavailableError as e:
            if any(x in str(e) for x in ["402", "403", "credit", "Insufficient"]):
                logger.warning(f"Replicate exhausted gen={gen_id} — trying Minimax")
            else:
                raise

        return await self._call_minimax_i2v(input_data)

    async def _call_fal_i2v(self, input_data: dict) -> GatewayResponse:
        """Fal.ai I2V via raw HTTP queue."""
        import httpx, asyncio

        model     = input_data.get("model", I2V_DEFAULT_MODEL)
        image_url = input_data.get("image_url", "")
        prompt    = input_data.get("prompt", "")
        duration  = input_data.get("duration", 9)
        seed      = input_data.get("seed", 42)
        gen_id    = input_data.get("gen_id", "")

        # Resolve model config — fall back to default if unknown
        model_config = I2V_MODELS.get(model, I2V_MODELS[I2V_DEFAULT_MODEL])
        api_key      = os.environ.get(model_config["key_env"], "")
        headers      = {
            "Authorization": f"Key {api_key}",
            "Content-Type":  "application/json",
        }

        submit_url = f"{FAL_QUEUE_BASE}/{model}"
        status_url = f"{FAL_QUEUE_BASE}/{model}/requests/{{request_id}}/status"
        result_url = f"{FAL_QUEUE_BASE}/{model}/requests/{{request_id}}"

        logger.info(
            f"Fal.ai I2V submit gen={gen_id} model={model} "
            f"duration={duration}s"
        )

        async with httpx.AsyncClient(timeout=30.0) as client:

            # Step 1: Submit job
            submit_resp = await client.post(
                submit_url,
                json={
                    "image_url": image_url,
                    "prompt":    prompt,
                    "duration":  duration,
                    "seed":      seed,
                },
                headers=headers,
            )

            if submit_resp.status_code not in (200, 201, 202):
                await self._record_health("fal-ai", "i2v", False)
                raise ProviderUnavailableError(
                    f"Fal.ai submit failed {submit_resp.status_code}: "
                    f"{submit_resp.text[:300]}"
                )

            request_id = submit_resp.json().get("request_id", "")
            if not request_id:
                raise ProviderUnavailableError(
                    f"Fal.ai returned no request_id gen={gen_id}"
                )

            logger.info(
                f"Fal.ai I2V queued gen={gen_id} "
                f"request_id={request_id}"
            )

            # Step 2: Poll status every 5 seconds (max 200 seconds)
            max_polls = 40
            poll_interval = 5

            for attempt in range(max_polls):
                await asyncio.sleep(poll_interval)

                status_resp = await client.get(
                    status_url.format(request_id=request_id),
                    headers=headers,
                    timeout=10.0,
                )

                if status_resp.status_code != 200:
                    logger.warning(
                        f"Fal.ai status check failed attempt={attempt} "
                        f"status={status_resp.status_code}"
                    )
                    continue

                status_data   = status_resp.json()
                current_status = status_data.get("status", "")

                logger.info(
                    f"Fal.ai I2V poll gen={gen_id} "
                    f"attempt={attempt+1}/{max_polls} "
                    f"status={current_status}"
                )

                if current_status == "COMPLETED":
                    break
                elif current_status in ("FAILED", "CANCELLED"):
                    await self._record_health("fal-ai", "i2v", False)
                    raise ProviderUnavailableError(
                        f"Fal.ai job {current_status} gen={gen_id}"
                    )
                # IN_QUEUE or IN_PROGRESS → keep polling

            else:
                # max_polls exceeded
                await self._record_health("fal-ai", "i2v", False)
                raise ProviderUnavailableError(
                    f"Fal.ai I2V timeout after "
                    f"{max_polls * poll_interval}s gen={gen_id}"
                )

            # Step 3: Get result
            result_resp = await client.get(
                result_url.format(request_id=request_id),
                headers=headers,
                timeout=10.0,
            )

            if result_resp.status_code != 200:
                raise ProviderUnavailableError(
                    f"Fal.ai result fetch failed "
                    f"{result_resp.status_code} gen={gen_id}"
                )

            result    = result_resp.json()
            video_url = (
                result.get("video", {}).get("url")
                or result.get("video_url")
                or ""
            )

            if not video_url:
                raise ProviderUnavailableError(
                    f"Fal.ai returned no video URL gen={gen_id} "
                    f"result_keys={list(result.keys())}"
                )

        await self._record_health("fal-ai", "i2v", True)
        logger.info(
            f"Fal.ai I2V complete gen={gen_id} model={model} "
            f"video_url={video_url[:60]}..."
        )

        return GatewayResponse(
            video_url=video_url,
            model_used=model,
            cost_inr=model_config["cost_inr"],
        )


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
