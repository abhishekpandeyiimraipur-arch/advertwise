"""
WorkerExport — Standalone ARQ job for C2PA-signed export.
[TDD-WORKERS]-H / [TDD-WORKERS]-J

Decoupled from phase4_coordinator. Enqueued exclusively by
/declaration and /retry-export routes.

Produces 2 signed export formats (square + vertical) from
preview_15s.mp4. C2PA signs both. Consumes 1 credit atomically
after all uploads succeed.
Unsigned videos are NEVER returned to client.
"""
import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from app.core.exceptions import C2PASignError, ExportPreconditionError

logger = logging.getLogger(__name__)

C2PA_SIGN_TIMEOUT_S   = 30.0
C2PA_VERIFY_TIMEOUT_S = 15.0
EXPORT_FORMATS = {
    "square":   "1080:1080",
    "vertical": "1080:1920",
}


class WorkerExport:
    """
    Standalone ARQ job — decoupled from phase4_coordinator.
    Produces 2 C2PA-signed export formats.
    Consumes 1 credit atomically after all uploads succeed.
    Unsigned videos are never returned to client.
    """

    def __init__(self, r2_client, redis_mgr, db_pool):
        self.r2_client  = r2_client
        self.redis_mgr  = redis_mgr
        self.db_pool    = db_pool
        self._last_manifest_hash: str = ""

    def _get_temp_path(self, gen_id: str, suffix: str) -> str:
        """Returns /tmp/{gen_id}_{suffix}"""
        return f"/tmp/{gen_id}_{suffix}"

    def _cleanup_temp_files(self, paths: list[str]) -> None:
        """
        Deletes temp files silently.
        Called in finally block — must never raise.
        """
        for path in paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                logger.warning(f"Temp cleanup failed {path}: {e}")

    def _build_manifest(
        self,
        gen_id: str,
        user_id: str,
    ) -> str:
        """
        Builds C2PA manifest JSON string, writes to temp file.
        Sets self._last_manifest_hash to SHA-256 of the manifest.
        Returns the manifest file path string.
        On failure → raise C2PASignError.
        """
        try:
            manifest = {
                "ta_url": "https://timestamp.digicert.com",
                "claim_generator": "AdvertWise/1.0",
                "assertions": [
                    {
                        "label": "c2pa.actions",
                        "data": {
                            "actions": [
                                {
                                    "action": "c2pa.created",
                                    "softwareAgent": "AdvertWise AI v1.0",
                                    "parameters": {
                                        "gen_id":    gen_id,
                                        "user_id":   user_id,
                                        "timestamp": datetime.now(timezone.utc).isoformat(),
                                        "ai_model":  "AdvertWise-Pipeline-v1",
                                    },
                                }
                            ]
                        },
                    },
                    {
                        "label": "c2pa.training-mining",
                        "data": {
                            "entries": {
                                "c2pa.ai_generative_training": {
                                    "use": "notAllowed"
                                }
                            }
                        },
                    },
                ],
            }

            manifest_json = json.dumps(manifest, indent=2)
            manifest_path = self._get_temp_path(gen_id, "manifest.json")

            with open(manifest_path, "w") as f:
                f.write(manifest_json)

            self._last_manifest_hash = hashlib.sha256(
                manifest_json.encode()
            ).hexdigest()

            return manifest_path

        except Exception as e:
            raise C2PASignError(f"Manifest build failed: {e}") from e

    async def _ffmpeg_scale(
        self,
        input_path: str,
        output_path: str,
        scale: str,
    ) -> None:
        """
        Scales video to target resolution using FFmpeg.
        scale: "1080:1080" (square) or "1080:1920" (vertical)

        Square:   scale + crop to fill 1080x1080
        Vertical: scale + pad to fit within 1080x1920 with black bars

        On non-zero returncode → raise C2PASignError.
        """
        if scale == "1080:1080":
            vf = (
                "scale=1080:1080:force_original_aspect_ratio=increase,"
                "crop=1080:1080"
            )
        else:
            # 1080:1920 — vertical
            vf = (
                "scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black"
            )

        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "copy",
            output_path,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise C2PASignError(
                f"FFmpeg scale failed rc={proc.returncode}: "
                f"{stderr.decode()[:300]}"
            )

    async def _c2pa_sign(
        self,
        video_path: str,
        manifest_path: str,
        gen_id: str,
    ) -> str:
        """
        Signs video with c2patool. Returns signed output path.
        Verify is best-effort — non-fatal if it fails.
        On sign timeout or failure → raise C2PASignError.
        """
        output_path = video_path.replace(".mp4", "_signed.mp4")

        # ── Sign ────────────────────────────────────────────────
        try:
            proc = await asyncio.create_subprocess_exec(
                "c2patool", video_path,
                "--output", output_path,
                "--manifest", manifest_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=C2PA_SIGN_TIMEOUT_S
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            raise C2PASignError(
                f"c2patool sign timeout gen={gen_id}"
            )

        if proc.returncode != 0:
            raise C2PASignError(
                f"c2patool sign failed rc={proc.returncode}: "
                f"{stderr.decode()[:300]}"
            )

        # ── Verify (best-effort — non-fatal) ─────────────────────
        try:
            vproc = await asyncio.create_subprocess_exec(
                "c2patool", "--verify", output_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, vstderr = await asyncio.wait_for(
                vproc.communicate(), timeout=C2PA_VERIFY_TIMEOUT_S
            )
            if vproc.returncode != 0:
                logger.warning(
                    f"c2patool verify non-zero gen={gen_id} "
                    f"(non-fatal): {vstderr.decode()[:200]}"
                )
        except asyncio.TimeoutError:
            logger.warning(
                f"c2patool verify timeout gen={gen_id} (non-fatal)"
            )
        except Exception as e:
            logger.warning(
                f"c2patool verify error gen={gen_id} (non-fatal): {e}"
            )

        return output_path

    async def process(self, gen_id: str) -> None:
        """
        Standalone export pipeline.
        Reads from DB, scales, signs, uploads, consumes credit.
        Never returns unsigned video.
        Cleans up /tmp/ in finally block always.
        """

        # ── Step 1: Read generation row ──────────────────────────
        async with self.db_pool.acquire() as conn:
            gen = await conn.fetchrow(
                """SELECT gen_id, user_id, preview_url,
                          declaration_accepted, plan_tier,
                          export_retry_count
                   FROM generations
                   WHERE gen_id = $1
                     AND status = 'export_queued'""",
                gen_id,
            )

        if not gen:
            logger.warning(
                f"WorkerExport: gen={gen_id} not in "
                f"export_queued state — skipping (idempotent)"
            )
            return

        # ── Step 2: Precondition guards ───────────────────────────
        if not gen["declaration_accepted"]:
            raise ExportPreconditionError(
                f"Declaration not accepted gen={gen_id} — "
                f"cannot export unsigned"
            )

        user_id   = str(gen["user_id"])
        plan_tier = gen["plan_tier"]

        # ── Step 3: Derive R2 key from public URL ─────────────────
        r2_public_url = os.environ.get(
            "R2_PUBLIC_URL",
            "https://pub-dfacf0a5eece46e4ac8e5aaaf5da5368.r2.dev"
        )
        preview_r2_key = gen["preview_url"].replace(
            f"{r2_public_url}/", ""
        )

        # ── Step 4: Verify preview still exists in R2 ────────────
        try:
            await asyncio.to_thread(
                self.r2_client.head_object,
                Bucket=os.environ["R2_BUCKET_NAME"],
                Key=preview_r2_key,
            )
        except Exception:
            # Preview purged by retention sweep
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """UPDATE generations
                       SET status = 'failed_export',
                           updated_at = NOW()
                       WHERE gen_id = $1""",
                    gen_id,
                )
            raise ExportPreconditionError(
                f"Preview asset purged gen={gen_id} "
                f"(ECM-018) — start new generation"
            )

        # ── Temp file paths ───────────────────────────────────────
        preview_path  = self._get_temp_path(gen_id, "preview.mp4")
        square_path   = self._get_temp_path(gen_id, "square.mp4")
        vertical_path = self._get_temp_path(gen_id, "vertical.mp4")
        sq_signed     = self._get_temp_path(gen_id, "square_signed.mp4")
        vt_signed     = self._get_temp_path(gen_id, "vertical_signed.mp4")
        manifest_path = self._get_temp_path(gen_id, "manifest.json")
        temp_files    = [
            preview_path, square_path, vertical_path,
            sq_signed, vt_signed, manifest_path,
        ]

        try:
            # ── Step 5: Download preview from R2 ─────────────────
            bucket = os.environ["R2_BUCKET_NAME"]
            resp = await asyncio.to_thread(
                self.r2_client.get_object,
                Bucket=bucket,
                Key=preview_r2_key,
            )
            preview_bytes = resp["Body"].read()
            await asyncio.to_thread(
                Path(preview_path).write_bytes, preview_bytes
            )
            logger.info(
                f"WorkerExport: preview downloaded gen={gen_id}"
            )

            # ── Step 6: Scale to 2 formats ────────────────────────
            await asyncio.gather(
                self._ffmpeg_scale(
                    preview_path, square_path, "1080:1080"
                ),
                self._ffmpeg_scale(
                    preview_path, vertical_path, "1080:1920"
                ),
            )
            logger.info(
                f"WorkerExport: scaled 2 formats gen={gen_id}"
            )

            # ── Step 7: Build C2PA manifest ───────────────────────
            manifest_path = self._build_manifest(gen_id, user_id)

            # ── Step 8: C2PA sign both formats sequentially ───────
            # Sequential not parallel — c2patool is CPU-bound
            # and shares the same manifest file
            sq_signed = await self._c2pa_sign(
                square_path, manifest_path, gen_id
            )
            vt_signed = await self._c2pa_sign(
                vertical_path, manifest_path, gen_id
            )
            logger.info(
                f"WorkerExport: C2PA signed both formats "
                f"gen={gen_id} manifest_hash="
                f"{self._last_manifest_hash[:16]}..."
            )

            # ── Step 9: Upload signed formats to R2 ──────────────
            sq_r2_key = f"{gen_id}/export/square_1x1.mp4"
            vt_r2_key = f"{gen_id}/export/vertical_9x16.mp4"

            async def upload(local_path: str, r2_key: str):
                data = await asyncio.to_thread(
                    Path(local_path).read_bytes
                )
                await asyncio.to_thread(
                    self.r2_client.put_object,
                    Bucket=bucket,
                    Key=r2_key,
                    Body=data,
                    ContentType="video/mp4",
                )

            await asyncio.gather(
                upload(sq_signed, sq_r2_key),
                upload(vt_signed, vt_r2_key),
            )
            logger.info(
                f"WorkerExport: uploaded both formats gen={gen_id}"
            )

            # ── Step 10: Construct public download URLs ───────────
            sq_public_url = f"{r2_public_url}/{sq_r2_key}"
            vt_public_url = f"{r2_public_url}/{vt_r2_key}"

            exports_payload = {
                "square_url":         sq_public_url,
                "vertical_url":       vt_public_url,
                "c2pa_manifest_hash": self._last_manifest_hash,
                "finalized_at":       datetime.now(
                    timezone.utc
                ).isoformat(),
            }

            # ── Step 11: Atomic DB commit + wallet consume ────────
            # Order is non-negotiable:
            # 1. UPDATE generations → export_ready
            # 2. wallet_consume Lua → deduct credit
            # 3. UPDATE wallet_transactions → consumed
            async with self.db_pool.acquire() as conn:
                async with conn.transaction():

                    # 11a. Update generation row
                    await conn.execute(
                        """UPDATE generations
                           SET exports            = $2::jsonb,
                               c2pa_manifest_hash = $3,
                               status             = 'export_ready',
                               updated_at         = NOW()
                           WHERE gen_id = $1
                             AND status = 'export_queued'""",
                        gen_id,
                        json.dumps(exports_payload),
                        self._last_manifest_hash,
                    )

                    # 11b. Consume wallet lock via Lua script
                    result = await self.redis_mgr.db0.evalsha(
                        self.redis_mgr.wallet_consume_sha,
                        2,
                        f"wallet:{user_id}",
                        f"walletlock:{user_id}:{gen_id}",
                    )
                    if result == 0:
                        logger.warning(
                            f"WorkerExport: wallet lock already "
                            f"consumed gen={gen_id} user={user_id} "
                            f"— continuing (retry scenario)"
                        )

                    # 11c. Mark wallet transaction as consumed
                    await conn.execute(
                        """UPDATE wallet_transactions
                           SET status     = 'consumed',
                               updated_at = NOW()
                           WHERE gen_id = $1
                             AND type   = 'lock'
                             AND status = 'locked'""",
                        gen_id,
                    )

            logger.info(
                f"WorkerExport: DB committed + credit consumed "
                f"gen={gen_id}"
            )

            # ── Step 12: Style memory (post-MVP stub) ─────────────
            # TODO: upsert user_style_profiles after schema added
            # Skipped for MVP — table does not exist yet

            # ── Step 13: SSE push export_ready ────────────────────
            try:
                sse_key = f"sse:{gen_id}"
                sse_payload = json.dumps({
                    "type":  "state_change",
                    "state": "export_ready",
                    "exports": {
                        "square_url":   sq_public_url,
                        "vertical_url": vt_public_url,
                    },
                })
                await self.redis_mgr.db0.lpush(sse_key, sse_payload)
                await self.redis_mgr.db0.expire(sse_key, 300)
            except Exception as e:
                logger.warning(
                    f"WorkerExport: SSE push failed gen={gen_id}: {e}"
                )

            logger.info(
                f"WorkerExport: DONE gen={gen_id} "
                f"sq={sq_public_url} vt={vt_public_url}"
            )

        except (C2PASignError, ExportPreconditionError):
            raise  # propagate to DLQ → failed_export + refund

        except Exception as e:
            raise C2PASignError(
                f"WorkerExport unexpected error gen={gen_id}: {e}"
            ) from e

        finally:
            self._cleanup_temp_files(temp_files)


# ── Standalone ARQ entry point ────────────────────────────────────

async def worker_export(ctx: dict, gen_id: str) -> None:
    """
    ARQ job entry point for WorkerExport.
    Registered on phase4_workers queue.
    Instantiates WorkerExport from ctx and calls process().
    """
    exporter = WorkerExport(
        r2_client = ctx["r2_client"],
        redis_mgr = ctx["redis_mgr"],
        db_pool   = ctx["db_pool"],
    )
    await exporter.process(gen_id=gen_id)
