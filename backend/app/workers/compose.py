"""
WorkerCompose — Assembles the 15s fractional render.
[TDD-WORKERS]-H

MVP pattern: Hook(3s) + I2V(9s) + CTA(3s)
Applies LUT color grade based on product benefit.
Burns SGI watermark per IT Rules 2026.
No DB access. No state transitions.
All temp files written to /tmp/{gen_id}_*.
Cleanup runs in finally block — always executes.
"""
import asyncio
import json
import logging
import os
import shutil
from pathlib import Path
from app.core.exceptions import ComposeError, ComposeDurationError

logger = logging.getLogger(__name__)

CANONICAL_DURATION_S = 15.0
MAX_SEGMENT_DURATION_S = 10.0

# LUT directory — relative to this file's location
# backend/app/luts/*.cube
LUT_DIR = Path(__file__).parent.parent / "luts"

BENEFIT_LUT_MAP: dict[str, str] = {
    "premium":  "premium_warm.cube",
    "trending": "trending_vivid.cube",
    "gift":     "gift_festive.cube",
    "natural":  "natural_green.cube",
}
DEFAULT_LUT = "neutral_balanced.cube"

SGI_WATERMARK_TEXT = "AI Generated | Adcreo"

# ── Pacing Templates ──────────────────────────────────────────
# Each template defines the segment structure for a 15s ad.
# source options: "broll" | "i2v" | "color_card"
# overlay options: "hook_top" | "cta_bottom" | "cta_center" | "none"
# transition options: "fade" | "cut" | "none"

PACING_TEMPLATES: dict[str, dict] = {

    "Drift": {
        # Fashion, slow pan, aspirational, premium
        # Mood: cinematic, let product breathe
        "segments": [
            {"type": "hook",    "source": "broll",      "duration_s": 3.0,
             "overlay": "hook_top",    "transition": "fade"},
            {"type": "product", "source": "i2v",        "duration_s": 10.0,
             "overlay": "none",        "transition": "fade"},
            {"type": "cta",     "source": "broll",      "duration_s": 2.0,
             "overlay": "cta_bottom",  "transition": "none"},
        ]
    },

    "Reveal": {
        # Packaged food, home kitchen, warm, trustworthy
        # Mood: clear, balanced, inviting
        "segments": [
            {"type": "hook",    "source": "broll",      "duration_s": 2.5,
             "overlay": "hook_top",    "transition": "cut"},
            {"type": "product", "source": "i2v",        "duration_s": 9.5,
             "overlay": "none",        "transition": "cut"},
            {"type": "cta",     "source": "broll",      "duration_s": 3.0,
             "overlay": "cta_bottom",  "transition": "none"},
        ]
    },

    "Showcase": {
        # Electronics, accessories, spec-heavy
        # Mood: informative, credible, feature-forward
        # 4 segments — adds context B-Roll between product and CTA
        "segments": [
            {"type": "hook",    "source": "broll",      "duration_s": 2.0,
             "overlay": "hook_top",    "transition": "cut"},
            {"type": "product", "source": "i2v",        "duration_s": 7.0,
             "overlay": "none",        "transition": "cut"},
            {"type": "context", "source": "broll",      "duration_s": 2.0,
             "overlay": "none",        "transition": "cut"},
            {"type": "cta",     "source": "broll",      "duration_s": 4.0,
             "overlay": "cta_bottom",  "transition": "none"},
        ]
    },

    "Festival": {
        # festival_occasion_hook, Diwali, gifting, wedding season
        # Mood: warm, celebratory, emotional
        "segments": [
            {"type": "hook",    "source": "broll",      "duration_s": 3.0,
             "overlay": "hook_top",    "transition": "fade"},
            {"type": "product", "source": "i2v",        "duration_s": 9.0,
             "overlay": "none",        "transition": "fade"},
            {"type": "cta",     "source": "broll",      "duration_s": 3.0,
             "overlay": "cta_bottom",  "transition": "none"},
        ]
    },

}

# Maps strategy_card.motion.name → template key
MOTION_TO_TEMPLATE: dict[str, str] = {
    "Drift":          "Drift",
    "Slow Pan":       "Drift",
    "Ambient Float":  "Drift",
    "Float":          "Drift",
    "Product Reveal": "Reveal",
    "Gentle Zoom":    "Reveal",
    "Usage Ritual":   "Reveal",
    "Spec Overlay":   "Showcase",
    "Impact":         "Showcase",
}

