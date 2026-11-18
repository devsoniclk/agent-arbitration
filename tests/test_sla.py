"""
Unit tests for SlaManager and execution trace auditing.
"""

import hashlib
import time
import pytest
from agent_arbitration.identity import IdentityRegistry
from agent_arbitration.sla import SlaManager
from agent_arbitration.types import AgentRole, BreachType, SlaAgreement, SlaExecutionTrace


@pytest.fixture
def setup_sla():
    reg = IdentityRegistry(min_stake_bond=2000.0)
    reg.register_agent("client_01", "pk_c", AgentRole.ORCHESTRATOR, 5000.0, 0.95)
    reg.register_agent("provider_01", "pk_p", AgentRole.SWARM_WORKER, 5000.0, 0.90)
    sla_mgr = SlaManager(identity_registry=reg)
    return reg, sla_mgr


def test_register_sla_success_and_validation(setup_sla):
    reg, sla_mgr = setup_sla

    ok, msg = sla_mgr.register_sla(
        sla_id="sla_01",
        client_id="client_01",
        provider_id="provider_01",
        max_latency_ms=500.0,
        min_accuracy_threshold=0.90,
        allowed_tools={"vector_search", "code_eval"},
        escrow_amount=1500.0,
    )
    assert ok is True
    assert "sla_01" in sla_mgr.agreements
    assert sla_mgr.locked_escrow["sla_01"] == 1500.0

    # Duplicate rejected
    dup, _ = sla_mgr.register_sla("sla_01", "client_01", "provider_01", 500.0, 0.90, set(), 1000.0)
    assert dup is False

    # Jailed party rejected
    reg.get_agent("provider_01").is_jailed = True
    jail_sla, _ = sla_mgr.register_sla("sla_02", "client_01", "provider_01", 500.0, 0.90, set(), 1000.0)
    assert jail_sla is False

    # Zero escrow rejected
    reg.get_agent("provider_01").is_jailed = False
    zero_esc, _ = sla_mgr.register_sla("sla_03", "client_01", "provider_01", 500.0, 0.90, set(), 0.0)
    assert zero_esc is False


def test_audit_trace_compliant(setup_sla):
    _, sla_mgr = setup_sla
    sla_mgr.register_sla(
        "sla_01", "client_01", "provider_01", 500.0, 0.90, {"vector_search", "code_eval"}, 1000.0
    )
    sla = sla_mgr.agreements["sla_01"]

    trace = SlaExecutionTrace(
        trace_id="tr_ok",
        sla_id="sla_01",
        execution_time_ms=320.0,
        accuracy_metric=0.95,
        tools_called=["vector_search"],
        execution_merkle_root=hashlib.sha256(b"merkle_clean").hexdigest(),
        trace_signature="sig_clean",
    )
    compliant, breach, msg = sla_mgr.audit_trace(sla, trace)
    assert compliant is True
    assert breach == BreachType.NONE


def test_audit_trace_latency_breach(setup_sla):
    _, sla_mgr = setup_sla
    sla_mgr.register_sla("sla_01", "client_01", "provider_01", 400.0, 0.90, {"vector_search"}, 1000.0)
    sla = sla_mgr.agreements["sla_01"]

    trace = SlaExecutionTrace(
        trace_id="tr_lat",
        sla_id="sla_01",
        execution_time_ms=650.0,
        accuracy_metric=0.95,
        tools_called=["vector_search"],
        execution_merkle_root=hashlib.sha256(b"root").hexdigest(),
        trace_signature="sig",
    )
    compliant, breach, msg = sla_mgr.audit_trace(sla, trace)
    assert compliant is False
    assert breach == BreachType.LATENCY_EXCEEDED
    assert "Latency breached" in msg


def test_audit_trace_accuracy_breach(setup_sla):
    _, sla_mgr = setup_sla
    sla_mgr.register_sla("sla_01", "client_01", "provider_01", 500.0, 0.92, {"vector_search"}, 1000.0)
    sla = sla_mgr.agreements["sla_01"]

    trace = SlaExecutionTrace(
        trace_id="tr_acc",
        sla_id="sla_01",
        execution_time_ms=250.0,
        accuracy_metric=0.88,
        tools_called=["vector_search"],
        execution_merkle_root=hashlib.sha256(b"root").hexdigest(),
        trace_signature="sig",
    )
    compliant, breach, msg = sla_mgr.audit_trace(sla, trace)
    assert compliant is False
    assert breach == BreachType.ACCURACY_DEGRADED
    assert "Accuracy breached" in msg


def test_audit_trace_forbidden_tool(setup_sla):
    _, sla_mgr = setup_sla
    sla_mgr.register_sla("sla_01", "client_01", "provider_01", 500.0, 0.90, {"vector_search"}, 1000.0)
    sla = sla_mgr.agreements["sla_01"]

    trace = SlaExecutionTrace(
        trace_id="tr_tool",
        sla_id="sla_01",
        execution_time_ms=200.0,
        accuracy_metric=0.95,
        tools_called=["vector_search", "unauthorized_network_eval"],
        execution_merkle_root=hashlib.sha256(b"root").hexdigest(),
        trace_signature="sig",
    )
    compliant, breach, msg = sla_mgr.audit_trace(sla, trace)
    assert compliant is False
    assert breach == BreachType.FORBIDDEN_TOOL
    assert "Forbidden tool invocation" in msg


def test_audit_trace_invalid_merkle_root(setup_sla):
    _, sla_mgr = setup_sla
    sla_mgr.register_sla("sla_01", "client_01", "provider_01", 500.0, 0.90, {"tool"}, 1000.0)
    sla = sla_mgr.agreements["sla_01"]

    trace = SlaExecutionTrace(
        trace_id="tr_root",
        sla_id="sla_01",
        execution_time_ms=200.0,
        accuracy_metric=0.95,
        tools_called=["tool"],
        execution_merkle_root="short_invalid_root",
        trace_signature="sig",
    )
    compliant, breach, msg = sla_mgr.audit_trace(sla, trace)
    assert compliant is False
    assert breach == BreachType.INCORRECT_OUTPUT


def test_escrow_release(setup_sla):
    _, sla_mgr = setup_sla
    sla_mgr.register_sla("sla_01", "client_01", "provider_01", 500.0, 0.90, {"tool"}, 1000.0)

    ok, amount, msg = sla_mgr.release_escrow("sla_01", "provider_01")
    assert ok is True
    assert amount == 1000.0
    assert sla_mgr.agreements["sla_01"].is_completed is True
    assert "sla_01" not in sla_mgr.locked_escrow

    # Nonexistent escrow
    bad_rel, _, _ = sla_mgr.release_escrow("sla_01", "provider_01")
    assert bad_rel is False
