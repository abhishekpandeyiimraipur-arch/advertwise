import pytest
import uuid
import json
from httpx import AsyncClient

from tests.integration.conftest import (
    make_client,
    seed_generation,
    get_generation_row,
    set_regenerate_count,
    TEST_USER_STARTER_ID,
    TEST_USER_PAID_ID,
    TEST_USER_BROKE_ID,
)



# ══════════════════════════════════════════════════════════════
# AC-3 TESTS — Co-Pilot Chat Invariants
# ══════════════════════════════════════════════════════════════

class TestChatGuards:
    """
    AC-3: Co-Pilot chat boundary enforcement.
    Tests the guard layers WITHOUT requiring real LLM calls.
    """

    @pytest.mark.asyncio
    async def test_chat_turn_limit_enforced(self):
        """
        AC-3 #1: After 3 turns, 4th call must return 429 ECM-008.
        Seed a generation that already has 3 turns used.
        """
        print("\n[TEST] chat_turn_limit_enforced")

        # Seed generation with all 3 turns already used
        gen_id = seed_generation(
            user_id=TEST_USER_PAID_ID,
            status="scripts_ready",
            chat_turns_used=3,
        )
        print(f"  [STEP 1] Seeded gen_id={gen_id} with chat_turns_used=3  OK")

        async with make_client(TEST_USER_PAID_ID, "paid@advertwise.in") as client:
            response = await client.post(
                f"/api/generations/{gen_id}/chat",
                json={"message": "Make it more emotional"},
                headers={"Idempotency-Key": str(uuid.uuid4())},
            )

        print(f"  [STEP 2] POST /chat → {response.status_code}")
        print(f"  [STEP 3] Response: {response.json()}")

        assert response.status_code == 429, (
            f"Expected 429 on 4th turn, got {response.status_code}"
        )
        assert response.json()["detail"]["error_code"] == "ECM-008"
        print("  [RESULT] ✅ 4th turn correctly blocked with ECM-008")

    @pytest.mark.asyncio
    async def test_chat_wrong_state_blocked(self):
        """
        AC-3: /chat must 409 if status != scripts_ready.
        Tests that FSM state guard fires before any processing.
        """
        print("\n[TEST] chat_wrong_state_blocked")

        # Seed generation in brief_ready — wrong state for chat
        gen_id = seed_generation(
            user_id=TEST_USER_PAID_ID,
            status="brief_ready",
            chat_turns_used=0,
        )
        print(f"  [STEP 1] Seeded gen_id={gen_id} with status=brief_ready  OK")

        async with make_client(TEST_USER_PAID_ID, "paid@advertwise.in") as client:
            response = await client.post(
                f"/api/generations/{gen_id}/chat",
                json={"message": "Make it more emotional"},
                headers={"Idempotency-Key": str(uuid.uuid4())},
            )

        print(f"  [STEP 2] POST /chat → {response.status_code}")
        print(f"  [STEP 3] Response: {response.json()}")

        assert response.status_code == 409
        assert response.json()["detail"]["error_code"] == "ECM-012"
        print("  [RESULT] ✅ Wrong state correctly blocked with ECM-012")

    @pytest.mark.asyncio
    async def test_chat_ownership_enforced(self):
        """
        AC-3: /chat must 404 if gen_id belongs to different user.
        Tests user ownership guard.
        """
        print("\n[TEST] chat_ownership_enforced")

        # Seed generation owned by PAID user
        gen_id = seed_generation(
            user_id=TEST_USER_PAID_ID,
            status="scripts_ready",
            chat_turns_used=0,
        )
        print(f"  [STEP 1] Seeded gen_id={gen_id} owned by PAID user  OK")

        # Try to access it as STARTER user
        async with make_client(
            TEST_USER_STARTER_ID, "test@advertwise.in"
        ) as client:
            response = await client.post(
                f"/api/generations/{gen_id}/chat",
                json={"message": "Make it more emotional"},
                headers={"Idempotency-Key": str(uuid.uuid4())},
            )

        print(f"  [STEP 2] POST /chat as wrong user → {response.status_code}")

        assert response.status_code == 404
        print("  [RESULT] ✅ Ownership correctly enforced — 404 for wrong user")


# ══════════════════════════════════════════════════════════════
# AC-4 TESTS — Approve Strategy Guards
# ══════════════════════════════════════════════════════════════

