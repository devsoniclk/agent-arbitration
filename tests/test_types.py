"""
Tests for core types, enums, and data models.
"""

import math
from agent_arbitration.types import (
    AgentIdentity,
    AgentRole,
    BreachType,
    DisputeRecord,
    DisputeStatus,
    Proposal,
    ProposalStatus,
    SlaAgreement,
    SlaExecutionTrace,
    StateWitness,
    VerdictOutcome,
)


def test_agent_identity_voting_power():
    agent = AgentIdentity(
        agent_id="test_agent",
        public_key="pk_01",
        role=AgentRole.SWARM_WORKER,
        stake_balance=10_000.0,
        benchmark_score=0.90,
    )
    # sqrt(10000) * 0.90 = 100 * 0.90 = 90.0
    assert math.isclose(agent.effective_voting_power, 90.0)

    # Jailed agent has 0 voting power
    agent.is_jailed = True
    assert agent.effective_voting_power == 0.0

    # Agent with zero stake has 0 voting power
    agent.is_jailed = False
    agent.stake_balance = 0.0
    assert agent.effective_voting_power == 0.0

    # Negative stake check
    agent.stake_balance = -50.0
    assert agent.effective_voting_power == 0.0


def test_agent_identity_dict_serialization():
    agent = AgentIdentity(
        agent_id="a1",
        public_key="pk_a1",
        role=AgentRole.ORCHESTRATOR,
        stake_balance=400.0,
        benchmark_score=1.0,
    )
    d = agent.to_dict()
    assert d["agent_id"] == "a1"
    assert d["role"] == AgentRole.ORCHESTRATOR
    assert math.isclose(d["effective_voting_power"], 20.0)


def test_sla_agreement_serialization():
    sla = SlaAgreement(
        sla_id="sla_1",
        client_id="c1",
        provider_id="p1",
        max_latency_ms=500.0,
        min_accuracy_threshold=0.95,
        allowed_tools={"t1", "t2"},
        escrow_amount=500.0,
        expiry_timestamp=1000.0,
    )
    d = sla.to_dict()
    assert d["allowed_tools"] == ["t1", "t2"]
    assert d["escrow_amount"] == 500.0


def test_dispute_record_serialization():
    record = DisputeRecord(
        dispute_id="disp_1",
        sla_id="sla_1",
        claimant_id="c1",
        defendant_id="p1",
        claim_reason="Timeout",
        dispute_bond=50.0,
    )
    d = record.to_dict()
    assert d["dispute_id"] == "disp_1"
    assert d["breach_type"] == BreachType.NONE
