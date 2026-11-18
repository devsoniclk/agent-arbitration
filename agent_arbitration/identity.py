"""
Identity and Proof-of-Compute Staking Manager for Swarm Agents.
"""

from __future__ import annotations
import math
from typing import Dict, List, Optional, Tuple
from agent_arbitration.types import AgentIdentity, AgentRole


class IdentityRegistry:
    """
    Manages agent identities, proof-of-compute stake bonds,
    sub-linear voting power, jailing mechanics, and reputation tracking.
    """

    def __init__(self, min_stake_bond: float = 2000.0) -> None:
        self.min_stake_bond = min_stake_bond
        self.agents: Dict[str, AgentIdentity] = {}

    def register_agent(
        self,
        agent_id: str,
        public_key: str,
        role: AgentRole,
        initial_stake: float,
        benchmark_score: float,
    ) -> Tuple[bool, str]:
        """
        Registers a new agent. Rejects registration if initial stake is below min_stake_bond.
        """
        if agent_id in self.agents:
            return False, f"Agent '{agent_id}' is already registered."
        if initial_stake < self.min_stake_bond:
            return False, (
                f"Initial stake {initial_stake:.2f} is below minimum requirement "
                f"{self.min_stake_bond:.2f}."
            )
        if not (0.0 <= benchmark_score <= 1.0):
            return False, f"Benchmark score {benchmark_score} must be between 0.0 and 1.0."

        agent = AgentIdentity(
            agent_id=agent_id,
            public_key=public_key,
            role=role,
            stake_balance=initial_stake,
            benchmark_score=benchmark_score,
            reputation_score=100.0,
            slashed_total=0.0,
            is_jailed=False,
        )
        self.agents[agent_id] = agent
        return True, f"Agent '{agent_id}' registered successfully."

    def get_agent(self, agent_id: str) -> Optional[AgentIdentity]:
        return self.agents.get(agent_id)

    def total_active_voting_power(self) -> float:
        """Sum of effective voting power of all active, unjailed agents."""
        return sum(agent.effective_voting_power for agent in self.agents.values() if not agent.is_jailed)

    def deposit_stake(self, agent_id: str, amount: float) -> Tuple[bool, str]:
        if amount <= 0:
            return False, "Deposit amount must be positive."
        agent = self.agents.get(agent_id)
        if not agent:
            return False, f"Agent '{agent_id}' not found."
        agent.stake_balance += amount
        if agent.is_jailed and agent.stake_balance >= self.min_stake_bond:
            agent.is_jailed = False
        return True, f"Deposited {amount:.2f} to '{agent_id}'. New balance: {agent.stake_balance:.2f}."

    def slash_agent(self, agent_id: str, penalty: float, reason: str = "") -> Tuple[bool, float, bool]:
        """
        Slashes stake from agent.
        Returns: (success, actual_deducted, is_now_jailed)
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return False, 0.0, False

        deducted = min(agent.stake_balance, penalty)
        agent.stake_balance -= deducted
        agent.slashed_total += deducted
        agent.reputation_score = max(0.0, agent.reputation_score - 20.0)

        # Trigger jailing if balance falls below minimum stake
        if agent.stake_balance < self.min_stake_bond:
            agent.is_jailed = True

        return True, deducted, agent.is_jailed

    def penalize_reputation(self, agent_id: str, penalty: float) -> bool:
        agent = self.agents.get(agent_id)
        if not agent:
            return False
        agent.reputation_score = max(0.0, agent.reputation_score - penalty)
        return True

    def reward_reputation(self, agent_id: str, boost: float = 2.0) -> bool:
        agent = self.agents.get(agent_id)
        if not agent:
            return False
        agent.reputation_score = min(100.0, agent.reputation_score + boost)
        return True

    def list_jurors(self) -> List[AgentIdentity]:
        """Returns all unjailed agents designated as TRIBUNAL_JUROR."""
        return [
            agent for agent in self.agents.values()
            if agent.role == AgentRole.TRIBUNAL_JUROR and not agent.is_jailed
        ]
