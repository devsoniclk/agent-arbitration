"""
Unit tests for TribunalManager, Juror consensus, and Automated Slashing.
"""

import hashlib
import pytest
from agent_arbitration.identity import IdentityRegistry
from agent_arbitration.sla import SlaManager
from agent_arbitration.tribunal import TribunalManager
from agent_arbitration.types import AgentRole, BreachType, SlaExecutionTrace, VerdictOutcome


@pytest.fixture
def setup_tribunal():
    reg = IdentityRegistry(min_stake_bond=2000.0)
    reg.register_agent("client_01", "pk_c", AgentRole.ORCHESTRATOR, 5000.0, 0.95)
    reg.register_agent("provider_01", "pk_p", AgentRole.SWARM_WORKER, 3000.0, 0.90)
    reg.register_agent("juror_1", "pk_j1", AgentRole.TRIBUNAL_JUROR, 5000.0, 0.98)
    reg.register_agent("juror_2", "pk_j2", AgentRole.TRIBUNAL_JUROR, 5000.0, 0.97)
    reg.register_agent("juror_3", "pk_j3", AgentRole.TRIBUNAL_JUROR, 5000.0, 0.96)

    sla_mgr = SlaManager(identity_registry=reg)
    sla_mgr.register_sla("sla_01", "client_01", "provider_01", 500.0, 0.90, {"search"}, 1000.0)

    trib = TribunalManager(identity_registry=reg, sla_manager=sla_mgr)
    return reg, sla_mgr, trib


def test_initiate_dispute_validation(setup_tribunal):
    reg, sla_mgr, trib = setup_tribunal

    # Low bond rejected (< 10% of 1000 = 100)
    low_ok, _ = trib.initiate_dispute("d_low", "sla_01", "client_01", "Breach", 50.0)
    assert low_ok is False

    # Valid bond (150 >= 100)
    ok, _ = trib.initiate_dispute("d_01", "sla_01", "client_01", "Latency Breach", 150.0)
    assert ok is True
    assert "d_01" in trib.disputes
    assert sla_mgr.agreements["sla_01"].is_disputed is True

    # Duplicate dispute on same SLA rejected
    dup_sla, _ = trib.initiate_dispute("d_02", "sla_01", "client_01", "Breach", 150.0)
    assert dup_sla is False

    # Non-party claimant rejected
    sla_mgr.register_sla("sla_02", "client_01", "provider_01", 500.0, 0.90, {"search"}, 1000.0)
    non_party, _ = trib.initiate_dispute("d_03", "sla_02", "juror_1", "Breach", 150.0)
    assert non_party is False


def test_juror_voting_and_conflict_check(setup_tribunal):
    reg, sla_mgr, trib = setup_tribunal
    trib.initiate_dispute("d_01", "sla_01", "client_01", "Breach", 150.0)

    # Conflicted party cannot vote (client_01 is claimant)
    conf_ok, _ = trib.cast_juror_vote("d_01", "client_01", favor_claimant=True)
    assert conf_ok is False

    # Conflicted provider cannot vote
    prov_ok, _ = trib.cast_juror_vote("d_01", "provider_01", favor_claimant=False)
    assert prov_ok is False

    # Non-juror role cannot vote
    reg.register_agent("other_worker", "pk_ow", AgentRole.SWARM_WORKER, 2500.0, 0.90)
    work_ok, _ = trib.cast_juror_vote("d_01", "other_worker", favor_claimant=True)
    assert work_ok is False

    # Valid juror votes
    ok_j1, _ = trib.cast_juror_vote("d_01", "juror_1", favor_claimant=True)
    assert ok_j1 is True

    # Double voting rejected
    dup_vote, _ = trib.cast_juror_vote("d_01", "juror_1", favor_claimant=True)
    assert dup_vote is False


def test_dispute_resolution_claimant_wins_objective_breach(setup_tribunal):
    reg, sla_mgr, trib = setup_tribunal
    trib.initiate_dispute("d_01", "sla_01", "client_01", "Breach", 200.0)

    # Submit trace showing latency breach (800ms > 500ms)
    trace = SlaExecutionTrace(
        trace_id="tr_b",
        sla_id="sla_01",
        execution_time_ms=800.0,
        accuracy_metric=0.95,
        tools_called=["search"],
        execution_merkle_root=hashlib.sha256(b"root").hexdigest(),
        trace_signature="sig",
    )
    trib.submit_trace_evidence("d_01", trace)

    initial_provider_stake = reg.get_agent("provider_01").stake_balance  # 3000.0

    res = trib.resolve_arbitration_and_slash("d_01")
    assert res["winner"] == "client_01"
    assert res["verdict_outcome"] == VerdictOutcome.CLAIMANT_FAVORED.value
    # 25% of 1000 = 250.0
    assert res["slashed_penalty_collected"] == 250.0
    assert res["refunded_escrow"] == 1000.0
    assert res["bond_returned"] == 200.0
    assert reg.get_agent("provider_01").stake_balance == initial_provider_stake - 250.0
    assert reg.get_agent("provider_01").reputation_score == 80.0
    assert res["defendant_jailed"] is False


def test_dispute_resolution_frivolous_claim(setup_tribunal):
    reg, sla_mgr, trib = setup_tribunal
    trib.initiate_dispute("d_friv", "sla_01", "client_01", "Frivolous claim", 200.0)

    # Submit compliant trace
    trace = SlaExecutionTrace(
        trace_id="tr_clean",
        sla_id="sla_01",
        execution_time_ms=250.0,
        accuracy_metric=0.95,
        tools_called=["search"],
        execution_merkle_root=hashlib.sha256(b"clean").hexdigest(),
        trace_signature="sig",
    )
    trib.submit_trace_evidence("d_friv", trace)

    # Jurors vote against claimant
    trib.cast_juror_vote("d_friv", "juror_1", favor_claimant=False)
    trib.cast_juror_vote("d_friv", "juror_2", favor_claimant=False)

    initial_client_rep = reg.get_agent("client_01").reputation_score

    res = trib.resolve_arbitration_and_slash("d_friv")
    assert res["winner"] == "provider_01"
    assert res["verdict_outcome"] == VerdictOutcome.DEFENDANT_FAVORED.value
    assert res["forfeited_bond"] == 200.0
    assert res["released_escrow"] == 1000.0
    # Claimant reputation penalized
    assert reg.get_agent("client_01").reputation_score == initial_client_rep - 10.0


def test_jailing_on_stake_exhaustion(setup_tribunal):
    reg, sla_mgr, trib = setup_tribunal
    # Set provider stake to 2100 (min is 2000)
    provider = reg.get_agent("provider_01")
    provider.stake_balance = 2100.0

    sla_mgr.register_sla("sla_jail", "client_01", "provider_01", 500.0, 0.90, {"search"}, 1000.0)
    trib.initiate_dispute("d_jail", "sla_jail", "client_01", "Breach", 150.0)

    trace = SlaExecutionTrace(
        trace_id="tr_b2",
        sla_id="sla_jail",
        execution_time_ms=900.0,
        accuracy_metric=0.50,
        tools_called=["search"],
        execution_merkle_root=hashlib.sha256(b"root2").hexdigest(),
        trace_signature="sig2",
    )
    trib.submit_trace_evidence("d_jail", trace)

    res = trib.resolve_arbitration_and_slash("d_jail")
    # 2100 - 250 = 1850 < 2000 -> jailed!
    assert res["defendant_jailed"] is True
    assert provider.is_jailed is True
    assert provider.effective_voting_power == 0.0