# framework_angle overrides motion-based selection
FRAMEWORK_OVERRIDE: dict[str, str] = {
    "festival_occasion_hook": "Festival",
    "spec_drop_flex":         "Showcase",
    "hyper_local_comfort":    "Reveal",
    "premium_upgrade":        "Drift",
    "asmr_trigger":           "Drift",
}

# Overlay style → (y_position_expr, font_size, font_color_expr)
# These are FFmpeg drawtext parameter values
OVERLAY_STYLES: dict[str, tuple] = {
    "hook_top":    ("140",    64, "white"),
    "cta_bottom":  ("h-180",  56, "white"),
    "cta_center":  ("(h-text_h)/2", 60, "white"),
    "none":        (None, None, None),
}

def select_template(strategy_card: dict) -> tuple[str, dict]:
    """
    Selects pacing template from strategy_card.
    framework_angle takes priority over motion.name.
    Returns (template_key, template_dict).
    Falls back to "Drift" if nothing matches.
    """
    framework_angle = (
        strategy_card.get("script_summary", {})
        .get("framework_angle", "")
    )
    motion_name = (
        strategy_card.get("motion", {})
        .get("name", "Drift")
    )

    if framework_angle in FRAMEWORK_OVERRIDE:
        key = FRAMEWORK_OVERRIDE[framework_angle]
    else:
        key = MOTION_TO_TEMPLATE.get(motion_name, "Drift")

    return key, PACING_TEMPLATES[key]


def assign_assets_to_segments(
    template: dict,
    i2v_r2_key: str,
    b_roll_plan: list[dict],
    hook_text: str,
    cta_text: str,
    brand_name: str,
    primary_color: str,
) -> list[dict]:
    """
    Walks template segments and assigns real asset keys.
    Consumes b_roll_plan clips in order across ALL broll slots.
    Falls back to color_card when b_roll_plan is exhausted.
    Returns list of fully-resolved segment dicts.
    """
    broll_queue = list(b_roll_plan)
    resolved = []

    for seg in template["segments"]:
        s = dict(seg)  # copy — never mutate template

        if s["source"] == "i2v":
            s["r2_key"] = i2v_r2_key
            s["clip_id"] = None

        elif s["source"] == "broll":
            if broll_queue:
                clip = broll_queue.pop(0)
                s["r2_key"]  = clip["r2_url"]
                s["clip_id"] = clip["clip_id"]
            else:
                # Exhausted — graceful fallback to color card
                s["source"]  = "color_card"
                s["r2_key"]  = None
                s["clip_id"] = None

        elif s["source"] == "color_card":
            s["r2_key"]  = None
            s["clip_id"] = None

        # Attach overlay text based on overlay style + segment type
        overlay_style = s.get("overlay", "none")
        if overlay_style == "hook_top":
            s["overlay_text"] = hook_text
            s["brand_text"]   = None
        elif overlay_style in ("cta_bottom", "cta_center"):
            s["overlay_text"] = cta_text
            s["brand_text"]   = brand_name  # shown below CTA text
        else:
            s["overlay_text"] = None
            s["brand_text"]   = None

        s["primary_color"] = primary_color
        resolved.append(s)

    return resolved


def build_timeline_ir(
    gen_id: str,
    i2v_r2_key: str,
    tts_r2_key: str,
    strategy_card: dict,
    b_roll_plan: list[dict],
    brand_profile: dict,
) -> dict:
    """
    Converts strategy_card + b_roll_plan → frozen Timeline IR dict.
    Selects pacing template from strategy_card signals.
    Assigns assets to segments with graceful fallback.
    Deterministic: same inputs = same IR every call.
    """
    # Text overlays from strategy
    hook_raw = strategy_card.get("script_summary", {}).get("hook", "")
    cta_raw  = strategy_card.get("script_summary", {}).get("cta", "")

    hook_text = ((hook_raw[:1].upper() + hook_raw[1:])
                 if hook_raw else "Watch This")[:40]
    cta_text  = ((cta_raw[:1].upper() + cta_raw[1:])
                 if cta_raw else "Order Now")[:40]

    # Brand tokens
    primary_color = brand_profile.get("primary_color", "#FFFFFF")
    brand_name    = brand_profile.get("brand_name", "AdvertWise")

    # Select template
    template_key, template = select_template(strategy_card)

    # Assign assets
    segments = assign_assets_to_segments(
        template=template,
        i2v_r2_key=i2v_r2_key,
        b_roll_plan=b_roll_plan,
        hook_text=hook_text,
        cta_text=cta_text,
        brand_name=brand_name,
        primary_color=primary_color,
    )

    return {
        "gen_id": gen_id,
        "duration_s": 15.0,
        "aspect_ratio": "9:16",
        "template_key": template_key,
        "segments": segments,
        "audio": {"r2_key": tts_r2_key},
        "brand_tokens": {
            "primary_color": primary_color,
            "brand_name": brand_name,
            "watermark_text": "AI Generated | Adcreo",
        },
    }