class TestApproveStrategyGuards:
    """
    AC-4: /approve-strategy boundary enforcement.
    Tests guard layers — starter block, wrong state, ownership.
    """

    @pytest.mark.asyncio
    async def test_starter_plan_blocked(self):
        """
        AC-3 #5 / AC-4: Starter plan must get 403 ECM-006.
        Starter users cannot render — must upgrade first.
        """
        print("\n[TEST] starter_plan_blocked")

        # Seed generation in strategy_preview for STARTER user
        gen_id = seed_generation(
            user_id=TEST_USER_STARTER_ID,
            status="strategy_preview",
            chat_turns_used=3,
        )
        print(f"  [STEP 1] Seeded gen_id={gen_id} for STARTER user  OK")

        async with make_client(
            TEST_USER_STARTER_ID, "test@advertwise.in"
        ) as client:
            response = await client.post(
                f"/api/generations/{gen_id}/approve-strategy",
                headers={"Idempotency-Key": str(uuid.uuid4())},
            )

        print(f"  [STEP 2] POST /approve-strategy → {response.status_code}")
        print(f"  [STEP 3] Response: {response.json()}")

        assert response.status_code == 403
        assert response.json()["detail"]["error_code"] == "ECM-006"
        print("  [RESULT] ✅ Starter correctly blocked with ECM-006")

    @pytest.mark.asyncio
    async def test_approve_strategy_wrong_state(self):
        """
        AC-4: /approve-strategy must 409 if status != strategy_preview.
        """
        print("\n[TEST] approve_strategy_wrong_state")

        # Seed generation in scripts_ready — wrong state
        gen_id = seed_generation(
            user_id=TEST_USER_PAID_ID,
            status="scripts_ready",
            chat_turns_used=3,
        )
        print(f"  [STEP 1] Seeded gen_id={gen_id} with status=scripts_ready  OK")

        async with make_client(
            TEST_USER_PAID_ID, "paid@advertwise.in"
        ) as client:
            response = await client.post(
                f"/api/generations/{gen_id}/approve-strategy",
                headers={"Idempotency-Key": str(uuid.uuid4())},
            )

        print(f"  [STEP 2] POST /approve-strategy → {response.status_code}")

        assert response.status_code == 409
        assert response.json()["detail"]["error_code"] == "ECM-012"
        print("  [RESULT] ✅ Wrong state correctly blocked with ECM-012")


# ══════════════════════════════════════════════════════════════
# AC-3 TESTS — Regenerate Limit
# ══════════════════════════════════════════════════════════════

class TestRegenerateGuards:
    """
    Regenerate boundary enforcement.
    Max 2 regenerations per generation.
    """

    @pytest.mark.asyncio
    async def test_regenerate_limit_enforced(self):
        """
        After 2 regenerations, 3rd must return 429 ECM-008.
        """
        print("\n[TEST] regenerate_limit_enforced")

        gen_id = seed_generation(
            user_id=TEST_USER_PAID_ID,
            status="scripts_ready",
            chat_turns_used=3,
        )
        # Manually set regenerate_count to 2 (at limit)
        set_regenerate_count(gen_id, 2)
        print(f"  [STEP 1] Seeded gen_id={gen_id} with regenerate_count=2  OK")

        async with make_client(TEST_USER_PAID_ID, "paid@advertwise.in") as client:
            response = await client.post(
                f"/api/generations/{gen_id}/regenerate",
                json={"framework_hint": None},
                headers={"Idempotency-Key": str(uuid.uuid4())},
            )

        print(f"  [STEP 2] POST /regenerate → {response.status_code}")
        print(f"  [STEP 3] Response: {response.json()}")

        assert response.status_code == 429
        assert response.json()["detail"]["error_code"] == "ECM-008"
        print("  [RESULT] ✅ 3rd regeneration correctly blocked with ECM-008")


# ══════════════════════════════════════════════════════════════
# AC-3 TESTS — Edit-Back FSM Rewind
# ══════════════════════════════════════════════════════════════

