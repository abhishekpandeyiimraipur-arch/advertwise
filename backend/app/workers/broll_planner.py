"""
BRollPlanner — deterministic B-roll clip selection.
Zero LLM calls. Zero external API. Pure SQL query.

Motion and environment constants are defined here because
no lookup table exists in the DB schema — IDs are plain
integers whose meaning lives in code.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Motion Archetype Constants ────────────────────────────────────
# Integer IDs map to WorkerI2V.MOTION_ARCHETYPES — keep in sync.
# ID → human-readable name shown on HD-4 Strategy Card.
MOTION_NAMES: dict[int, str] = {
    1: "Orbit",         # Product rotates slowly
    2: "Drift",         # Gentle lateral float — default/gentle_zoom
    3: "Hero Zoom",     # Push-in zoom on product
    4: "Unbox",         # Product reveal motion
    5: "Liquid Pour",   # Liquid/pour products
}

# ── Environment Preset Constants ─────────────────────────────────
# No DB lookup table. IDs defined here. WorkerI2V reads these.
ENV_NAMES: dict[int, str] = {
    1: "Clean White",        # Minimal studio, white background
    2: "Minimal Studio",     # Dark/neutral studio
    3: "Kitchen Warm",       # Morning kitchen, natural light
    4: "Outdoor Natural",    # Natural outdoor setting
    5: "Living Room Warm",   # Home interior, warm tones
    6: "Outdoor Fashion",    # Fashion outdoor
    7: "Home Interior",      # Home decor setting
    8: "Product Focus",      # Pure product on surface
}

# ── Cold-Start Style Defaults (BEF GAP-12) ───────────────────────
# Used by WorkerStrategist when motion_archetype_id or
# environment_preset_id is NULL in DB (new user, first generation).
# Keys match GreenZoneCategory ENUM values exactly.
COLD_START_DEFAULTS: dict[str, dict] = {
    "packaged_food":  {"motion_archetype_id": 2, "environment_preset_id": 3},
    "d2c_beauty":     {"motion_archetype_id": 4, "environment_preset_id": 1},
    "electronics":    {"motion_archetype_id": 1, "environment_preset_id": 2},
    "fashion":        {"motion_archetype_id": 2, "environment_preset_id": 4},
    "home_decor":     {"motion_archetype_id": 2, "environment_preset_id": 5},
    "home_kitchen":   {"motion_archetype_id": 3, "environment_preset_id": 3},
}
# Fallback for any category not in COLD_START_DEFAULTS
DEFAULT_STYLE_FALLBACK = {"motion_archetype_id": 2, "environment_preset_id": 1}


class BRollPlanner:
    """
    Deterministic B-roll clip selection from the broll_clips table.
    No LLM. No external API. Returns up to 3 matching clips.

    Query logic:
      1. Match by framework_angle (maps to broll_clips.archetype)
      2. Match by product category
      3. Only active clips (is_active = TRUE)
      4. Max 3 clips (DB constraint: b_roll_plan max length 3)

    If no clips match → returns [] (b_roll_available: false on HD-5)
    """

    def __init__(self, db_pool):
        self.db = db_pool

    async def plan(
        self,
        framework_angle: str,
        category: str,
    ) -> list[dict]:
        """
        Returns up to 3 B-roll clip dicts for the given angle + category.

        Args:
            framework_angle: "emotion" | "logic" | "conversion"
            category: GreenZoneCategory value e.g. "packaged_food"

        Returns:
            list of dicts with keys: clip_id, r2_url, duration_ms, archetype
            Empty list if no matching clips found.
        """
        try:
            async with self.db.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT clip_id, r2_url, duration_ms, archetype
                       FROM broll_clips
                       WHERE archetype = $1
                         AND category = $2
                         AND is_active = TRUE
                       ORDER BY clip_id
                       LIMIT 3""",
                    framework_angle,
                    category,
                )
            return [dict(row) for row in rows]
        except Exception as e:
            # Graceful degradation — broll_clips table may be empty
            # during beta. Return empty list, not an error.
            logger.warning(
                f"BRollPlanner: query failed for "
                f"angle={framework_angle} category={category}: {e}. "
                f"Returning empty b_roll_plan."
            )
            return []
