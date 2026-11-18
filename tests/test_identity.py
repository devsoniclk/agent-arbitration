"""
Unit tests for IdentityRegistry and AgentIdentity.
"""

import pytest
from agent_arbitration.identity import IdentityRegistry
from agent_arbitration.types import AgentIdentity, AgentRole


def test_agent_registration_success():
    reg = IdentityRegistry(min_stake_bond=2000.0)
    ok, msg = reg.register_agent("worker_01", "pk_w01", AgentRole.SWARM_WORKER, 2500.0, 0.90)
    assert ok is True
    agent = reg.get_agent("worker_01")
    assert agent is not None
    assert agent.agent_id == "worker_01"
    assert agent.role == AgentRole.SWARM_WORKER
    assert agent.stake_balance == 2500.0
    assert agent.benchmark_score == 0.90
    assert agent.reputation_score == 100.0
    assert agent.is_jailed is False


def test_agent_registration_duplicate():
    reg = IdentityRegistry(min_stake_bond=2000.0)
    reg.register_agent("worker_01", "pk_w01", AgentRole.SWARM_WORKER, 2500.0, 0.90)
    ok, msg = reg.register_agent("worker_01", "pk_w01", AgentRole.SWARM_WORKER, 2500.0, 0.90)
    assert ok is False
    assert "already registered" in msg


def test_agent_registration_sub_minimum_stake():
    reg = IdentityRegistry(min_stake_bond=2000.0)
    ok, msg = reg.register_agent("worker_low", "pk_low", AgentRole.SWARM_WORKER, 1500.0, 0.90)
    assert ok is False
    assert "below minimum requirement" in msg


def test_agent_registration_invalid_benchmark():
    reg = IdentityRegistry(min_stake_bond=2000.0)
    ok, msg = reg.register_agent("worker_bad", "pk_bad", AgentRole.SWARM_WORKER, 2500.0, 1.5)
    assert ok is False
    assert "Benchmark score" in msg


def test_effective_voting_power_calculation():
    reg = IdentityRegistry(min_stake_bond=2000.0)
    # S = 2500, B = 0.8 -> sqrt(2500) * 0.8 = 50 * 0.8 = 40.0
    reg.register_agent("worker_01", "pk_w01", AgentRole.SWARM_WORKER, 2500.0, 0.80)
    agent = reg.get_agent("worker_01")
    assert abs(agent.effective_voting_power - 40.0) < 1e-4

    # Jailed agent has zero voting power
    agent.is_jailed = True
    assert agent.effective_voting_power == 0.0

    # Negative or zero stake has zero voting power
    agent.is_jailed = False
    agent.stake_balance = 0.0
    assert agent.effective_voting_power == 0.0


def test_stake_deposit_and_unjail():
    reg = IdentityRegistry(min_stake_bond=2000.0)
    reg.register_agent("worker_01", "pk_w01", AgentRole.SWARM_WORKER, 2500.0, 0.80)
    agent = reg.get_agent("worker_01")

    # Slash below minimum to jail
    reg.slash_agent("worker_01", 1000.0)
    assert agent.stake_balance == 1500.0
    assert agent.is_jailed is True

    # Deposit to restore above min_stake
    ok, msg = reg.deposit_stake("worker_01", 1000.0)
    assert ok is True
    assert agent.stake_balance == 2500.0
    assert agent.is_jailed is False

    # Negative deposit fails
    bad_dep, _ = reg.deposit_stake("worker_01", -50.0)
    assert bad_dep is False

    # Nonexistent agent fails
    none_dep, _ = reg.deposit_stake("ghost", 100.0)
    assert none_dep is False


def test_slashing_and_reputation():
    reg = IdentityRegistry(min_stake_bond=2000.0)
    reg.register_agent("worker_01", "pk_w01", AgentRole.SWARM_WORKER, 3000.0, 0.80)
    agent = reg.get_agent("worker_01")

    ok, deducted, is_jailed = reg.slash_agent("worker_01", 500.0)
    assert ok is True
    assert deducted == 500.0
    assert agent.stake_balance == 2500.0
    assert agent.reputation_score == 80.0
    assert is_jailed is False

    # Nonexistent agent slash
    bad_slash, _, _ = reg.slash_agent("ghost", 100.0)
    assert bad_slash is False

    # Reputation boost and penalties
    reg.reward_reputation("worker_01", boost=5.0)
    assert agent.reputation_score == 85.0
    reg.penalize_reputation("worker_01", penalty=10.0)
    assert agent.reputation_score == 75.0


def test_list_jurors():
    reg = IdentityRegistry(min_stake_bond=2000.0)
    reg.register_agent("worker_01", "pk_w01", AgentRole.SWARM_WORKER, 2500.0, 0.80)
    reg.register_agent("juror_01", "pk_j01", AgentRole.TRIBUNAL_JUROR, 5000.0, 0.95)
    reg.register_agent("juror_02", "pk_j02", AgentRole.TRIBUNAL_JUROR, 5000.0, 0.95)

    jurors = reg.list_jurors()
    assert len(jurors) == 2
    assert {j.agent_id for j in jurors} == {"juror_01", "juror_02"}

    # Jailing juror removes them from active list
    reg.get_agent("juror_01").is_jailed = True
    assert len(reg.list_jurors()) == 1
