"""
Service Level Agreement (SLA) Contracts and Cryptographic Execution Trace Audit.
"""

from __future__ import annotations
import hashlib
import time
from typing import Dict, List, Optional, Set, Tuple
from agent_arbitration.types import BreachType, SlaAgreement, SlaExecutionTrace
from agent_arbitration.identity import IdentityRegistry


class SlaManager:
    """
    Manages programmatic SLA contracts, escrow holding, and execution trace verification.
    """

    def __init__(self, identity_registry: IdentityRegistry) -> None:
        self.registry = identity_registry
        self.agreements: Dict[str, SlaAgreement] = {}
        self.locked_escrow: Dict[str, float] = {}  # sla_id -> amount

    def register_sla(
        self,
        sla_id: str,
        client_id: str,
        provider_id: str,
        max_latency_ms: float,
        min_accuracy_threshold: float,
        allowed_tools: Set[str],
        escrow_amount: float,
        duration_seconds: float = 3600.0,
    ) -> Tuple[bool, str]:
        if sla_id in self.agreements:
            return False, f"SLA '{sla_id}' already registered."

        client = self.registry.get_agent(client_id)
        if not client:
            return False, f"Client agent '{client_id}' not found."
        if client.is_jailed:
            return False, f"Client agent '{client_id}' is jailed."

        provider = self.registry.get_agent(provider_id)
        if not provider:
            return False, f"Provider agent '{provider_id}' not found."
        if provider.is_jailed:
            return False, f"Provider agent '{provider_id}' is jailed."

        if escrow_amount <= 0:
            return False, "Escrow amount must be positive."

        now = time.time()
        sla = SlaAgreement(
            sla_id=sla_id,
            client_id=client_id,
            provider_id=provider_id,
            max_latency_ms=max_latency_ms,
            min_accuracy_threshold=min_accuracy_threshold,
            allowed_tools=set(allowed_tools),
            escrow_amount=escrow_amount,
            expiry_timestamp=now + duration_seconds,
            is_completed=False,
            is_disputed=False,
        )
        self.agreements[sla_id] = sla
        self.locked_escrow[sla_id] = escrow_amount
        return True, f"SLA '{sla_id}' registered and {escrow_amount:.2f} locked in escrow."

    def audit_trace(self, sla: SlaAgreement, trace: SlaExecutionTrace) -> Tuple[bool, BreachType, str]:
        """
        Deterministically evaluates an execution trace against the SLA invariants.
        Returns: (is_compliant, breach_type, explanation)
        """
        # 1. Latency check
        if trace.execution_time_ms > sla.max_latency_ms:
            return (
                False,
                BreachType.LATENCY_EXCEEDED,
                (
                    f"Latency breached: {trace.execution_time_ms:.1f}ms "
                    f"> SLA max {sla.max_latency_ms:.1f}ms."
                ),
            )

        # 2. Accuracy check
        if trace.accuracy_metric < sla.min_accuracy_threshold:
            return (
                False,
                BreachType.ACCURACY_DEGRADED,
                (
                    f"Accuracy breached: {trace.accuracy_metric:.4f} "
                    f"< SLA min threshold {sla.min_accuracy_threshold:.4f}."
                ),
            )

        # 3. Tool containment check
        for tool in trace.tools_called:
            if tool not in sla.allowed_tools:
                return (
                    False,
                    BreachType.FORBIDDEN_TOOL,
                    f"Forbidden tool invocation detected: '{tool}' not in {sorted(list(sla.allowed_tools))}.",
                )

        # 4. Cryptographic execution Merkle root integrity
        if not trace.execution_merkle_root or len(trace.execution_merkle_root) != 64:
            return (
                False,
                BreachType.INCORRECT_OUTPUT,
                "Invalid execution Merkle root hash format.",
            )

        return True, BreachType.NONE, "Execution trace strictly complies with all SLA parameters."

    def release_escrow(self, sla_id: str, recipient_id: str) -> Tuple[bool, float, str]:
        if sla_id not in self.locked_escrow:
            return False, 0.0, f"No locked escrow for SLA '{sla_id}'."

        amount = self.locked_escrow.pop(sla_id)
        sla = self.agreements.get(sla_id)
        if sla:
            sla.is_completed = True
        return True, amount, f"Released {amount:.2f} from SLA '{sla_id}' to '{recipient_id}'."
