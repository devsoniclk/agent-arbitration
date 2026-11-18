# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-18

### Added
- **Proof-of-Compute Staking:** Sybil-resistant staking requiring minimum bond ($S_{\min} \ge 2,000$) and sub-linear voting power scaling $V_i = \sqrt{S_i} \times B_i$.
- **Dynamic Quorum Governance:** Risk-adjusted quorum scaling $Q(t) = Q_{\text{base}} + \Delta Q \cdot \min(1.0, \text{Requested} / \text{Treasury})$.
- **Quadratic Resource Voting:** Non-collusive quadratic voting allocation $W_i = \sqrt{C_i} \times B_i$.
- **SLA Contracts & Escrow:** Programmatic SLA agreements with locked escrow, latency bounds, accuracy thresholds, and tool whitelisting.
- **Deterministic Tribunal & Slashing:** Cryptographic execution trace auditing with automatic 25% stake slashing, escrow refund, reputation decay, and rogue agent jailing.
- **Action Witness DAG:** Tamper-evident SHA-256 state root ledger linking every state mutation.
- **CLI Suite:** `verify`, `benchmark`, `info` subcommands with 26 operational test gates.
