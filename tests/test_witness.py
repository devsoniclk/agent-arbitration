"""
Unit tests for WitnessDAG and Cryptographic Integrity Ledger.
"""

import json
from agent_arbitration.witness import WitnessDAG


def test_genesis_state_root():
    dag = WitnessDAG()
    assert len(dag) == 0
    assert len(dag.state_root) == 64
    assert dag.verify_chain_integrity() is True


def test_action_recording_and_chaining():
    dag = WitnessDAG()
    w1 = dag.record_action("AGENT_REGISTERED", "agent_01", {"stake": 2500.0})
    assert len(dag) == 1
    assert w1.step_index == 1
    assert w1.prev_hash == dag.genesis_hash
    assert dag.state_root == w1.witness_hash
    assert dag.verify_chain_integrity() is True

    w2 = dag.record_action("PROPOSAL_CREATED", "prop_01", {"amount": 5000.0})
    assert len(dag) == 2
    assert w2.step_index == 2
    assert w2.prev_hash == w1.witness_hash
    assert dag.state_root == w2.witness_hash
    assert dag.verify_chain_integrity() is True


def test_tamper_detection():
    dag = WitnessDAG()
    for i in range(5):
        dag.record_action("ACTION", f"e_{i}", {"val": i})

    assert dag.verify_chain_integrity() is True

    # Tamper with intermediate node payload
    dag.witness_chain[2].payload_hash = "0" * 64
    assert dag.verify_chain_integrity() is False


def test_export_ledger():
    dag = WitnessDAG()
    dag.record_action("ACTION_A", "e1", {"k": 1})
    dag.record_action("ACTION_B", "e2", {"k": 2})

    ledger = dag.export_ledger()
    assert len(ledger) == 2
    assert ledger[0]["action_type"] == "ACTION_A"
    assert ledger[1]["action_type"] == "ACTION_B"
