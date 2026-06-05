"""SAR workflow tests — timeliness (31 CFR 1020.320), Travel Rule (1010.410(f))."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from payments_agent_audit.governance.sar_workflow import (
    SARWorkflowAudit,
    SARWorkflowError,
)

DET = datetime(2026, 1, 1, tzinfo=UTC)


def test_30_day_deadline_with_suspect() -> None:
    sw = SARWorkflowAudit()
    r = sw.check_timeliness(
        detection_date=DET,
        proposed_filing_date=DET + timedelta(days=29),
        suspect_identified=True,
        case_id="c1",
    )
    assert r.meets_deadline is True
    assert r.deadline == DET + timedelta(days=30)


def test_30_day_deadline_boundary_inclusive() -> None:
    """Filing exactly on day 30 meets the deadline (<=, not <)."""
    sw = SARWorkflowAudit()
    r = sw.check_timeliness(
        detection_date=DET,
        proposed_filing_date=DET + timedelta(days=30),
        suspect_identified=True,
        case_id="c1b",
    )
    assert r.meets_deadline is True
    assert r.days_remaining == 0


def test_30_day_deadline_missed() -> None:
    sw = SARWorkflowAudit()
    r = sw.check_timeliness(
        detection_date=DET,
        proposed_filing_date=DET + timedelta(days=31),
        suspect_identified=True,
        case_id="c2",
    )
    assert r.meets_deadline is False
    assert r.days_remaining < 0


def test_60_day_deadline_no_suspect() -> None:
    sw = SARWorkflowAudit()
    r = sw.check_timeliness(
        detection_date=DET,
        proposed_filing_date=DET + timedelta(days=55),
        suspect_identified=False,
        case_id="c3",
    )
    assert r.meets_deadline is True
    assert r.deadline == DET + timedelta(days=60)


def test_travel_rule_in_scope_missing_fields() -> None:
    sw = SARWorkflowAudit()
    r = sw.check_travel_rule(amount_usd=5000, fields={"originator_name": "A"}, transmittal_id="t1")
    assert r.in_scope is True
    assert r.compliant is False
    assert "beneficiary_name" in r.missing_fields


def test_travel_rule_in_scope_complete() -> None:
    sw = SARWorkflowAudit()
    fields = {
        "originator_name": "Alice",
        "originator_account": "111",
        "originator_address": "1 St",
        "amount": "5000",
        "beneficiary_name": "Bob",
        "beneficiary_account": "222",
    }
    r = sw.check_travel_rule(amount_usd=5000, fields=fields, transmittal_id="t2")
    assert r.compliant is True


def test_travel_rule_below_threshold_compliant() -> None:
    sw = SARWorkflowAudit()
    r = sw.check_travel_rule(amount_usd=100, fields={}, transmittal_id="t3")
    assert r.in_scope is False
    assert r.compliant is True


def test_travel_rule_threshold_boundary() -> None:
    sw = SARWorkflowAudit()
    assert sw.check_travel_rule(amount_usd=3000, fields={}, transmittal_id="t4").in_scope is True
    assert (
        sw.check_travel_rule(amount_usd=2999.99, fields={}, transmittal_id="t5").in_scope is False
    )


def test_vague_disposition_rejected() -> None:
    sw = SARWorkflowAudit()
    for vague in ("model decision", "score below threshold", "per policy", ""):
        with pytest.raises(SARWorkflowError):
            sw.validate_alert_disposition(vague)


def test_specific_disposition_accepted() -> None:
    sw = SARWorkflowAudit()
    sw.validate_alert_disposition(
        "Counterparty is a long-standing payroll vendor; pattern matches prior 18 months."
    )


def test_emits_to_chain(chain) -> None:
    sw = SARWorkflowAudit(audit_chain=chain)
    sw.check_timeliness(
        detection_date=DET,
        proposed_filing_date=DET + timedelta(days=5),
        suspect_identified=True,
        case_id="c9",
    )
    sw.check_travel_rule(amount_usd=4000, fields={}, transmittal_id="t9")
    assert any(e.event_type.value == "payments.sar_filed" for e in chain._events)
    assert any(e.event_type.value == "payments.travel_rule_recorded" for e in chain._events)
