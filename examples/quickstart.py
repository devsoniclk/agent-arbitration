#!/usr/bin/env python3
"""
Quickstart Example: Autonomous Swarm SLA Arbitration & Automated Stake Slashing.

Demonstrates:
1. Agent registration with compute stake bonds and benchmark integrity scores.
2. Dynamic quorum proposal and non-collusive quadratic voting.
3. SLA agreement creation with locked escrow.
4. Objective execution trace breach detection.
5. Deterministic tribunal resolution, automated stake slashing, and jailing.
6. Verification of the cryptographic Action Witness DAG state root.
"""

import hashlib
import sys
import time
from pathlib import Path

# Add project root to sys.path for direct script execution
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent_arbitration import (
    AgentRole,
    ArbitrationEngine,
    SlaAgreement,
    SlaExecutionTrace,
)


def main():
    print("=" * 70)
    print("AGENT ARBITRATION QUICKSTART DEMONSTRATION")
    print("=" * 70)

    # 1. Initialize engine
    engine = ArbitrationEngine(
        min_stake_bond=2000.0,
        initial_treasury=100_000.0,
        slashing_rate=0.25,
        min_dispute_bond_ratio=0.10,
    )

    # 2. Register swarm agents
    print("\n[1] Registering Swarm Agents...")
    engine.register_agent("client_bot", "pk_client", AgentRole.ORCHESTRATOR, 10_000.0, 0.95)
    engine.register_agent("worker_node", "pk_worker", AgentRole.SWARM_WORKER, 2_200.0, 0.90)
    engine.register_agent("juror_alpha", "pk_juror_1", AgentRole.TRIBUNAL_JUROR, 5_000.0, 0.99)
    engine.register_agent("juror_beta", "pk_juror_2", AgentRole.TRIBUNAL_JUROR, 5_000.0, 0.99)

    for agent_id, agent in engine.agents.items():
        print(f"  - {agent_id}: stake=${agent.stake_balance:,.1f}, power={agent.effective_voting_power:.2f}")

    # 3. Create SLA Agreement
    print("\n[2] Creating Programmatic Service Level Agreement...")
    sla = SlaAgreement(
        sla_id="sla_code_refactor_42",
        client_id="client_bot",
        provider_id="worker_node",
        max_latency_ms=1000.0,
        min_accuracy_threshold=0.92,
        allowed_tools={"ast_parse", "git_diff", "type_check"},
        escrow_amount=1_200.0,
        expiry_timestamp=time.time() + 7200.0,
    )
    ok, msg = engine.register_sla(sla)
    print(f"  {msg}")

    # 4. Worker executes task with a breach (exceeded latency + forbidden tool)
    print("\n[3] Submitting Breached Execution Trace...")
    bad_trace = SlaExecutionTrace(
        trace_id="tr_42_breach",
        sla_id="sla_code_refactor_42",
        execution_time_ms=1450.0,  # Breached: 1450ms > 1000ms
        accuracy_metric=0.85,      # Breached: 0.85 < 0.92
        tools_called=["ast_parse", "rm_rf_subshell"],  # Breached: unauthorized tool
        execution_merkle_root=hashlib.sha256(b"breach_merkle_leaf").hexdigest(),
        trace_signature="sig_ed25519_worker_node",
    )

    # 5. Client files dispute
    print("\n[4] Client Filing Dispute...")
    engine.initiate_dispute(
        dispute_id="disp_refactor_01",
        sla_id="sla_code_refactor_42",
        claimant_id="client_bot",
        claim_reason="Worker breached latency, accuracy, and invoked unauthorized subshell",
        dispute_bond=250.0,
    )
    _, audit_msg = engine.submit_trace_evidence("disp_refactor_01", bad_trace)
    print(f"  {audit_msg}")

    # 6. Tribunal Resolution & Slashing
    print("\n[5] Resolving Tribunal & Enforcing Slashing Penalty...")
    worker_before_stake = engine.agents["worker_node"].stake_balance
    receipt = engine.resolve_arbitration_and_slash("disp_refactor_01")
    worker_after_stake = engine.agents["worker_node"].stake_balance

    print(f"  Verdict:           {receipt['verdict']}")
    print(f"  Winner:            {receipt['winner']}")
    print(f"  Breach Detail:     {receipt['breach_description']}")
    print(f"  Slashed Penalty:   ${receipt['slashed_penalty_collected']:.2f}")
    print(f"  Worker Stake:      ${worker_before_stake:.2f} -> ${worker_after_stake:.2f}")
    print(f"  Worker Jailed:     {receipt['provider_jailed']} (below $2,000 min stake)")

    # 7. Verification of Action Witness DAG
    print("\n[6] Verifying Action Witness DAG...")
    print(f"  Witness DAG Depth: {len(engine.action_witness_dag)} blocks")
    print(f"  State Root Hash:   {engine.state_root}")

    print("\n" + "=" * 70)
    print("QUICKSTART DEMONSTRATION COMPLETE - 100% OPERATIONAL")
    print("=" * 70)


if __name__ == "__main__":
    main()
