"""
L5: ModelGateway — Phase 1 Vision implementation.
Calls Gemini Vision API for product analysis.
"""
import os
import base64
import json
import logging
import google.generativeai as genai
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
  "color_palette": ["#hex1", "#hex2", "#hex3"] — dominant product colors,
  "shape": "one of: bottle, box, pouch, tube, jar, can, irregular"
}

Return ONLY the JSON object. No markdown, no explanation, no backticks."""


class ModelGateway:
    def __init__(self):
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        self.vision_model = genai.GenerativeModel("gemini-2.0-flash")

    async def route(self, capability: str, input_data: dict) -> dict:
        if capability == "vision":
            return await self._vision_analysis(input_data)
        raise NotImplementedError(f"Unknown capability: {capability}")

    async def _vision_analysis(self, input_data: dict) -> dict:
        import asyncio
        image_b64 = input_data["image_b64"]
        gen_id = input_data.get("gen_id", "unknown")

        image_bytes = base64.b64decode(image_b64)
        image = Image.open(io.BytesIO(image_bytes))

        def call_gemini():
            response = self.vision_model.generate_content([
                VISION_PROMPT,
                image
            ])
            return response.text

        try:
            raw = await asyncio.to_thread(call_gemini)
            # Strip markdown fences if present
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            result = json.loads(clean.strip())
            logger.info(f"Gemini Vision success for gen_id={gen_id}: category={result.get('category')}")
            return result
        except Exception as e:
            logger.error(f"Gemini Vision failed for gen_id={gen_id}: {e}")
            raise


# Singleton — built once at worker startup
_gateway_instance = None

def get_gateway() -> ModelGateway:
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = ModelGateway()
    return _gateway_instance


# Backwards compat — StubGateway kept for reference only
class StubGateway:
    async def route(self, capability: str, input_data: dict) -> dict:
        raise NotImplementedError(
            f"ModelGateway not yet built. "
            f"Called with capability='{capability}' for gen_id={input_data.get('gen_id')}. "
            f"Build L5 ModelGateway in gateway slice."
        )
