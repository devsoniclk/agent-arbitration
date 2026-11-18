"""
Algorithmic Governance, Dynamic Quorum Calibration, and Quadratic Voting.
"""

from __future__ import annotations
import math
import time
from typing import Dict, List, Optional, Tuple
from agent_arbitration.types import Proposal, ProposalStatus
from agent_arbitration.identity import IdentityRegistry


class GovernanceManager:
    """
    Manages DAO resource allocation proposals, dynamic risk-adjusted quorums,
    and non-collusive quadratic voting for multi-agent swarms.
    """

    def __init__(
        self,
        identity_registry: IdentityRegistry,
        initial_treasury: float = 100_000.0,
        base_quorum: float = 0.25,
        delta_quorum: float = 0.35,
    ) -> None:
        self.registry = identity_registry
        self.treasury_balance = initial_treasury
        self.base_quorum = base_quorum
        self.delta_quorum = delta_quorum
        self.proposals: Dict[str, Proposal] = {}

    def calculate_dynamic_quorum(self, requested_amount: float) -> float:
        """
        Q(t) = Q_base + Delta_Q * min(1.0, Requested / Treasury)
        """
        if self.treasury_balance <= 0:
            return self.base_quorum + self.delta_quorum
        exposure_ratio = min(1.0, max(0.0, requested_amount / self.treasury_balance))
        return self.base_quorum + (self.delta_quorum * exposure_ratio)

    def create_proposal(
        self,
        proposal_id: str,
        proposer_id: str,
        title: str,
        description: str,
        requested_amount: float,
        duration_seconds: float = 86400.0,
    ) -> Tuple[bool, str]:
        if proposal_id in self.proposals:
            return False, f"Proposal '{proposal_id}' already exists."

        proposer = self.registry.get_agent(proposer_id)
        if not proposer:
            return False, f"Proposer '{proposer_id}' not found."
        if proposer.is_jailed:
            return False, f"Proposer '{proposer_id}' is currently jailed."
        if requested_amount > self.treasury_balance:
            return False, f"Requested amount {requested_amount:.2f} exceeds treasury {self.treasury_balance:.2f}."

        now = time.time()
        target_quorum = self.calculate_dynamic_quorum(requested_amount)

        proposal = Proposal(
            proposal_id=proposal_id,
            proposer_id=proposer_id,
            title=title,
            description=description,
            requested_amount=requested_amount,
            status=ProposalStatus.ACTIVE,
            created_at=now,
            expires_at=now + duration_seconds,
            target_quorum=target_quorum,
            yes_weight=0.0,
            no_weight=0.0,
            votes={},
        )
        self.proposals[proposal_id] = proposal
        return True, f"Proposal '{proposal_id}' created with dynamic quorum {target_quorum * 100:.1f}%."

    def cast_quadratic_vote(
        self,
        proposal_id: str,
        voter_id: str,
        credits_allocated: float,
        vote_yes: bool,
    ) -> Tuple[bool, str]:
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return False, f"Proposal '{proposal_id}' not found."
        if proposal.status != ProposalStatus.ACTIVE:
            return False, f"Proposal '{proposal_id}' is not active (status={proposal.status.value})."

        voter = self.registry.get_agent(voter_id)
        if not voter:
            return False, f"Voter '{voter_id}' not registered."
        if voter.is_jailed:
            return False, f"Voter '{voter_id}' is currently jailed."
        if credits_allocated <= 0.0:
            return False, "Credits allocated must be greater than zero."
        if voter_id in proposal.votes:
            return False, f"Voter '{voter_id}' has already voted on proposal '{proposal_id}'."

        # Non-collusive quadratic voting weight: W = sqrt(credits) * benchmark_score
        weight = math.sqrt(credits_allocated) * voter.benchmark_score

        proposal.votes[voter_id] = (credits_allocated, weight, vote_yes)
        if vote_yes:
            proposal.yes_weight += weight
        else:
            proposal.no_weight += weight

        return True, f"Vote recorded for '{voter_id}'. Quadratic weight: {weight:.4f}."

    def evaluate_proposal(
        self,
        proposal_id: str,
        finalize: bool = True,
    ) -> Tuple[bool, ProposalStatus, str]:
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return False, ProposalStatus.REJECTED, f"Proposal '{proposal_id}' not found."

        total_active_power = self.registry.total_active_voting_power()
        if total_active_power <= 0:
            if finalize:
                proposal.status = ProposalStatus.REJECTED
            return False, proposal.status, "Zero active voting power in the swarm."

        # Compute quorum participation based on effective voting power of participating voters
        participating_power = sum(
            self.registry.get_agent(vid).effective_voting_power
            for vid in proposal.votes.keys()
            if self.registry.get_agent(vid) and not self.registry.get_agent(vid).is_jailed
        )
        current_quorum_achieved = participating_power / total_active_power

        quorum_met = current_quorum_achieved >= proposal.target_quorum
        passed = quorum_met and (proposal.yes_weight > proposal.no_weight)

        if finalize:
            proposal.status = ProposalStatus.PASSED if passed else ProposalStatus.REJECTED

        if not quorum_met:
            return False, proposal.status, (
                f"Quorum not achieved: {current_quorum_achieved * 100:.1f}% "
                f"< target {proposal.target_quorum * 100:.1f}%."
            )

        if passed:
            return True, proposal.status, (
                f"Proposal passed: YES weight {proposal.yes_weight:.2f} "
                f"> NO weight {proposal.no_weight:.2f}."
            )
        else:
            return False, proposal.status, (
                f"Proposal rejected: NO weight {proposal.no_weight:.2f} "
                f">= YES weight {proposal.yes_weight:.2f}."
            )

    def execute_proposal(self, proposal_id: str) -> Tuple[bool, str]:
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return False, f"Proposal '{proposal_id}' not found."
        if proposal.status != ProposalStatus.PASSED:
            return False, f"Proposal '{proposal_id}' has not passed (status={proposal.status.value})."

        self.treasury_balance -= proposal.requested_amount
        proposal.status = ProposalStatus.EXECUTED
        return True, (
            f"Executed proposal '{proposal_id}'. Allocated {proposal.requested_amount:.2f}. "
            f"Remaining treasury: {self.treasury_balance:.2f}."
        )
