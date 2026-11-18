"""
Tribunal Arbitration Manager, Juror Consensus, and Automated Escrow Slashing.
"""

from __future__ import annotations
import time
from typing import Any, Dict, List, Optional, Tuple
from agent_arbitration.types import (
    AgentRole,
    BreachType,
    DisputeRecord,
    DisputeStatus,
    SlaAgreement,
    SlaExecutionTrace,
    VerdictOutcome,
)
from agent_arbitration.identity import IdentityRegistry
from agent_arbitration.sla import SlaManager


class TribunalManager:
    """
    Manages deterministic SLA dispute tribunals, evidence trace verification,
    juror voting, conflict of interest enforcement, and automated escrow slashing.
    """

    def __init__(
        self,
        identity_registry: IdentityRegistry,
        sla_manager: SlaManager,
        slashing_penalty_rate: float = 0.25,
        min_dispute_bond_ratio: float = 0.10,
    ) -> None:
        self.registry = identity_registry
        self.sla_manager = sla_manager
        self.slashing_penalty_rate = slashing_penalty_rate  # 25% of SLA escrow
        self.min_dispute_bond_ratio = min_dispute_bond_ratio  # 10% of SLA escrow
        self.disputes: Dict[str, DisputeRecord] = {}

    def initiate_dispute(
        self,
        dispute_id: str,
        sla_id: str,
        claimant_id: str,
        claim_reason: str,
        dispute_bond: float,
    ) -> Tuple[bool, str]:
        """
        Initiates a dispute against an active SLA.
        Requires claimant to post a dispute bond >= min_dispute_bond_ratio * escrow_amount.
        """
        if dispute_id in self.disputes:
            return False, f"Dispute '{dispute_id}' already exists."

        sla = self.sla_manager.agreements.get(sla_id)
        if not sla:
            return False, f"SLA '{sla_id}' not found."
        if sla.is_completed:
            return False, f"SLA '{sla_id}' has already been completed."
        if sla.is_disputed:
            return False, f"SLA '{sla_id}' is already under dispute."

        # Verify claimant is a party to the SLA
        if claimant_id not in (sla.client_id, sla.provider_id):
            return False, f"Claimant '{claimant_id}' is not a party to SLA '{sla_id}'."

        defendant_id = sla.provider_id if claimant_id == sla.client_id else sla.client_id

        claimant = self.registry.get_agent(claimant_id)
        if not claimant:
            return False, f"Claimant '{claimant_id}' not found in identity registry."
        if claimant.is_jailed:
            return False, f"Claimant '{claimant_id}' is jailed."

        # Verify minimum dispute bond (>= 10% of escrow amount)
        min_required_bond = sla.escrow_amount * self.min_dispute_bond_ratio
        if dispute_bond < min_required_bond:
            return False, (
                f"Dispute bond {dispute_bond:.2f} is below minimum required "
                f"{min_required_bond:.2f} ({self.min_dispute_bond_ratio * 100:.0f}% of escrow)."
            )

        now = time.time()
        sla.is_disputed = True
        dispute = DisputeRecord(
            dispute_id=dispute_id,
            sla_id=sla_id,
            claimant_id=claimant_id,
            defendant_id=defendant_id,
            claim_reason=claim_reason,
            dispute_bond=dispute_bond,
            status=DisputeStatus.INITIATED,
            created_at=now,
            evidence_trace=None,
            juror_votes={},
            verdict_outcome=None,
            slashed_penalty=0.0,
            forfeited_bond=0.0,
            closed_at=None,
            breach_type=BreachType.NONE,
        )
        self.disputes[dispute_id] = dispute
        return True, f"Dispute '{dispute_id}' initiated for SLA '{sla_id}' with bond {dispute_bond:.2f}."

    def submit_trace_evidence(
        self,
        dispute_id: str,
        trace: SlaExecutionTrace,
    ) -> Tuple[bool, str]:
        """
        Attaches cryptographic execution trace evidence to the dispute and evaluates SLA invariants.
        """
        dispute = self.disputes.get(dispute_id)
        if not dispute:
            return False, f"Dispute '{dispute_id}' not found."
        if dispute.status in (DisputeStatus.VERDICT_RESOLVED, DisputeStatus.ESCROW_SETTLED):
            return False, f"Dispute '{dispute_id}' is already resolved/settled."
        if trace.sla_id != dispute.sla_id:
            return False, f"Trace SLA ID '{trace.sla_id}' does not match dispute SLA ID '{dispute.sla_id}'."

        sla = self.sla_manager.agreements.get(dispute.sla_id)
        if not sla:
            return False, f"SLA '{dispute.sla_id}' not found."

        # Audit trace against SLA invariants
        is_compliant, breach_type, explanation = self.sla_manager.audit_trace(sla, trace)
        dispute.evidence_trace = trace
        dispute.breach_type = breach_type
        dispute.status = DisputeStatus.TRIBUNAL_EVALUATION

        return True, f"Trace evidence accepted. Compliance: {is_compliant}. Breach: {breach_type.value}. {explanation}"

    def cast_juror_vote(
        self,
        dispute_id: str,
        juror_id: str,
        favor_claimant: bool,
    ) -> Tuple[bool, str]:
        """
        Allows designated, unjailed, non-conflicted tribunal jurors to cast a vote on the dispute.
        """
        dispute = self.disputes.get(dispute_id)
        if not dispute:
            return False, f"Dispute '{dispute_id}' not found."
        if dispute.status in (DisputeStatus.VERDICT_RESOLVED, DisputeStatus.ESCROW_SETTLED):
            return False, f"Dispute '{dispute_id}' is already closed."

        # Juror eligibility check
        juror = self.registry.get_agent(juror_id)
        if not juror:
            return False, f"Juror '{juror_id}' not found."
        if juror.is_jailed:
            return False, f"Juror '{juror_id}' is jailed."
        if juror.role != AgentRole.TRIBUNAL_JUROR:
            return False, f"Agent '{juror_id}' is not designated as a TRIBUNAL_JUROR."

        # Conflict of interest check: party to the SLA cannot vote
        sla = self.sla_manager.agreements.get(dispute.sla_id)
        if sla and juror_id in (sla.client_id, sla.provider_id):
            return False, f"Juror '{juror_id}' is a conflicted party to SLA '{dispute.sla_id}'."
        if juror_id in (dispute.claimant_id, dispute.defendant_id):
            return False, f"Juror '{juror_id}' is a conflicted party in dispute '{dispute_id}'."

        if juror_id in dispute.juror_votes:
            return False, f"Juror '{juror_id}' has already voted on dispute '{dispute_id}'."

        dispute.juror_votes[juror_id] = favor_claimant
        dispute.status = DisputeStatus.TRIBUNAL_EVALUATION
        vote_label = "Claimant" if favor_claimant else "Defendant"
        return True, f"Juror '{juror_id}' voted in favor of {vote_label}."

    def resolve_arbitration_and_slash(self, dispute_id: str) -> Dict[str, Any]:
        """
        Deterministically resolves the dispute, executes automated stake slashing,
        reputation penalties, escrow settlement, and jailing mechanics.
        """
        dispute = self.disputes.get(dispute_id)
        if not dispute:
            raise ValueError(f"Dispute '{dispute_id}' not found.")
        if dispute.status == DisputeStatus.ESCROW_SETTLED:
            raise ValueError(f"Dispute '{dispute_id}' has already been settled.")

        sla = self.sla_manager.agreements.get(dispute.sla_id)
        if not sla:
            raise ValueError(f"SLA '{dispute.sla_id}' not found.")

        # Determine verdict
        # 1. Deterministic trace breach: if execution trace has an objective breach, claimant wins
        if dispute.breach_type != BreachType.NONE:
            favor_claimant = True
        elif dispute.evidence_trace is not None and dispute.breach_type == BreachType.NONE:
            # Trace was verified and is compliant!
            # If jurors voted, count them; otherwise, defendant wins because trace proves compliance
            if dispute.juror_votes:
                claimant_votes = sum(1 for v in dispute.juror_votes.values() if v)
                defendant_votes = len(dispute.juror_votes) - claimant_votes
                favor_claimant = claimant_votes > defendant_votes
            else:
                favor_claimant = False
        else:
            # No trace submitted: rely on juror consensus
            if dispute.juror_votes:
                claimant_votes = sum(1 for v in dispute.juror_votes.values() if v)
                defendant_votes = len(dispute.juror_votes) - claimant_votes
                favor_claimant = claimant_votes > defendant_votes
            else:
                # Default to defendant if claimant failed to present evidence or juror votes
                favor_claimant = False

        now = time.time()
        dispute.closed_at = now

        if favor_claimant:
            dispute.verdict_outcome = VerdictOutcome.CLAIMANT_FAVORED
            winner_id = dispute.claimant_id
            loser_id = dispute.defendant_id

            # Provider stake slashing: exact 25% of SLA escrow amount
            slashed_penalty = sla.escrow_amount * self.slashing_penalty_rate
            _, actual_slashed, is_jailed = self.registry.slash_agent(
                loser_id,
                slashed_penalty,
                reason=f"SLA breach penalty ({dispute.breach_type.value})",
            )
            dispute.slashed_penalty = actual_slashed

            # Refund SLA escrow to claimant (client)
            _, refunded_escrow, _ = self.sla_manager.release_escrow(sla.sla_id, winner_id)

            # Return dispute bond to claimant
            bond_returned = dispute.dispute_bond
            forfeited_bond = 0.0

            dispute.status = DisputeStatus.ESCROW_SETTLED

            return {
                "dispute_id": dispute_id,
                "winner": winner_id,
                "loser": loser_id,
                "verdict_outcome": VerdictOutcome.CLAIMANT_FAVORED.value,
                "breach_type": dispute.breach_type.value,
                "slashed_penalty_collected": actual_slashed,
                "refunded_escrow": refunded_escrow,
                "bond_returned": bond_returned,
                "forfeited_bond": forfeited_bond,
                "defendant_jailed": is_jailed,
            }
        else:
            dispute.verdict_outcome = VerdictOutcome.DEFENDANT_FAVORED
            winner_id = dispute.defendant_id
            loser_id = dispute.claimant_id

            # Unfounded / frivolous dispute:
            # Forfeit claimant's dispute bond to defendant & treasury
            forfeited_bond = dispute.dispute_bond
            dispute.forfeited_bond = forfeited_bond
            self.registry.penalize_reputation(loser_id, penalty=10.0)

            # Release locked escrow to provider (defendant)
            _, released_escrow, _ = self.sla_manager.release_escrow(sla.sla_id, winner_id)

            dispute.status = DisputeStatus.ESCROW_SETTLED

            return {
                "dispute_id": dispute_id,
                "winner": winner_id,
                "loser": loser_id,
                "verdict_outcome": VerdictOutcome.DEFENDANT_FAVORED.value,
                "breach_type": dispute.breach_type.value,
                "slashed_penalty_collected": 0.0,
                "refunded_escrow": 0.0,
                "forfeited_bond": forfeited_bond,
                "bond_returned": 0.0,
                "released_escrow": released_escrow,
                "defendant_jailed": False,
            }
