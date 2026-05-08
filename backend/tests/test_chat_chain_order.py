import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass
from app.workers.copilot import CopilotChain, CopilotResult, CopilotChainError
from app.types.script import Script

@pytest.fixture
def mock_script():
    """Minimal valid Script for testing."""
    return Script(
        hook="Test hook",
        body="Product benefit",
        cta="Buy now",
        full_text="Test hook. Product benefit. Buy now.",
        word_count=8,
        language_mix="en",
        framework="pas_micro",
        framework_angle="problem_agitation",
        framework_rationale="Strong problem-solution fit for test",
        evidence_note="test",
        suggested_tone="energetic",
    )

@pytest.fixture
def mock_deps(mock_script):
    """
    Returns a dict of all mocked CopilotChain dependencies.
    Default: all stages pass, LLM returns mock_script.
    """
    compliance = AsyncMock()
    compliance.check_input.return_value = MagicMock(safe=True)

    cost_guard = AsyncMock()
    cost_guard.pre_check.return_value = MagicMock(ok=True)
    cost_guard.record = AsyncMock()

    gateway = MagicMock()
    gateway.last_call_cost = 0.06
    gateway.last_model_used = "deepseek-chat"

    output_guard = AsyncMock()
    output_guard.check_output.return_value = MagicMock(safe=True)

    copy_worker = AsyncMock()
    copy_worker.refine = AsyncMock(return_value=mock_script)

    db = AsyncMock()
    db.execute = AsyncMock()

    prompt_catalog = MagicMock()

    return {
        "gateway": gateway,
        "compliance_gate": compliance,
        "cost_guard": cost_guard,
        "output_guard": output_guard,
        "prompt_catalog": prompt_catalog,
        "db": db,
        "copy_worker": copy_worker,
    }

@pytest.fixture
def chain(mock_deps):
    return CopilotChain(
        gateway=mock_deps["gateway"],
        compliance_gate=mock_deps["compliance_gate"],
        cost_guard=mock_deps["cost_guard"],
        output_guard=mock_deps["output_guard"],
        prompt_catalog=mock_deps["prompt_catalog"],
        db=mock_deps["db"],
    )

def make_run_args(mock_script):
    return dict(
        gen_id="test-gen-123",
        message="Make it more emotional",
        current_script=mock_script,
        product_brief={"category": "skincare"},
        tts_language="en",
        plan_tier="starter",
    )

@pytest.mark.asyncio
async def test_chain_success_stage_order(chain, mock_deps, mock_script):
    """
    On success, stages_traversed must be exactly:
    ["compliance_gate", "cost_guard_pre", "llm_refine",
     "cost_guard_record", "output_guard"]
    in that exact order. This is the CI-critical invariant.
    """
    # Patch WorkerCopy so it uses our mock
    import app.workers.copilot as copilot_module
    original = copilot_module.WorkerCopy
    
    class MockWorkerCopy:
        def __init__(self, **kwargs): pass
        async def refine(self, *args, **kwargs):
            return mock_script
    
    copilot_module.WorkerCopy = MockWorkerCopy
    
    try:
        result = await chain.run(**make_run_args(mock_script))
    finally:
        copilot_module.WorkerCopy = original

    assert isinstance(result, CopilotResult)
    assert result.stages_traversed == [
        "compliance_gate",
        "cost_guard_pre",
        "llm_refine",
        "cost_guard_record",
        "output_guard",
    ]

@pytest.mark.asyncio
async def test_cost_record_fires_before_output_guard(chain, mock_deps, mock_script):
    """
    Even when OutputGuard rejects, cost_guard.record must have
    already been called. This is the rejected-turn-leak fix (F-603).
    """
    call_order = []

    mock_deps["cost_guard"].record = AsyncMock(
        side_effect=lambda *a, **kw: call_order.append("cost_record")
    )
    mock_deps["output_guard"].check_output = AsyncMock(
        side_effect=lambda *a, **kw: call_order.append("output_guard") 
        or MagicMock(safe=False)
    )

    import app.workers.copilot as copilot_module
    original = copilot_module.WorkerCopy

    class MockWorkerCopy:
        def __init__(self, **kwargs): pass
        async def refine(self, *args, **kwargs):
            return mock_script

    copilot_module.WorkerCopy = MockWorkerCopy

    try:
        result = await chain.run(**make_run_args(mock_script))
    finally:
        copilot_module.WorkerCopy = original

    # cost_record MUST appear before output_guard in call order
    assert "cost_record" in call_order
    assert "output_guard" in call_order
    assert call_order.index("cost_record") < call_order.index("output_guard")
    assert isinstance(result, CopilotChainError)
    assert result.error_code == "ECM-010"

@pytest.mark.asyncio
async def test_compliance_gate_blocks_before_spend(chain, mock_deps, mock_script):
    """
    If ComplianceGate rejects, cost_guard.pre_check must never be called.
    Zero spend on blocked input.
    """
    mock_deps["compliance_gate"].check_input.return_value = MagicMock(safe=False)

    result = await chain.run(**make_run_args(mock_script))

    assert isinstance(result, CopilotChainError)
    assert result.error_code == "ECM-011"
    assert result.stage == "compliance_gate"
    mock_deps["cost_guard"].pre_check.assert_not_called()
    mock_deps["cost_guard"].record.assert_not_called()

@pytest.mark.asyncio
async def test_cost_guard_pre_blocks_before_llm(chain, mock_deps, mock_script):
    """
    If CostGuard.pre_check fails (ceiling hit), no LLM call is made.
    """
    mock_deps["cost_guard"].pre_check.return_value = MagicMock(ok=False)

    import app.workers.copilot as copilot_module
    original = copilot_module.WorkerCopy
    llm_called = []

    class MockWorkerCopy:
        def __init__(self, **kwargs): pass
        async def refine(self, *args, **kwargs):
            llm_called.append(True)
            return mock_script

    copilot_module.WorkerCopy = MockWorkerCopy

    try:
        result = await chain.run(**make_run_args(mock_script))
    finally:
        copilot_module.WorkerCopy = original

    assert isinstance(result, CopilotChainError)
    assert result.error_code == "ECM-009"
    assert len(llm_called) == 0
    mock_deps["cost_guard"].record.assert_not_called()
