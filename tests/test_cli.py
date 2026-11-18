"""
Unit tests for CLI commands.
"""

import sys
from agent_arbitration.cli import main, run_verification, run_benchmark


def test_cli_verify():
    assert run_verification() is True


def test_cli_benchmark(capsys):
    run_benchmark()
    captured = capsys.readouterr()
    assert "AGENT ARBITRATION BENCHMARK" in captured.out
    assert "Integrity Verified: True" in captured.out


def test_cli_main_info(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["agent-arbitration", "info"])
    main()
    captured = capsys.readouterr()
    assert "Agent Arbitration CLI" in captured.out
    assert "Lakshitha Dananjaya" in captured.out


def test_cli_main_verify(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["agent-arbitration", "verify"])
    try:
        main()
    except SystemExit as e:
        assert e.code == 0
