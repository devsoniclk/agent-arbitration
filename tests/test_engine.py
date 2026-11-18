"""
Integration tests for AgentArbitrationEngine.
"""

import hashlib
import time
from agent_arbitration.engine import AgentArbitrationEngine
from agent_arbitration.types import AgentRole, ProposalStatus, SlaAgreement, SlaExecutionTrace


def test_engine_full_workflow():
    engine = AgentArbitrationEngine(treasury_balance=100_000.0, min_stake=2_000.0)

    # 1. Register agents
    engine.register_agent("worker_alpha", "pk_a", AgentRole.SWARM_WORKER, 2500.0, 0.95)
    engine.register_agent("worker_beta", "pk_b", AgentRole.SWARM_WORKER, 2500.0, 0.90)
    engine.register_agent("juror_01", "pk_j", AgentRole.TRIBUNAL_JUROR, 5000.0, 0.98)

    assert len(engine.agents) == 3
    assert engine.treasury_balance == 100_000.0

    # 2. Deposit stake
    engine.deposit_stake("worker_alpha", 500.0)
    assert engine.agents["worker_alpha"].stake_balance == 3000.0

    # 3. Create proposal
    ok_p, _ = engine.create_resource_proposal(
        "p_alpha", "worker_alpha", 15_000.0, "Infrastructure expansion"
    )
    assert ok_p is True
    assert "p_alpha" in engine.proposals

    # 4. Cast quadratic votes
    engine.cast_quadratic_vote("p_alpha", "worker_alpha", 100.0, vote_yes=True)
    engine.cast_quadratic_vote("p_alpha", "worker_beta", 100.0, vote_yes=True)
    engine.cast_quadratic_vote("p_alpha", "juror_01", 100.0, vote_yes=True)

    # 5. Evaluate and execute
    passed, status, _ = engine.evaluate_proposal("p_alpha", finalize=True)
    assert passed is True
    assert status == ProposalStatus.PASSED

    ok_exec, _ = engine.execute_proposal("p_alpha")
    assert ok_exec is True
    assert engine.treasury_balance == 85_000.0

    # 6. SLA Agreement
    sla = SlaAgreement(
        "sla_engine_01",
        "worker_alpha",
        "worker_beta",
        400.0,
        0.90,
        {"model_inference"},
        2000.0,
        time.time() + 3600,
    )
    engine.register_sla(sla)
    assert "sla_engine_01" in engine.slas

    # 7. Dispute and Trace
    engine.initiate_dispute("disp_engine", "sla_engine_01", "worker_alpha", "Accuracy fail", 300.0)
    trace = SlaExecutionTrace(
        "tr_e",
        "sla_engine_01",
        300.0,
        0.70,  # Below 0.90 threshold
        ["model_inference"],
        hashlib.sha256(b"root").hexdigest(),
        "sig",
    )
    engine.submit_trace_evidence("disp_engine", trace)
    engine.cast_tribunal_juror_vote("disp_engine", "juror_01", favor_claimant=True)

    # 8. Settle
    res = engine.resolve_arbitration_and_slash("disp_engine")
    assert res["winner"] == "worker_alpha"
    assert res["slashed_penalty_collected"] == 500.0  # 25% of 2000.0

    # 9. Verify witness DAG
    assert engine.verify_integrity() is True
    assert len(engine.action_witness_dag) >= 9
