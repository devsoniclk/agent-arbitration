"""
Autonomous Agent DAO Governance & SLA Dispute Arbitration Swarm Demo.
"""

from __future__ import annotations
import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent_arbitration.engine import AgentArbitrationEngine
from agent_arbitration.types import AgentRole, SlaAgreement, SlaExecutionTrace


def main():
    print("======================================================================")
    print("AUTONOMOUS AGENT DAO GOVERNANCE & SLA ARBITRATION SWARM SIMULATION")
    print("======================================================================")

    engine = AgentArbitrationEngine(treasury_balance=100_000.0, min_stake=2_000.0)

    # 1. Register agents
    print("[1] Registering Swarm Agents...")
    engine.register_agent("alpha_orchestrator", "pk_alpha", AgentRole.ORCHESTRATOR, 10_000.0, 0.99)
    engine.register_agent("beta_worker", "pk_beta", AgentRole.SWARM_WORKER, 2_500.0, 0.92)
    engine.register_agent("gamma_worker", "pk_gamma", AgentRole.SWARM_WORKER, 2_500.0, 0.88)
    engine.register_agent("juror_solon", "pk_solon", AgentRole.TRIBUNAL_JUROR, 5_000.0, 0.98)
    engine.register_agent("juror_themis", "pk_themis", AgentRole.TRIBUNAL_JUROR, 5_000.0, 0.97)

    print(f"    Active swarm agents: {len(engine.agents)}")
    print(f"    Total active voting power: {engine.registry.total_active_voting_power():.2f}")

    # 2. Resource Allocation Proposal & Quadratic Voting
    print("\n[2] Submitting DAO Treasury Resource Allocation Proposal...")
    engine.create_resource_proposal(
        proposal_id="prop_gpu_sublease",
        creator_id="alpha_orchestrator",
        requested_amount=20_000.0,
        title="Sublease H100 GPU Cluster",
        description="Expand parallel compute capability for real-time model synthesis.",
    )
    prop = engine.proposals["prop_gpu_sublease"]
    print(f"    Dynamic Risk Quorum Calibrated: {prop.target_quorum * 100:.1f}%")

    print("\n[3] Casting Non-Collusive Quadratic Votes...")
    engine.cast_quadratic_vote("prop_gpu_sublease", "alpha_orchestrator", credits_allocated=400.0, vote_yes=True)
    engine.cast_quadratic_vote("prop_gpu_sublease", "beta_worker", credits_allocated=100.0, vote_yes=True)
    engine.cast_quadratic_vote("prop_gpu_sublease", "gamma_worker", credits_allocated=100.0, vote_yes=True)
    engine.cast_quadratic_vote("prop_gpu_sublease", "juror_solon", credits_allocated=100.0, vote_yes=True)

    passed, status, msg = engine.evaluate_proposal("prop_gpu_sublease", finalize=True)
    print(f"    Proposal Evaluation: {status.value} (YES: {prop.yes_weight:.2f}, NO: {prop.no_weight:.2f})")
    engine.execute_proposal("prop_gpu_sublease")
    print(f"    Treasury Balance after execution: ${engine.treasury_balance:,.2f}")

    # 3. SLA Contract & Escrow Locking
    print("\n[4] Registering Programmatic SLA Contract with Escrow Lock...")
    sla = SlaAgreement(
        sla_id="sla_code_synthesis_01",
        client_id="alpha_orchestrator",
        provider_id="beta_worker",
        max_latency_ms=450.0,
        min_accuracy_threshold=0.92,
        allowed_tools={"ast_parser", "symbolic_eval"},
        escrow_amount=2_000.0,
        expiry_timestamp=time.time() + 3600.0,
    )
    engine.register_sla(sla)
    print(f"    SLA '{sla.sla_id}' registered. Escrow locked: ${sla.escrow_amount:,.2f}")

    # 4. Dispute Initiation & Execution Trace Audit
    print("\n[5] Dispute Triggered by Client (Latency & Tool Invariant Breach)...")
    engine.initiate_dispute(
        dispute_id="disp_sla_01",
        sla_id="sla_code_synthesis_01",
        claimant_id="alpha_orchestrator",
        claim_reason="Worker exceeded 450ms latency SLA and invoked forbidden tool.",
        dispute_bond=400.0,  # 20% > 10%
    )

    breach_trace = SlaExecutionTrace(
        trace_id="trace_breach_beta",
        sla_id="sla_code_synthesis_01",
        execution_time_ms=820.0,  # Breached!
        accuracy_metric=0.85,     # Breached!
        tools_called=["ast_parser", "unauthorized_socket"],  # Breached!
        execution_merkle_root=hashlib.sha256(b"breach_merkle_proof").hexdigest(),
        trace_signature="sig_ed25519_beta",
    )
    ok_trace, trace_msg = engine.submit_trace_evidence("disp_sla_01", breach_trace)
    print(f"    {trace_msg}")

    # 5. Tribunal Juror Consensus & Conflicted Disqualification
    print("\n[6] Tribunal Juror Deliberation & Voting...")
    ok_v1, _ = engine.cast_tribunal_juror_vote("disp_sla_01", "juror_solon", favor_claimant=True)
    ok_v2, _ = engine.cast_tribunal_juror_vote("disp_sla_01", "juror_themis", favor_claimant=True)
    conflict_v, c_msg = engine.cast_tribunal_juror_vote("disp_sla_01", "alpha_orchestrator", favor_claimant=True)
    print(f"    Conflicted party vote blocked: '{c_msg}'")

    # 6. Automated Slashing & Settlement
    print("\n[7] Resolving Tribunal Arbitration & Executing Slashing...")
    initial_provider_stake = engine.agents["beta_worker"].stake_balance
    settlement = engine.resolve_arbitration_and_slash("disp_sla_01")
    print(f"    Winner: {settlement['winner']}")
    print(f"    Slashed Stake Collected: ${settlement['slashed_penalty_collected']:,.2f} (25% of Escrow)")
    print(f"    Refunded Escrow: ${settlement['refunded_escrow']:,.2f}")
    print(f"    Provider Stake: ${initial_provider_stake:,.2f} -> ${engine.agents['beta_worker'].stake_balance:,.2f}")
    print(f"    Provider Reputation: {engine.agents['beta_worker'].reputation_score:.1f}/100.0")

    # 7. Cryptographic Witness DAG Verification
    print("\n[8] Verifying Cryptographic State Witness DAG Ledger...")
    is_valid = engine.verify_integrity()
    print(f"    Witness DAG chain length: {len(engine.witness_dag)} blocks")
    print(f"    State Root: {engine.state_root}")
    print(f"    Integrity Verified: {is_valid}")
    print("======================================================================")


if __name__ == "__main__":
    main()
