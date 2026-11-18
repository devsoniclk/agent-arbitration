"""
Agent Arbitration: Deterministic SLA dispute arbitration, proof-of-compute staking &
automated escrow slashing for autonomous AI agent swarms.

Author: Lakshitha Dananjaya (devsoniclk)
"""

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
from agent_arbitration.identity import IdentityRegistry
from agent_arbitration.governance import GovernanceManager
from agent_arbitration.sla import SlaManager
from agent_arbitration.tribunal import TribunalManager
from agent_arbitration.witness import WitnessDAG
from agent_arbitration.engine import AgentArbitrationEngine, ArbitrationEngine

__version__ = "0.1.0"
__author__ = "Lakshitha Dananjaya"

__all__ = [
    "AgentIdentity",
    "AgentRole",
    "BreachType",
    "DisputeRecord",
    "DisputeStatus",
    "Proposal",
    "ProposalStatus",
    "SlaAgreement",
    "SlaExecutionTrace",
    "StateWitness",
    "VerdictOutcome",
    "IdentityRegistry",
    "GovernanceManager",
    "SlaManager",
    "TribunalManager",
    "WitnessDAG",
    "AgentArbitrationEngine",
    "ArbitrationEngine",
    "__version__",
]