class WorkerCompose:
    """
    Assembles the 15s fractional render.
    MVP pattern: Hook(3s) + I2V(9s) + CTA(3s)
    Applies LUT color grade based on product benefit.
    Burns SGI watermark per IT Rules 2026.
    No DB access. No state transitions.
    All temp files written to /tmp/{gen_id}_*.
    Cleanup runs in finally block — always executes.
    """

    def __init__(self, r2_client):
        self.r2_client = r2_client

    def _select_lut(self, benefit: str) -> Path:
        """
        Pure function. Maps benefit string to absolute LUT path.
        Falls back to DEFAULT_LUT for unknown benefit.
        Returns absolute Path object.
        LUT files live at backend/app/luts/*.cube
        """
        filename = BENEFIT_LUT_MAP.get(benefit, DEFAULT_LUT)
        return LUT_DIR / filename

    def _get_temp_path(self, gen_id: str, suffix: str) -> str:
        """
        Returns /tmp/{gen_id}_{suffix} string.
        e.g. _get_temp_path("abc-123", "hook.mp4")
             → "/tmp/abc-123_hook.mp4"
        """
        return f"/tmp/{gen_id}_{suffix}"

    def _cleanup_temp_files(self, paths: list[str]) -> None:
        """
        Deletes all temp files in paths list.
        Silently ignores missing files.
        Called in finally block — must never raise.
        """
        for path in paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                logger.warning(f"Temp cleanup failed for {path}: {e}")

    def _build_filter_graph(
        self,
        ir: dict,
        local_paths: dict,
        lut_path: str,
    ) -> tuple[str, list[str]]:
        """
        Builds FFmpeg filter_complex from IR segments.
        Handles 3-segment and 4-segment templates.
        Returns (filter_graph_string, ffmpeg_inputs_list).

        local_paths keys: segment index as string → local file path
        e.g. {"0": "/tmp/gen_hook.mp4", "1": "/tmp/gen_i2v.mp4", ...}
        Keys present only for broll and i2v segments (not color_card).
        TTS is always the LAST input.
        """
        W, H = 1080, 1920
        font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        brand    = ir["brand_tokens"]
        segments = ir["segments"]
        watermark = brand["watermark_text"].replace("'", "\u2019")
        primary_hex = brand["primary_color"].lstrip("#")

        parts        = []
        ffmpeg_inputs = []
        seg_labels   = []   # final scaled+overlay label per segment
        input_idx    = 0    # tracks -i input file index

        for i, seg in enumerate(segments):
            source     = seg["source"]
            duration_s = seg["duration_s"]
            raw_label  = f"seg{i}_raw"
            scaled_label = f"seg{i}_scaled"
            final_label  = f"seg{i}_v"

            # ── Build video source for this segment ──
            if source in ("broll", "i2v"):
                ffmpeg_inputs += ["-i", local_paths[str(i)]]
                parts.append(
                    f"[{input_idx}:v]fps=30,"
                    f"scale={W}:{H}:"
                    f"force_original_aspect_ratio=decrease,"
                    f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,"
                    f"tpad=stop_mode=clone:"
                    f"stop_duration="
                    f"{max(0.0, duration_s - 0.1):.3f},"
                    f"trim=end={duration_s:.3f},"
                    f"setsar=1[{scaled_label}]"
                )
                input_idx += 1
            elif source == "color_card":
                # lavfi color source — no input file needed
                parts.append(
                    f"color=c=#{primary_hex}:"
                    f"s={W}x{H}:d={duration_s:.3f},"
                    f"fps=30,setsar=1[{scaled_label}]"
                )

            # ── Add overlay if segment has overlay_text ──
            overlay_text  = seg.get("overlay_text")
            brand_text    = seg.get("brand_text")
            overlay_style = seg.get("overlay", "none")

            if overlay_text and overlay_style != "none":
                style = OVERLAY_STYLES.get(overlay_style,
                                           OVERLAY_STYLES["none"])
                y_expr, font_size, font_color = style

                if y_expr is not None:
                    safe_text = overlay_text.replace("'", "\u2019")
                    parts.append(
                        f"[{scaled_label}]drawtext="
                        f"text='{safe_text}':"
                        f"fontfile={font}:"
                        f"fontsize={font_size}:"
                        f"fontcolor={font_color}:"
                        f"x=(w-text_w)/2:y={y_expr}:"
                        f"shadowcolor=black@0.8:"
                        f"shadowx=2:shadowy=2[{raw_label}]"
                    )

                    # Brand name below CTA text
                    if brand_text:
                        safe_brand = brand_text.replace(
                            "'", "\u2019")[:30]
                        parts.append(
                            f"[{raw_label}]drawtext="
                            f"text='{safe_brand}':"
                            f"fontfile={font}:"
                            f"fontsize=30:fontcolor=white:"
                            f"x=(w-text_w)/2:y=h-120:"
                            f"shadowcolor=black@0.6:"
                            f"shadowx=1:shadowy=1[{final_label}]"
                        )
                    else:
                        # Rename raw_label to final_label
                        parts[-1] = parts[-1].replace(
                            f"[{raw_label}]", f"[{final_label}]"
                        )
                else:
                    # overlay style is "none" — pass through
                    parts.append(
                        f"[{scaled_label}]null[{final_label}]"
                    )
            else:
                # No overlay — pass through directly
                parts.append(
                    f"[{scaled_label}]null[{final_label}]"
                )

            seg_labels.append(f"[{final_label}]")

        # ── TTS audio input (always last) ──
        tts_input_idx = input_idx
        ffmpeg_inputs += ["-i", local_paths["tts"]]

        # ── Concat all segments ──
        n = len(segments)
        concat_inputs = "".join(seg_labels)
        parts.append(
            f"{concat_inputs}concat=n={n}:v=1:a=0[concat_v]"
        )

        # ── LUT color grade ──
        parts.append(f"[concat_v]lut3d={lut_path}[graded_v]")

        # ── SGI watermark — always present, bottom-left ──
        safe_watermark = watermark.replace("'", "\u2019")
        parts.append(
            f"[graded_v]drawtext="
            f"text='{safe_watermark}':"
            f"fontsize=22:fontcolor=white@0.85:"
            f"x=20:y=h-44[final_v]"
        )

        # ── Audio pad/trim ──
        parts.append(
            f"[{tts_input_idx}:a]"
            f"atrim=end=15.0,apad=whole_dur=15.0[padded_a]"
        )

        return ";\n".join(parts), ffmpeg_inputs

    def _build_ffmpeg_cmd(
        self,
        inputs: list[str],
        output_path: str,
        filter_graph: str,
    ) -> list[str]:
        return [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", filter_graph,
            "-map", "[final_v]",
            "-map", "[padded_a]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-r", "30",
            "-t", "15",
            output_path,
        ]

    async def _probe_duration(self, file_path: str) -> float:
        """
        Uses ffprobe to get video/audio duration in seconds.
        Returns float duration.
        On failure → raise ComposeError.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffprobe",
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise ComposeError(
                    f"ffprobe non-zero exit for {file_path}: "
                    f"{stderr.decode().strip()}"
                )
            return float(stdout.decode().strip())
        except ComposeError:
            raise
        except Exception as e:
            raise ComposeError(f"ffprobe failed: {e}") from e

    async def process(
        self,
        gen_id: str,
        i2v_r2_key: str,
        tts_r2_key: str,
        strategy_card: dict,
        b_roll_plan: list[dict],
        brand_profile: dict,
        plan_tier: str,
    ) -> str:
        """
        Assembles 15s MP4: Hook(3s) + I2V(9s) + CTA(3s) + TTS audio.
        Applies LUT color grade + SGI watermark.
        Uploads result to R2. Returns R2 key string.

        strategy_card  — Phase 3 strategy output (contains benefit, etc.)
        brand_profile  — User brand identity tokens from users table.
        b_roll_plan[0] = hook clip dict (r2_url = R2 object key)
        b_roll_plan[1] = cta clip dict  (r2_url = R2 object key)

        Raises ComposeError on any unrecoverable failure.
        Raises ComposeDurationError if segment durations out of bounds.
        Temp files always cleaned up in finally block.
        """
        # ── Step 0: Build Timeline IR ──────────────────────────
        ir = build_timeline_ir(
            gen_id, i2v_r2_key, tts_r2_key,
            strategy_card, b_roll_plan, brand_profile
        )
        logger.info(
            f"[compose] IR gen={gen_id} "
            f"template={ir['template_key']} "
            f"segments={len(ir['segments'])}: "
            f"{json.dumps(ir)}"
        )

        brand = ir["brand_tokens"]
        segments = ir["segments"]

        # ── Temp paths ─────────────────────────────────────────
        output_path = self._get_temp_path(gen_id, "preview.mp4")
        tts_path    = self._get_temp_path(gen_id, "tts.mp3")
        temp_files  = [output_path, tts_path]

        # local_paths: segment index → local file path
        # "tts" → tts local path
        local_paths: dict[str, str] = {"tts": tts_path}

        for i, seg in enumerate(segments):
            if seg["source"] in ("broll", "i2v"):
                ext = "mp4"
                p   = self._get_temp_path(gen_id, f"seg{i}.{ext}")
                local_paths[str(i)] = p
                temp_files.append(p)

        try:
            # ── Step 1: Download assets concurrently ───────────
            bucket = os.environ["R2_BUCKET_NAME"]

            async def download_and_write(
                r2_key: str, local_path: str
            ) -> None:
                resp = await asyncio.to_thread(
                    self.r2_client.get_object,
                    Bucket=bucket, Key=r2_key,
                )
                data = resp["Body"].read()
                await asyncio.to_thread(
                    Path(local_path).write_bytes, data
                )

            downloads = [
                download_and_write(
                    ir["audio"]["r2_key"], tts_path
                )
            ]
            for i, seg in enumerate(segments):
                if seg["source"] in ("broll", "i2v"):
                    downloads.append(
                        download_and_write(
                            seg["r2_key"], local_paths[str(i)]
                        )
                    )

            await asyncio.gather(*downloads)
            logger.info(
                f"[compose] Downloads done gen={gen_id} "
                f"count={len(downloads)}"
            )

            # ── Step 2: Probe I2V duration only ────────────────
            i2v_seg_idx = next(
                i for i, s in enumerate(segments)
                if s["source"] == "i2v"
            )
            i2v_dur = await self._probe_duration(
                local_paths[str(i2v_seg_idx)]
            )
            if i2v_dur > MAX_SEGMENT_DURATION_S:
                raise ComposeDurationError(
                    f"I2V duration {i2v_dur:.1f}s exceeds "
                    f"max {MAX_SEGMENT_DURATION_S}s gen={gen_id}"
                )

            # Patch i2v segment duration with actual probed value
            # (template says 9 or 10, actual clip may differ)
            segments[i2v_seg_idx]["duration_s"] = min(
                i2v_dur, segments[i2v_seg_idx]["duration_s"]
            )

            # ── Step 3: Build filter graph ──────────────────────
            benefit  = strategy_card.get("benefit", "natural")
            lut_path_obj = self._select_lut(benefit)
            lut_str  = str(lut_path_obj).replace(os.sep, "/")

            filter_graph, ffmpeg_video_inputs = (
                self._build_filter_graph(ir, local_paths, lut_str)
            )

            # ── Step 4: Build full FFmpeg command ───────────────
            cmd = self._build_ffmpeg_cmd(
                ffmpeg_video_inputs, output_path, filter_graph
            )
            logger.info(
                f"[compose] FFmpeg start gen={gen_id} "
                f"template={ir['template_key']} "
                f"lut={lut_path_obj.name}"
            )

            # ── Step 5: Run FFmpeg ──────────────────────────────
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            if proc.returncode != 0:
                raise ComposeError(
                    f"FFmpeg failed gen={gen_id} "
                    f"rc={proc.returncode}: "
                    f"{stderr.decode()[:800]}"
                )
            logger.info(f"[compose] FFmpeg done gen={gen_id}")

            # ── Step 6: Upload to R2 ────────────────────────────
            r2_key        = f"{gen_id}/compose/preview_15s.mp4"
            preview_bytes = await asyncio.to_thread(
                Path(output_path).read_bytes
            )
            await asyncio.to_thread(
                self.r2_client.put_object,
                Bucket=bucket,
                Key=r2_key,
                Body=preview_bytes,
                ContentType="video/mp4",
            )
            logger.info(
                f"[compose] Uploaded gen={gen_id} key={r2_key}"
            )
            return r2_key

        except (ComposeError, ComposeDurationError):
            raise
        except Exception as e:
            raise ComposeError(
                f"Compose unexpected error gen={gen_id}: {e}"
            ) from e
        finally:
            self._cleanup_temp_files(temp_files)
