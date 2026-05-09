from app.schemas.enums import AdFramework

# Maps each AdFramework to its dominant creative angle.
# Used by WorkerCopy to tag scripts and by WorkerCritic
# for tie-breaking when critic scores are equal.
# Tie-break priority: conversion > emotion > logic
FRAMEWORK_ANGLE_MAP: dict[AdFramework, str] = {
    # emotion-led
    AdFramework.PAS_MICRO:              "emotion",
    AdFramework.USAGE_RITUAL:           "emotion",
    AdFramework.ASMR_TRIGGER:           "emotion",
    AdFramework.HYPER_LOCAL_COMFORT:    "emotion",
    AdFramework.PREMIUM_UPGRADE:        "emotion",
    # logic-led
    AdFramework.CLINICAL_FLEX:          "logic",
    AdFramework.MYTH_BUSTER:            "logic",
    AdFramework.SPEC_DROP_FLEX:         "logic",
    AdFramework.ROI_DURABILITY_FLEX:    "logic",
    # conversion-led
    AdFramework.FESTIVAL_OCCASION_HOOK: "conversion",
    AdFramework.SCARCITY_DROP:          "conversion",
    AdFramework.SOCIAL_PROOF:           "conversion",
}

# Default safe fallback trio — 1 emotion + 1 logic + 1 conversion.
# Guarantees one script per angle even on weak product evidence.
# Used by:
#   - WorkerCopy.framework_router() on weak evidence detection
#   - phase2_chain on SafetyError auto-retry
SAFE_TRIO: list[AdFramework] = [
    AdFramework.PAS_MICRO,               # emotion
    AdFramework.CLINICAL_FLEX,           # logic
    AdFramework.FESTIVAL_OCCASION_HOOK,  # conversion
]
