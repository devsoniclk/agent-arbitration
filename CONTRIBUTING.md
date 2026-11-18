# Contributing to agent-arbitration

Thank you for your interest in contributing to `agent-arbitration`! We welcome contributions to improve multi-agent DAO governance, cryptographic trace audits, and dispute resolution mechanisms.

## Development Workflow

1. Clone the repository:
   ```bash
   git clone https://github.com/devsoniclk/agent-arbitration.git
   cd agent-arbitration
   ```

2. Set up virtual environment & install development dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```

3. Run the automated test suite and verification gates:
   ```bash
   pytest tests/ -v --cov=agent_arbitration
   agent-arbitration verify
   ```

4. Code Style & Standards:
   - Type hints on all functions and methods.
   - Comprehensive docstrings with operational rationale.
   - 100% test pass rate required before pull requests are merged.
