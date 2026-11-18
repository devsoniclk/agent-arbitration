"""
High-throughput benchmark harness for Agent Arbitration.
"""

from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent_arbitration.cli import run_benchmark

if __name__ == "__main__":
    run_benchmark()
