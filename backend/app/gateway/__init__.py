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


class ModelGateway:
    def __init__(self):
        self.together_key = os.environ.get("TOGETHER_API_KEY", "")
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")
        self.openai_key = os.environ.get("OPEN_AI_API_KEY", "")

    async def route(self, capability: str, input_data: dict) -> dict:
        if capability == "vision":
            return await self._vision_with_fallback(input_data)
        raise NotImplementedError(f"Unknown capability: {capability}")

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

def get_gateway() -> ModelGateway:
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = ModelGateway()
    return _gateway_instance


class StubGateway:
    async def route(self, capability: str, input_data: dict) -> dict:
        raise NotImplementedError(
            f"StubGateway called with capability='{capability}' "
            f"for gen_id={input_data.get('gen_id')}."
        )