class TestEditBackGuards:
    """
    Edit-back FSM rewind boundary enforcement.
    """

    @pytest.mark.asyncio
    async def test_editback_invalid_target_blocked(self):
        """
        /edit-back must 400 if target_status is not a valid rewind target.
        """
        print("\n[TEST] editback_invalid_target_blocked")

        gen_id = seed_generation(
            user_id=TEST_USER_PAID_ID,
            status="scripts_ready",
            chat_turns_used=3,
        )
        print(f"  [STEP 1] Seeded gen_id={gen_id}  OK")

        async with make_client(TEST_USER_PAID_ID, "paid@advertwise.in") as client:
            response = await client.post(
                f"/api/generations/{gen_id}/edit-back",
                json={"target_status": "funds_locked"},
                headers={"Idempotency-Key": str(uuid.uuid4())},
            )

        print(f"  [STEP 2] POST /edit-back → {response.status_code}")
        print(f"  [STEP 3] Response: {response.json()}")

        assert response.status_code == 400
        print("  [RESULT] ✅ Invalid rewind target correctly blocked with 400")

    @pytest.mark.asyncio
    async def test_editback_path_a_scripts_to_brief(self):
        """
        Path A: scripts_ready → brief_ready
        Assert status changes and downstream fields nulled.
        """
        print("\n[TEST] editback_path_a_scripts_to_brief")

        gen_id = seed_generation(
            user_id=TEST_USER_PAID_ID,
            status="scripts_ready",
            chat_turns_used=3,
        )
        print(f"  [STEP 1] Seeded gen_id={gen_id} status=scripts_ready  OK")

        async with make_client(TEST_USER_PAID_ID, "paid@advertwise.in") as client:
            response = await client.post(
                f"/api/generations/{gen_id}/edit-back",
                json={"target_status": "brief_ready"},
                headers={"Idempotency-Key": str(uuid.uuid4())},
            )

        print(f"  [STEP 2] POST /edit-back → {response.status_code}")
        print(f"  [STEP 3] Response: {response.json()}")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "brief_ready"
        assert body["previous_status"] == "scripts_ready"

        # Verify DB state
        row = get_generation_row(gen_id)
        print(f"  [STEP 4] DB status={row['status']} safe_scripts={row['safe_scripts']}  OK")
        assert str(row["status"]) == "brief_ready"
        assert row["safe_scripts"] is None
        assert row["refined_script"] is None
        print("  [RESULT] ✅ Path A rewind correct — status=brief_ready, fields nulled")

    @pytest.mark.asyncio
    async def test_editback_forward_transition_blocked(self):
        """
        Edit-back must never allow forward transitions.
        brief_ready → scripts_ready must 409.
        """
        print("\n[TEST] editback_forward_transition_blocked")

        gen_id = seed_generation(
            user_id=TEST_USER_PAID_ID,
            status="brief_ready",
            chat_turns_used=0,
        )
        print(f"  [STEP 1] Seeded gen_id={gen_id} status=brief_ready  OK")

        async with make_client(TEST_USER_PAID_ID, "paid@advertwise.in") as client:
            response = await client.post(
                f"/api/generations/{gen_id}/edit-back",
                json={"target_status": "scripts_ready"},
                headers={"Idempotency-Key": str(uuid.uuid4())},
            )

        print(f"  [STEP 2] POST /edit-back → {response.status_code}")

        assert response.status_code == 409
        print("  [RESULT] ✅ Forward transition correctly blocked with 409")


# ══════════════════════════════════════════════════════════════
# GATE 3 SUMMARY TEST — runs last
# ══════════════════════════════════════════════════════════════

class TestGate3Summary:

    @pytest.mark.asyncio
    async def test_gate3_invariants_summary(self):
        """
        Summary assertion — verifies DB schema has all Gate 3 columns.
        If this passes, the migration and schema are correct.
        """
        print("\n[TEST] gate3_invariants_summary")

        conn = await get_conn()
        try:
            cols = await conn.fetch("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='generations'
                AND column_name IN (
                    'chat_turns_used', 'regenerate_count',
                    'refined_script', 'strategy_card',
                    'pre_topup_status', 'chat_history'
                )
                ORDER BY column_name
            """)
        finally:
            await conn.close()
        found = [r["column_name"] for r in cols]
        print(f"  [STEP 1] Gate 3 columns found: {found}")

        expected = sorted([
            "chat_turns_used", "regenerate_count",
            "refined_script", "strategy_card",
            "pre_topup_status", "chat_history"
        ])
        assert sorted(found) == expected, (
            f"Missing columns: {set(expected) - set(found)}"
        )
        print("  [RESULT] ✅ All Gate 3 schema columns present")
