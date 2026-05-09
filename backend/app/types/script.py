from dataclasses import dataclass


@dataclass
class Script:
    """
    Canonical Script type. Shared across WorkerCopy, WorkerCritic,
    WorkerSafety, and phase2_chain.

    Lives here — not in any worker file — so that no worker ever
    needs to import from another worker (import graph rule).

    Fields mirror the prompt YAML output schema for script-generate
    v1.0.0. All LLM-generated fields are required at construction
    except critic_score and critic_rationale which are added later
    by WorkerCritic.
    """

    # ── LLM-generated structural fields (set by WorkerCopy) ──────
    hook: str                 # Opening line — displayed as tile headline on HD-3
    body: str                 # Middle section — product proof / story
    cta: str                  # Call-to-action line — displayed on tile footer
    full_text: str            # Complete concatenated script (hook + body + cta)
    word_count: int           # Total word count — LLM-computed
    language_mix: str         # 'pure_hindi' | 'hinglish' | 'pure_english'

    # ── Framework metadata (set by WorkerCopy) ───────────────────
    framework: str            # AdFramework enum value as string
    framework_angle: str      # 'logic' | 'emotion' | 'conversion'
    framework_rationale: str  # Why this framework was chosen for this product
    evidence_note: str        # Which product evidence this script draws on
    suggested_tone: str       # Tone guidance passed to TTS worker

    # ── Scoring fields (set by WorkerCritic, default empty) ──────
    critic_score: int = 0
    critic_rationale: str = ""
