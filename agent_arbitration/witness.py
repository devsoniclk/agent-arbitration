"""
Cryptographic State Witness DAG and Audit Ledger.
"""

from __future__ import annotations
import hashlib
import json
import time
from typing import Any, Dict, List, Optional
from agent_arbitration.types import StateWitness


class WitnessDAG:
    """
    Cryptographic tamper-evident action witness DAG and state root tracker.
    Every state change in the multi-agent arbitration engine is hashed, chained,
    and verified.
    """

    def __init__(self, genesis_label: str = "genesis_agent_arbitration") -> None:
        self.genesis_hash: str = hashlib.sha256(genesis_label.encode()).hexdigest()
        self.state_root: str = self.genesis_hash
        self.witness_chain: List[StateWitness] = []

    def record_action(
        self,
        action_type: str,
        entity_id: str,
        payload: Dict[str, Any],
    ) -> StateWitness:
        """
        Records an action into the witness DAG, computes cryptographic hashes,
        updates state root, and appends the witness record.
        """
        step_index = len(self.witness_chain) + 1
        prev_hash = self.state_root
        now = time.time()

        serialized_payload = json.dumps(payload, sort_keys=True)
        payload_hash = hashlib.sha256(serialized_payload.encode()).hexdigest()

        # Chain witness hash: sha256(step:action:entity:prev:payload:timestamp)
        chain_input = f"{step_index}:{action_type}:{entity_id}:{prev_hash}:{payload_hash}:{now:.6f}"
        witness_hash = hashlib.sha256(chain_input.encode()).hexdigest()

        witness = StateWitness(
            step_index=step_index,
            action_type=action_type,
            entity_id=entity_id,
            prev_hash=prev_hash,
            payload_hash=payload_hash,
            witness_hash=witness_hash,
            timestamp=now,
        )

        self.witness_chain.append(witness)
        self.state_root = witness_hash
        return witness

    def verify_chain_integrity(self) -> bool:
        """
        Verifies that every node in the DAG is sequentially indexed, correctly linked
        to its predecessor hash, and matches its expected witness hash.
        """
        if not self.witness_chain:
            return self.state_root == self.genesis_hash

        expected_prev = self.genesis_hash
        for i, node in enumerate(self.witness_chain):
            if node.step_index != i + 1:
                return False
            if node.prev_hash != expected_prev:
                return False

            chain_input = (
                f"{node.step_index}:{node.action_type}:{node.entity_id}:"
                f"{node.prev_hash}:{node.payload_hash}:{node.timestamp:.6f}"
            )
            recalculated = hashlib.sha256(chain_input.encode()).hexdigest()
            if recalculated != node.witness_hash:
                return False

            expected_prev = node.witness_hash

        return self.state_root == self.witness_chain[-1].witness_hash

    def export_ledger(self) -> List[Dict[str, Any]]:
        """Returns the serialized witness ledger."""
        return [w.to_dict() for w in self.witness_chain]

    def __len__(self) -> int:
        return len(self.witness_chain)

    def __getitem__(self, idx: int) -> StateWitness:
        return self.witness_chain[idx]
