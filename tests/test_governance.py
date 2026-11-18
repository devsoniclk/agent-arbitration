"""
Unit tests for GovernanceManager and Quadratic Voting.
"""

import pytest
from agent_arbitration.identity import IdentityRegistry
from agent_arbitration.governance import GovernanceManager
from agent_arbitration.types import AgentRole, ProposalStatus


@pytest.fixture
def setup_gov():
    reg = IdentityRegistry(min_stake_bond=2000.0)
    reg.register_agent("proposer", "pk_p", AgentRole.ORCHESTRATOR, 5000.0, 0.95)
    reg.register_agent("voter_1", "pk_v1", AgentRole.SWARM_WORKER, 2500.0, 0.90)
    reg.register_agent("voter_2", "pk_v2", AgentRole.SWARM_WORKER, 3600.0, 0.80)
    gov = GovernanceManager(identity_registry=reg, initial_treasury=100_000.0)
    return reg, gov


def test_dynamic_quorum_calculation(setup_gov):
    _, gov = setup_gov
    # Base = 0.25, Delta = 0.35
    # 0 amount -> 0.25
    assert abs(gov.calculate_dynamic_quorum(0.0) - 0.25) < 1e-4

    # 50,000 / 100,000 = 0.5 -> 0.25 + 0.35 * 0.5 = 0.25 + 0.175 = 0.425
    assert abs(gov.calculate_dynamic_quorum(50_000.0) - 0.425) < 1e-4

    # 100,000 / 100,000 = 1.0 -> 0.25 + 0.35 * 1.0 = 0.60
    assert abs(gov.calculate_dynamic_quorum(100_000.0) - 0.60) < 1e-4

    # Exceeding treasury capped at 1.0 -> 0.60
    assert abs(gov.calculate_dynamic_quorum(150_000.0) - 0.60) < 1e-4


def test_create_proposal_validation(setup_gov):
    reg, gov = setup_gov

    # Success
    ok, msg = gov.create_proposal("p1", "proposer", "Title", "Desc", 10_000.0)
    assert ok is True
    assert "p1" in gov.proposals

    # Duplicate ID
    dup_ok, _ = gov.create_proposal("p1", "proposer", "Title", "Desc", 10_000.0)
    assert dup_ok is False

    # Nonexistent proposer
    ghost_ok, _ = gov.create_proposal("p2", "ghost", "Title", "Desc", 10_000.0)
    assert ghost_ok is False

    # Jailed proposer
    reg.get_agent("proposer").is_jailed = True
    jailed_ok, _ = gov.create_proposal("p3", "proposer", "Title", "Desc", 10_000.0)
    assert jailed_ok is False

    # Exceeding treasury
    reg.get_agent("proposer").is_jailed = False
    excess_ok, _ = gov.create_proposal("p4", "proposer", "Title", "Desc", 200_000.0)
    assert excess_ok is False


def test_quadratic_voting_mechanism(setup_gov):
    reg, gov = setup_gov
    gov.create_proposal("p1", "proposer", "Title", "Desc", 10_000.0)

    # voter_1: B = 0.90, credits = 100 -> weight = sqrt(100) * 0.90 = 10 * 0.90 = 9.0
    ok, msg = gov.cast_quadratic_vote("p1", "voter_1", credits_allocated=100.0, vote_yes=True)
    assert ok is True
    prop = gov.proposals["p1"]
    assert abs(prop.yes_weight - 9.0) < 1e-4
    assert prop.no_weight == 0.0

    # Double voting rejected
    double_ok, _ = gov.cast_quadratic_vote("p1", "voter_1", credits_allocated=50.0, vote_yes=True)
    assert double_ok is False

    # voter_2: B = 0.80, credits = 400 -> weight = sqrt(400) * 0.80 = 20 * 0.80 = 16.0
    gov.cast_quadratic_vote("p1", "voter_2", credits_allocated=400.0, vote_yes=False)
    assert abs(prop.no_weight - 16.0) < 1e-4

    # Non-positive credits rejected
    bad_cred, _ = gov.cast_quadratic_vote("p1", "proposer", credits_allocated=0.0, vote_yes=True)
    assert bad_cred is False


def test_proposal_evaluation_and_execution(setup_gov):
    reg, gov = setup_gov
    gov.create_proposal("p1", "proposer", "Title", "Desc", 10_000.0)

    # Early check without finalize
    passed, status, msg = gov.evaluate_proposal("p1", finalize=False)
    assert passed is False
    assert status == ProposalStatus.ACTIVE

    # All participate
    gov.cast_quadratic_vote("p1", "proposer", credits_allocated=900.0, vote_yes=True)
    gov.cast_quadratic_vote("p1", "voter_1", credits_allocated=400.0, vote_yes=True)
    gov.cast_quadratic_vote("p1", "voter_2", credits_allocated=100.0, vote_yes=False)

    passed, status, msg = gov.evaluate_proposal("p1", finalize=True)
    assert passed is True
    assert status == ProposalStatus.PASSED

    # Execute proposal
    initial_treasury = gov.treasury_balance
    ok_exec, _ = gov.execute_proposal("p1")
    assert ok_exec is True
    assert gov.treasury_balance == initial_treasury - 10_000.0
    assert gov.proposals["p1"].status == ProposalStatus.EXECUTED

    # Re-executing fails
    dup_exec, _ = gov.execute_proposal("p1")
    assert dup_exec is False
