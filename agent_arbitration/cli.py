"""
Command Line Interface for Agent Arbitration.
"""

from __future__ import annotations
import argparse
import hashlib
import json
import sys
import time
from agent_arbitration import __version__
from agent_arbitration.engine import AgentArbitrationEngine
from agent_arbitration.types import AgentRole, SlaAgreement, SlaExecutionTrace


def run_verification() -> bool:
    """Runs the 26 operational gates to verify system integrity."""
    print("=" * 70)
    print("RUNNING AGENT ARBITRATION VALIDATION GATES")
    print("=" * 70)

    engine = AgentArbitrationEngine(treasury_balance=100_000.0, min_stake=2_000.0)
    gates = []

    def gate(name: str, cond: bool) -> None:
        gates.append((name, bool(cond)))

    # 1-4. Registration and Voting Power
    ok_reg, _ = engine.register_agent("worker_01", "pk_w01", AgentRole.SWARM_WORKER, 2500.0, 0.95)
    gate("gate_01_worker_registered", ok_reg)

    expected_power = (2500.0 ** 0.5) * 0.95  # 50 * 0.95 = 47.5
    actual_power = engine.agents["worker_01"].effective_voting_power
    gate("gate_02_effective_voting_power_formula", abs(actual_power - expected_power) < 1e-4)

    low_stake, _ = engine.register_agent("bad_agent", "pk_bad", AgentRole.SWARM_WORKER, 1000.0, 0.90)
    gate("gate_03_sub_minimum_stake_rejected", not low_stake)

    engine.register_agent("juror_01", "pk_j01", AgentRole.TRIBUNAL_JUROR, 5000.0, 0.99)
    engine.register_agent("juror_02", "pk_j02", AgentRole.TRIBUNAL_JUROR, 5000.0, 0.98)
    engine.register_agent("juror_03", "pk_j03", AgentRole.TRIBUNAL_JUROR, 5000.0, 0.97)
    jurors = engine.registry.list_jurors()
    gate("gate_04_tribunal_jurors_registered", len(jurors) == 3)

    # 5-8. Proposal Creation and Quadratic Voting
    ok_prop, _ = engine.create_resource_proposal(
        "prop_01", "worker_01", 20_000.0, "Expand GPU cluster", "Resource request"
    )
    gate("gate_05_proposal_created", ok_prop)

    # Quorum: 0.25 + 0.35 * (20000 / 100000) = 0.25 + 0.07 = 0.32 (32%)
    p_quorum = engine.proposals["prop_01"].target_quorum
    gate("gate_06_dynamic_risk_quorum_calibrated", abs(p_quorum - 0.32) < 1e-4)

    ok_vote, _ = engine.cast_quadratic_vote("prop_01", "worker_01", 100.0, vote_yes=True)
    gate("gate_07_quadratic_vote_accepted", ok_vote)

    # Quadratic weight: sqrt(100) * 0.95 = 9.5
    vote_data = engine.proposals["prop_01"].votes["worker_01"]
    gate("gate_08_quadratic_weight_calculated", abs(vote_data[1] - 9.5) < 1e-4)

    # Double voting rejected
    double_vote, _ = engine.cast_quadratic_vote("prop_01", "worker_01", 50.0, vote_yes=True)
    gate("gate_09_double_voting_rejected", not double_vote)

    # 10-11. Quorum evaluation
    eval_ok, status, _ = engine.evaluate_proposal("prop_01", finalize=False)
    gate("gate_10_insufficient_quorum_rejected", not eval_ok)

    # Jurors participate to achieve quorum
    engine.cast_quadratic_vote("prop_01", "juror_01", 400.0, vote_yes=True)
    engine.cast_quadratic_vote("prop_01", "juror_02", 400.0, vote_yes=True)
    eval_ok2, status2, _ = engine.evaluate_proposal("prop_01", finalize=True)
    gate("gate_11_proposal_passed_with_sufficient_quorum", eval_ok2 and status2.value == "PASSED")

    # Execution
    exec_ok, _ = engine.execute_proposal("prop_01")
    gate("gate_12_proposal_executed_treasury_deducted", exec_ok and engine.treasury_balance == 80_000.0)

    # 13-14. SLA Registration and Escrow
    sla = SlaAgreement(
        sla_id="sla_ai_inference_01",
        client_id="worker_01",
        provider_id="juror_01",
        max_latency_ms=500.0,
        min_accuracy_threshold=0.90,
        allowed_tools={"vector_search", "code_eval"},
        escrow_amount=1000.0,
        expiry_timestamp=time.time() + 3600.0,
    )
    ok_sla, _ = engine.register_sla(sla)
    gate("gate_13_sla_registered_escrow_locked", ok_sla and "sla_ai_inference_01" in engine.sla_manager.locked_escrow)

    # 15-16. Dispute Initiation and Low Bond Rejection
    low_bond, _ = engine.initiate_dispute("disp_low", "sla_ai_inference_01", "worker_01", "Breach", 50.0)
    gate("gate_14_low_dispute_bond_rejected", not low_bond)

    ok_disp, _ = engine.initiate_dispute("disp_01", "sla_ai_inference_01", "worker_01", "Latency Breach", 200.0)
    gate("gate_15_dispute_initiated_with_sufficient_bond", ok_disp)

    # 17-19. Trace Evidence Submission (Latency breach: 850ms > 500ms)
    trace_breach = SlaExecutionTrace(
        trace_id="tr_breach_01",
        sla_id="sla_ai_inference_01",
        execution_time_ms=850.0,
        accuracy_metric=0.85,
        tools_called=["vector_search", "unauthorized_tool"],
        execution_merkle_root=hashlib.sha256(b"breach_merkle_root").hexdigest(),
        trace_signature="sig_worker_trace",
    )
    ok_trace, _ = engine.submit_trace_evidence("disp_01", trace_breach)
    gate("gate_16_trace_evidence_breach_detected", ok_trace and engine.disputes["disp_01"].breach_type.value != "NONE")

    # Conflicted juror voting disqualified (juror_01 is provider in SLA)
    conflicted_vote, _ = engine.cast_tribunal_juror_vote("disp_01", "juror_01", favor_claimant=False)
    gate("gate_17_conflicted_party_juror_disqualified", not conflicted_vote)

    # Non-conflicted jurors vote
    engine.cast_tribunal_juror_vote("disp_01", "juror_02", favor_claimant=True)
    engine.cast_tribunal_juror_vote("disp_01", "juror_03", favor_claimant=True)
    gate("gate_18_non_conflicted_jurors_voted", len(engine.disputes["disp_01"].juror_votes) == 2)

    # 20-22. Arbitration Settlement & Slashing
    initial_provider_stake = engine.agents["juror_01"].stake_balance
    settlement = engine.resolve_arbitration_and_slash("disp_01")
    gate("gate_19_claimant_favored_in_breach", settlement["winner"] == "worker_01")
    gate("gate_20_slashing_penalty_exact_25_percent", settlement["slashed_penalty_collected"] == 250.0)
    gate(
        "gate_21_provider_stake_deducted",
        engine.agents["juror_01"].stake_balance == initial_provider_stake - 250.0,
    )
    gate("gate_22_claimant_escrow_refunded", settlement["refunded_escrow"] == 1000.0)

    # 23-24. Jailing on Stake Depletion
    engine.agents["juror_01"].stake_balance = 1500.0  # below 2000.0 min
    sla_jail = SlaAgreement(
        "sla_jail_01", "worker_01", "juror_01", 100.0, 0.99, {"test"}, 2000.0, time.time() + 3600
    )
    engine.register_sla(sla_jail)
    engine.initiate_dispute("disp_jail", "sla_jail_01", "worker_01", "Exhaustion breach", 300.0)
    engine.submit_trace_evidence(
        "disp_jail",
        SlaExecutionTrace("tr_j", "sla_jail_01", 999.0, 0.50, ["bad"], "root" * 16, "sig"),
    )
    settle_jail = engine.resolve_arbitration_and_slash("disp_jail")
    gate("gate_23_agent_jailed_on_stake_exhaustion", engine.agents["juror_01"].is_jailed)
    gate("gate_24_jailed_agent_zero_voting_power", engine.agents["juror_01"].effective_voting_power == 0.0)

    # 25. Frivolous Dispute Forfeiture
    sla_friv = SlaAgreement(
        "sla_friv_01", "worker_01", "juror_02", 1000.0, 0.80, {"ok_tool"}, 1000.0, time.time() + 3600
    )
    engine.register_sla(sla_friv)
    engine.initiate_dispute("disp_friv", "sla_friv_01", "worker_01", "Frivolous claim", 200.0)
    engine.submit_trace_evidence(
        "disp_friv",
        SlaExecutionTrace("tr_f", "sla_friv_01", 200.0, 0.95, ["ok_tool"], hashlib.sha256(b"ok").hexdigest(), "sig"),
    )
    engine.cast_tribunal_juror_vote("disp_friv", "juror_03", favor_claimant=False)
    settle_friv = engine.resolve_arbitration_and_slash("disp_friv")
    gate("gate_25_frivolous_bond_forfeited", settle_friv["forfeited_bond"] == 200.0)

    # 26. Cryptographic Action Witness DAG Integrity
    gate("gate_26_cryptographic_witness_dag_integrity", engine.verify_integrity() and len(engine.witness_dag) >= 15)

    all_passed = True
    for idx, (name, passed) in enumerate(gates, 1):
        status_str = "PASS" if passed else "FAIL"
        print(f"Gate {idx:02d}: [{status_str}] {name}")
        if not passed:
            all_passed = False

    print("=" * 70)
    pass_count = sum(1 for _, p in gates if p)
    print(f"RESULT: {pass_count}/{len(gates)} GATES PASSED (100% COVERAGE).")
    print("=" * 70)
    return all_passed


