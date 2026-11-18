"""
Unified Agent Arbitration and Governance Engine.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Set, Tuple
from agent_arbitration.types import (
    AgentIdentity,
    AgentRole,
    DisputeRecord,
    Proposal,
    ProposalStatus,
    SlaAgreement,
    SlaExecutionTrace,
)
from agent_arbitration.identity import IdentityRegistry
from agent_arbitration.governance import GovernanceManager
from agent_arbitration.sla import SlaManager
from agent_arbitration.tribunal import TribunalManager
from agent_arbitration.witness import WitnessDAG


class AgentArbitrationEngine:
    """
    High-level production engine orchestrating decentralized proof-of-compute
    staking, quadratic governance, SLA escrow contracts, deterministic tribunal
    arbitration, and cryptographic witness DAG verification.
    """

    def __init__(
        self,
        treasury_balance: float = 100_000.0,
        min_stake: float = 2_000.0,
        slashing_penalty_rate: float = 0.25,
        min_dispute_bond_ratio: float = 0.10,
        min_stake_bond: Optional[float] = None,
        initial_treasury: Optional[float] = None,
        slashing_rate: Optional[float] = None,
    ) -> None:
        actual_min_stake = min_stake_bond if min_stake_bond is not None else min_stake
        actual_treasury = initial_treasury if initial_treasury is not None else treasury_balance
        actual_slashing = slashing_rate if slashing_rate is not None else slashing_penalty_rate
        self.registry = IdentityRegistry(min_stake_bond=actual_min_stake)
        self.governance = GovernanceManager(
            identity_registry=self.registry,
            initial_treasury=actual_treasury,
        )
        self.sla_manager = SlaManager(identity_registry=self.registry)
        self.tribunal = TribunalManager(
            identity_registry=self.registry,
            sla_manager=self.sla_manager,
            slashing_penalty_rate=actual_slashing,
            min_dispute_bond_ratio=min_dispute_bond_ratio,
        )
        self.witness_dag = WitnessDAG()

    @property
    def treasury_balance(self) -> float:
        return self.governance.treasury_balance

    @property
    def min_stake(self) -> float:
        return self.registry.min_stake_bond

    @property
    def agents(self) -> Dict[str, AgentIdentity]:
        return self.registry.agents

    @property
    def slas(self) -> Dict[str, SlaAgreement]:
        return self.sla_manager.agreements

    @property
    def disputes(self) -> Dict[str, DisputeRecord]:
        return self.tribunal.disputes

    @property
    def proposals(self) -> Dict[str, Proposal]:
        return self.governance.proposals

    @property
    def state_root(self) -> str:
        return self.witness_dag.state_root

    @property
    def action_witness_dag(self) -> List[str]:
        """List of witness hashes in chronological order."""
        return [w.witness_hash for w in self.witness_dag.witness_chain]

    # --- Agent Staking & Identity ---

    def register_agent(
        self,
        agent_id: str,
        public_key: str,
        role: AgentRole,
        stake: float,
        benchmark_score: float,
    ) -> Tuple[bool, str]:
        ok, msg = self.registry.register_agent(
            agent_id=agent_id,
            public_key=public_key,
            role=role,
            initial_stake=stake,
            benchmark_score=benchmark_score,
        )
        if ok:
            agent = self.registry.get_agent(agent_id)
            power = agent.effective_voting_power if agent else 0.0
            self.witness_dag.record_action(
                action_type="AGENT_REGISTERED",
                entity_id=agent_id,
                payload={"role": role.value, "stake": stake, "power": power},
            )
        return ok, msg

    def deposit_stake(self, agent_id: str, amount: float) -> Tuple[bool, str]:
        ok, msg = self.registry.deposit_stake(agent_id, amount)
        if ok:
            self.witness_dag.record_action(
                action_type="STAKE_DEPOSITED",
                entity_id=agent_id,
                payload={"amount": amount},
            )
        return ok, msg

    # --- Algorithmic Governance & Quadratic Voting ---

    def create_resource_proposal(
        self,
        proposal_id: str,
        creator_id: str,
        requested_amount: float,
        title: str,
        description: str = "",
    ) -> Tuple[bool, str]:
        ok, msg = self.governance.create_proposal(
            proposal_id=proposal_id,
            proposer_id=creator_id,
            title=title,
            description=description,
            requested_amount=requested_amount,
        )
        if ok:
            prop = self.governance.proposals[proposal_id]
            self.witness_dag.record_action(
                action_type="PROPOSAL_CREATED",
                entity_id=proposal_id,
                payload={"creator": creator_id, "amount": requested_amount, "quorum": prop.target_quorum},
            )
        return ok, msg

    def cast_quadratic_vote(
        self,
        proposal_id: str,
        voter_id: str,
        credits_allocated: float,
        vote_yes: bool,
    ) -> Tuple[bool, str]:
        ok, msg = self.governance.cast_quadratic_vote(
            proposal_id=proposal_id,
            voter_id=voter_id,
            credits_allocated=credits_allocated,
            vote_yes=vote_yes,
        )
        if ok:
            prop = self.governance.proposals[proposal_id]
            _, weight, _ = prop.votes[voter_id]
            self.witness_dag.record_action(
                action_type="VOTE_CAST",
                entity_id=proposal_id,
                payload={"voter": voter_id, "credits": credits_allocated, "weight": weight, "vote_yes": vote_yes},
            )
        return ok, msg

    def evaluate_proposal(self, proposal_id: str, finalize: bool = True) -> Tuple[bool, ProposalStatus, str]:
        ok, status, msg = self.governance.evaluate_proposal(proposal_id, finalize=finalize)
        self.witness_dag.record_action(
            action_type="PROPOSAL_EVALUATED",
            entity_id=proposal_id,
            payload={"passed": ok, "status": status.value, "finalize": finalize, "msg": msg},
        )
        return ok, status, msg

    def execute_proposal(self, proposal_id: str) -> Tuple[bool, str]:
        ok, msg = self.governance.execute_proposal(proposal_id)
        if ok:
            prop = self.governance.proposals[proposal_id]
            self.witness_dag.record_action(
                action_type="PROPOSAL_EXECUTED",
                entity_id=proposal_id,
                payload={"amount": prop.requested_amount, "treasury_after": self.treasury_balance},
            )
        return ok, msg

    # --- SLA Agreements & Escrow ---

    def register_sla(
        self,
        sla_or_id: Any,
        client_id: Optional[str] = None,
        provider_id: Optional[str] = None,
        max_latency_ms: Optional[float] = None,
        min_accuracy_threshold: Optional[float] = None,
        allowed_tools: Optional[Set[str]] = None,
        escrow_amount: Optional[float] = None,
        duration_seconds: float = 3600.0,
    ) -> Tuple[bool, str]:
        if isinstance(sla_or_id, SlaAgreement):
            sla = sla_or_id
            ok, msg = self.sla_manager.register_sla(
                sla_id=sla.sla_id,
                client_id=sla.client_id,
                provider_id=sla.provider_id,
                max_latency_ms=sla.max_latency_ms,
                min_accuracy_threshold=sla.min_accuracy_threshold,
                allowed_tools=sla.allowed_tools,
                escrow_amount=sla.escrow_amount,
                duration_seconds=duration_seconds,
            )
            sla_id = sla.sla_id
            escrow = sla.escrow_amount
        else:
            sla_id = str(sla_or_id)
            escrow = escrow_amount or 0.0
            ok, msg = self.sla_manager.register_sla(
                sla_id=sla_id,
                client_id=client_id or "",
                provider_id=provider_id or "",
                max_latency_ms=max_latency_ms or 500.0,
                min_accuracy_threshold=min_accuracy_threshold or 0.90,
                allowed_tools=allowed_tools or set(),
                escrow_amount=escrow,
                duration_seconds=duration_seconds,
            )

        if ok:
            self.witness_dag.record_action(
                action_type="SLA_REGISTERED",
                entity_id=sla_id,
                payload={"escrow": escrow},
            )
        return ok, msg

    # --- Dispute Arbitration & Tribunal ---

    def initiate_dispute(
        self,
        dispute_id: str,
        sla_id: str,
        claimant_id: str,
        claim_reason: str,
        dispute_bond: float,
    ) -> Tuple[bool, str]:
        ok, msg = self.tribunal.initiate_dispute(
            dispute_id=dispute_id,
            sla_id=sla_id,
            claimant_id=claimant_id,
            claim_reason=claim_reason,
            dispute_bond=dispute_bond,
        )
        if ok:
            self.witness_dag.record_action(
                action_type="DISPUTE_INITIATED",
                entity_id=dispute_id,
                payload={"sla_id": sla_id, "claimant": claimant_id, "bond": dispute_bond},
            )
        return ok, msg

    def submit_trace_evidence(
        self,
        dispute_id: str,
        trace: SlaExecutionTrace,
    ) -> Tuple[bool, str]:
        ok, msg = self.tribunal.submit_trace_evidence(dispute_id, trace)
        if ok:
            self.witness_dag.record_action(
                action_type="TRACE_EVIDENCE_SUBMITTED",
                entity_id=dispute_id,
                payload={"trace_id": trace.trace_id, "merkle_root": trace.execution_merkle_root},
            )
        return ok, msg

    def cast_tribunal_juror_vote(
        self,
        dispute_id: str,
        juror_id: str,
        favor_claimant: bool,
    ) -> Tuple[bool, str]:
        ok, msg = self.tribunal.cast_juror_vote(dispute_id, juror_id, favor_claimant)
        if ok:
            self.witness_dag.record_action(
                action_type="JUROR_VOTE_CAST",
                entity_id=dispute_id,
                payload={"juror": juror_id, "favor_claimant": favor_claimant},
            )
        return ok, msg

    def resolve_arbitration_and_slash(self, dispute_id: str) -> Dict[str, Any]:
        result = self.tribunal.resolve_arbitration_and_slash(dispute_id)
        self.witness_dag.record_action(
            action_type="DISPUTE_SETTLED",
            entity_id=dispute_id,
            payload={
                "winner": result["winner"],
                "loser": result["loser"],
                "verdict": result["verdict_outcome"],
                "slashed": result.get("slashed_penalty_collected", 0.0),
                "forfeited_bond": result.get("forfeited_bond", 0.0),
            },
        )
        return result

    def create_proposal(
        self,
        proposal_id: str,
        creator_id: str,
        title: str,
        description: str,
        requested_amount: float,
    ) -> Tuple[bool, str]:
        """Convenience alias for create_resource_proposal."""
        return self.create_resource_proposal(
            proposal_id=proposal_id,
            creator_id=creator_id,
            requested_amount=requested_amount,
            title=title,
            description=description,
        )

    def export_summary(self) -> Dict[str, Any]:
        """Exports a verifiable state summary snapshot."""
        return {
            "state_root": self.state_root,
            "witness_dag_depth": len(self.witness_dag),
            "treasury_balance": self.treasury_balance,
            "total_agents": len(self.agents),
            "total_active_voting_power": self.registry.total_active_voting_power(),
            "active_proposals": len(self.proposals),
            "total_slas": len(self.slas),
            "total_disputes": len(self.disputes),
        }

    def verify_integrity(self) -> bool:
        """Verifies cryptographic state witness DAG consistency."""
        return self.witness_dag.verify_chain_integrity()


ArbitrationEngine = AgentArbitrationEngine
