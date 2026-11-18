"""
Core data types, enums, and data models for Agent Arbitration.
"""

from __future__ import annotations
import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class AgentRole(str, Enum):
    SWARM_WORKER = "SWARM_WORKER"
    ORCHESTRATOR = "ORCHESTRATOR"
    TRIBUNAL_JUROR = "TRIBUNAL_JUROR"
    SECURITY_AUDITOR = "SECURITY_AUDITOR"


class DisputeStatus(str, Enum):
    INITIATED = "INITIATED"
    EVIDENCE_SUBMISSION = "EVIDENCE_SUBMISSION"
    TRIBUNAL_EVALUATION = "TRIBUNAL_EVALUATION"
    VERDICT_RESOLVED = "VERDICT_RESOLVED"
    ESCROW_SETTLED = "ESCROW_SETTLED"
    APPEAL_ESCALATION = "APPEAL_ESCALATION"


class ProposalStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PASSED = "PASSED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"


class BreachType(str, Enum):
    LATENCY_EXCEEDED = "LATENCY_EXCEEDED"
    ACCURACY_DEGRADED = "ACCURACY_DEGRADED"
    FORBIDDEN_TOOL = "FORBIDDEN_TOOL"
    INCORRECT_OUTPUT = "INCORRECT_OUTPUT"
    NONE = "NONE"


class VerdictOutcome(str, Enum):
    CLAIMANT_FAVORED = "CLAIMANT_FAVORED"
    DEFENDANT_FAVORED = "DEFENDANT_FAVORED"
    SPLIT_SETTLEMENT = "SPLIT_SETTLEMENT"


@dataclass
class AgentIdentity:
    agent_id: str
    public_key: str
    role: AgentRole
    stake_balance: float
    benchmark_score: float  # [0.0 - 1.0] compute integrity score
    reputation_score: float = 100.0
    slashed_total: float = 0.0
    is_jailed: bool = False

    @property
    def effective_voting_power(self) -> float:
        """
        Sub-linear voting power: V_i = sqrt(S_i) * B_i.
        Returns 0.0 if the agent is jailed or has zero/negative stake.
        """
        if self.is_jailed or self.stake_balance <= 0.0:
            return 0.0
        return math.sqrt(self.stake_balance) * max(0.0, min(1.0, self.benchmark_score))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["effective_voting_power"] = self.effective_voting_power
        return d


@dataclass
class Proposal:
    proposal_id: str
    proposer_id: str
    title: str
    description: str
    requested_amount: float
    status: ProposalStatus = ProposalStatus.ACTIVE
    created_at: float = field(default_factory=float)
    expires_at: float = field(default_factory=float)
    target_quorum: float = 0.0
    yes_weight: float = 0.0
    no_weight: float = 0.0
    votes: Dict[str, Tuple[float, float, bool]] = field(default_factory=dict)  # agent_id -> (credits, weight, vote_yes)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SlaAgreement:
    sla_id: str
    client_id: str
    provider_id: str
    max_latency_ms: float
    min_accuracy_threshold: float
    allowed_tools: Set[str]
    escrow_amount: float
    expiry_timestamp: float
    is_completed: bool = False
    is_disputed: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["allowed_tools"] = sorted(list(self.allowed_tools))
        return d


@dataclass
class SlaExecutionTrace:
    trace_id: str
    sla_id: str
    execution_time_ms: float
    accuracy_metric: float
    tools_called: List[str]
    execution_merkle_root: str
    trace_signature: str
    error_payload: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DisputeRecord:
    dispute_id: str
    sla_id: str
    claimant_id: str
    defendant_id: str
    claim_reason: str
    dispute_bond: float
    status: DisputeStatus = DisputeStatus.INITIATED
    created_at: float = field(default_factory=float)
    evidence_trace: Optional[SlaExecutionTrace] = None
    juror_votes: Dict[str, bool] = field(default_factory=dict)  # juror_id -> favor_claimant
    verdict_outcome: Optional[VerdictOutcome] = None
    slashed_penalty: float = 0.0
    forfeited_bond: float = 0.0
    closed_at: Optional[float] = None
    breach_type: BreachType = BreachType.NONE

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.evidence_trace:
            d["evidence_trace"] = self.evidence_trace.to_dict()
        return d


@dataclass
class StateWitness:
    step_index: int
    action_type: str
    entity_id: str
    prev_hash: str
    payload_hash: str
    witness_hash: str
    timestamp: float

    def to_dict(self) -> dict:
        return asdict(self)