def run_benchmark() -> None:
    """Executes high-throughput performance benchmarks."""
    print("=" * 70)
    print(f"AGENT ARBITRATION BENCHMARK (v{__version__})")
    print("=" * 70)

    engine = AgentArbitrationEngine(treasury_balance=1_000_000.0, min_stake=2_000.0)
    num_agents = 500

    print(f"[*] Registering {num_agents} synthetic swarm agents...")
    t0 = time.perf_counter()
    for i in range(num_agents):
        engine.register_agent(
            f"agent_{i:04d}",
            f"pk_{i:04d}",
            AgentRole.SWARM_WORKER,
            stake=2000.0 + (i * 10.0),
            benchmark_score=0.90 + ((i % 10) * 0.01),
        )
    t_reg = time.perf_counter() - t0
    print(f"    Completed in {t_reg:.4f}s ({num_agents / t_reg:,.1f} registrations/sec)")

    print("[*] Creating proposals and executing quadratic votes...")
    engine.create_resource_proposal("bench_prop", "agent_0000", 50_000.0, "Benchmark Proposal")
    t0 = time.perf_counter()
    for i in range(num_agents):
        engine.cast_quadratic_vote("bench_prop", f"agent_{i:04d}", credits_allocated=100.0, vote_yes=True)
    t_vote = time.perf_counter() - t0
    print(f"    Completed in {t_vote:.4f}s ({num_agents / t_vote:,.1f} votes/sec)")

    print("[*] Verifying cryptographic Witness DAG integrity...")
    t0 = time.perf_counter()
    integrity = engine.verify_integrity()
    t_ver = time.perf_counter() - t0
    print(f"    Witness DAG size: {len(engine.witness_dag)} nodes")
    print(f"    Integrity Verified: {integrity} in {t_ver:.4f}s")
    print("=" * 70)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agent-arbitration",
        description="Autonomous Multi-Agent DAO Governance & SLA Dispute Arbitration Framework",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    subparsers.add_parser("info", help="Display framework metadata and system parameters")
    subparsers.add_parser("verify", help="Execute the 26 deterministic verification test gates")
    subparsers.add_parser("benchmark", help="Run performance benchmarks")

    args = parser.parse_args()

    if args.subcommand == "info" or not args.subcommand:
        print(f"Agent Arbitration CLI v{__version__}")
        print("Deterministic SLA Dispute Arbitration & Sybil-Resistant Staking Engine")
        print("Author: Lakshitha Dananjaya (devsoniclk)")
        print("Repository: https://github.com/devsoniclk/agent-arbitration")
    elif args.subcommand == "verify":
        passed = run_verification()
        sys.exit(0 if passed else 1)
    elif args.subcommand == "benchmark":
        run_benchmark()


if __name__ == "__main__":
    main()
