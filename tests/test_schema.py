"""AuditEvent schema tests."""

from __future__ import annotations

import pytest

from payments_agent_audit.governance.audit_chain import AuditChainTamperError
from payments_agent_audit.schemas.audit_event import (
    AuditChain,
    AuditEvent,
    AuditEventType,
    AutonomyLevel,
)


def test_create_computes_hash() -> None:
    e = AuditEvent.create(
        event_type=AuditEventType.OFAC_SCREENED,
        autonomy_level=AutonomyLevel.A2,
        agent_id="x",
        payload={"a": 1},
        prev_hash="0" * 64,
    )
    assert len(e.event_hash) == 64
    assert e.event_hash == e._compute_hash()


def test_frozen_event_is_immutable() -> None:
    e = AuditEvent.create(
        event_type=AuditEventType.OFAC_SCREENED,
        autonomy_level=AutonomyLevel.A2,
        agent_id="x",
        payload={"a": 1},
        prev_hash="0" * 64,
    )
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        e.agent_id = "y"  # type: ignore[misc]


def test_from_jsonl_roundtrip() -> None:
    e = AuditEvent.create(
        event_type=AuditEventType.SAR_FILED,
        autonomy_level=AutonomyLevel.A2,
        agent_id="sar",
        payload={"case": "c1"},
        prev_hash="0" * 64,
    )
    replayed = AuditEvent.from_jsonl(e.to_dict())
    assert replayed.event_hash == e.event_hash


def test_from_jsonl_detects_tamper() -> None:
    e = AuditEvent.create(
        event_type=AuditEventType.SAR_FILED,
        autonomy_level=AutonomyLevel.A2,
        agent_id="sar",
        payload={"case": "c1"},
        prev_hash="0" * 64,
    )
    data = e.to_dict()
    data["payload"] = {"case": "tampered"}
    with pytest.raises(AuditChainTamperError):
        AuditEvent.from_jsonl(data)


def test_to_jsonl_is_sorted_json() -> None:
    e = AuditEvent.create(
        event_type=AuditEventType.SAR_FILED,
        autonomy_level=AutonomyLevel.A2,
        agent_id="sar",
        payload={"b": 2, "a": 1},
        prev_hash="0" * 64,
    )
    line = e.to_jsonl()
    assert line.index('"a"') < line.index('"b"')


def test_reexported_auditchain_is_class() -> None:
    assert AuditChain.__name__ == "AuditChain"


def test_schema_getattr_unknown_raises() -> None:
    import payments_agent_audit.schemas.audit_event as mod

    with pytest.raises(AttributeError):
        mod.NoSuchSymbol  # noqa: B018


def test_all_payment_event_types_present() -> None:
    for name in (
        "OFAC_SCREENED",
        "OFAC_HIT_DISPOSITIONED",
        "SAR_FILED",
        "TRAVEL_RULE_RECORDED",
        "REG_E_ERROR_RESOLVED",
        "RAIL_FINALITY_ASSESSED",
        "IRREVERSIBLE_PROMOTION_REFUSED",
        "SPONSOR_BANK_OVERSIGHT",
    ):
        assert hasattr(AuditEventType, name)
