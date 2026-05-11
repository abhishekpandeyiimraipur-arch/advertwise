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
    "packaged_food":    {"motion_archetype_id": 2, "environment_preset_id": 3},
    "d2c_beauty":       {"motion_archetype_id": 4, "environment_preset_id": 1},
    "electronics":      {"motion_archetype_id": 1, "environment_preset_id": 2},
    "hard_accessories": {"motion_archetype_id": 3, "environment_preset_id": 2},
    "home_kitchen":     {"motion_archetype_id": 2, "environment_preset_id": 3},
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

    ANGLE_TO_HOOK_ARCHETYPE: dict[str, str] = {
        "emotion":               "lifestyle",
        "logic":                 "lifestyle",
        "conversion":            "lifestyle",
        "festival_occasion_hook":"lifestyle",
        "premium_upgrade":       "lifestyle",
        "hyper_local_comfort":   "lifestyle",
        "spec_drop_flex":        "lifestyle",
        "scarcity_drop":         "lifestyle",
        "social_proof":          "lifestyle",
        "pas_micro":             "lifestyle",
        "myth_buster":           "lifestyle",
        "asmr_trigger":          "lifestyle",
        "usage_ritual":          "lifestyle",
        "roi_durability_flex":   "lifestyle",
        "clinical_flex":         "lifestyle",
    }

    ANGLE_TO_CTA_ARCHETYPE: dict[str, str] = {
        "emotion":               "cta_clean",
        "logic":                 "cta_clean",
        "conversion":            "cta_clean",
        "festival_occasion_hook":"cta_clean",
        "premium_upgrade":       "cta_clean",
        "hyper_local_comfort":   "cta_clean",
        "spec_drop_flex":        "cta_clean",
        "scarcity_drop":         "cta_clean",
        "social_proof":          "cta_clean",
        "pas_micro":             "cta_clean",
        "myth_buster":           "cta_clean",
        "asmr_trigger":          "cta_clean",
        "usage_ritual":          "cta_clean",
        "roi_durability_flex":   "cta_clean",
        "clinical_flex":         "cta_clean",
    }

    def __init__(self, db_pool):
        self.db = db_pool

    async def plan(self, framework_angle: str, category: str) -> list[dict]:
        hook_archetype = self.ANGLE_TO_HOOK_ARCHETYPE.get(
            framework_angle, "lifestyle"
        )
        cta_archetype = self.ANGLE_TO_CTA_ARCHETYPE.get(
            framework_angle, "cta_clean"
        )

        try:
            async with self.db.acquire() as conn:
                # Hook clip — match category first, fallback to any category
                hook_row = await conn.fetchrow(
                    """SELECT clip_id, r2_url, duration_ms, archetype
                       FROM broll_clips
                       WHERE archetype = $1
                         AND category = $2::green_zone_category
                         AND is_active = TRUE
                       ORDER BY clip_id ASC
                       LIMIT 1""",
                    hook_archetype, category
                )
                if not hook_row:
                    # Fallback: any category with this archetype
                    hook_row = await conn.fetchrow(
                        """SELECT clip_id, r2_url, duration_ms, archetype
                           FROM broll_clips
                           WHERE archetype = $1
                             AND is_active = TRUE
                           ORDER BY clip_id ASC
                           LIMIT 1""",
                        hook_archetype
                    )
                if not hook_row:
                    return []

                # CTA clip — match category first, fallback to any category
                cta_row = await conn.fetchrow(
                    """SELECT clip_id, r2_url, duration_ms, archetype
                       FROM broll_clips
                       WHERE archetype = $1
                         AND category = $2::green_zone_category
                         AND is_active = TRUE
                         AND clip_id != $3
                       ORDER BY clip_id ASC
                       LIMIT 1""",
                    cta_archetype, category, hook_row["clip_id"]
                )
                if not cta_row:
                    # Fallback: any category with this archetype
                    cta_row = await conn.fetchrow(
                        """SELECT clip_id, r2_url, duration_ms, archetype
                           FROM broll_clips
                           WHERE archetype = $1
                             AND is_active = TRUE
                             AND clip_id != $2
                           ORDER BY clip_id ASC
                           LIMIT 1""",
                        cta_archetype, hook_row["clip_id"]
                    )
                if not cta_row:
                    return []

            return [dict(hook_row), dict(cta_row)]

        except Exception as e:
            logger.warning(
                f"BRollPlanner: query failed for "
                f"angle={framework_angle} category={category}: {e}. "
                f"Returning empty b_roll_plan."
            )
            return []
