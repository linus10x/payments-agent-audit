"""Reg E error-resolution tests (12 CFR 1005.11)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from payments_agent_audit.governance.reg_e import (
    ErrorType,
    RegEErrorResolution,
)

NOTICE = datetime(2026, 1, 1, tzinfo=UTC)


def test_resolved_within_initial_window_compliant() -> None:
    r = RegEErrorResolution().resolve(
        error_type=ErrorType.UNAUTHORIZED_TRANSFER,
        notice_date=NOTICE,
        investigation_completion_date=NOTICE + timedelta(days=8),
        provisional_credit_given=False,
        is_new_account_pos_or_foreign=False,
        claim_id="cl1",
    )
    assert r.compliant is True
    assert r.provisional_credit_required is False


def test_extended_without_provisional_credit_noncompliant() -> None:
    r = RegEErrorResolution().resolve(
        error_type=ErrorType.UNAUTHORIZED_TRANSFER,
        notice_date=NOTICE,
        investigation_completion_date=NOTICE + timedelta(days=20),
        provisional_credit_given=False,
        is_new_account_pos_or_foreign=False,
        claim_id="cl2",
    )
    assert r.compliant is False
    assert r.provisional_credit_required is True


def test_extended_with_provisional_credit_compliant() -> None:
    r = RegEErrorResolution().resolve(
        error_type=ErrorType.UNAUTHORIZED_TRANSFER,
        notice_date=NOTICE,
        investigation_completion_date=NOTICE + timedelta(days=40),
        provisional_credit_given=True,
        is_new_account_pos_or_foreign=False,
        claim_id="cl3",
    )
    assert r.compliant is True


def test_completed_past_extended_deadline_noncompliant() -> None:
    r = RegEErrorResolution().resolve(
        error_type=ErrorType.INCORRECT_AMOUNT,
        notice_date=NOTICE,
        investigation_completion_date=NOTICE + timedelta(days=50),
        provisional_credit_given=True,
        is_new_account_pos_or_foreign=False,
        claim_id="cl4",
    )
    assert r.compliant is False
    assert any("extended deadline" in f for f in r.failures)


def test_new_account_20_day_initial_window() -> None:
    """D2: a new-account claim completed at day 15 — past the standard 10-day
    window but within the new-account 20-business-day window — is compliant
    WITHOUT provisional credit (12 CFR 1005.11(c)(3))."""
    r = RegEErrorResolution().resolve(
        error_type=ErrorType.UNAUTHORIZED_TRANSFER,
        notice_date=NOTICE,
        investigation_completion_date=NOTICE + timedelta(days=15),
        provisional_credit_given=False,
        is_new_account_pos_or_foreign=True,
        claim_id="cl-na-1",
    )
    assert r.compliant is True
    assert r.provisional_credit_required is False


def test_standard_account_15_days_requires_provisional() -> None:
    """Contrast: a standard (non-new) account at day 15 IS past the 10-day
    window and requires provisional credit."""
    r = RegEErrorResolution().resolve(
        error_type=ErrorType.UNAUTHORIZED_TRANSFER,
        notice_date=NOTICE,
        investigation_completion_date=NOTICE + timedelta(days=15),
        provisional_credit_given=False,
        is_new_account_pos_or_foreign=False,
        claim_id="cl-std-1",
    )
    assert r.compliant is False


def test_new_account_90_day_window() -> None:
    r = RegEErrorResolution().resolve(
        error_type=ErrorType.UNAUTHORIZED_TRANSFER,
        notice_date=NOTICE,
        investigation_completion_date=NOTICE + timedelta(days=80),
        provisional_credit_given=True,
        is_new_account_pos_or_foreign=True,
        claim_id="cl5",
    )
    assert r.compliant is True
    assert r.investigation_deadline == NOTICE + timedelta(days=90)


def test_emits_to_chain(chain) -> None:
    RegEErrorResolution(audit_chain=chain).resolve(
        error_type=ErrorType.MISSING_STATEMENT_ENTRY,
        notice_date=NOTICE,
        investigation_completion_date=NOTICE + timedelta(days=5),
        provisional_credit_given=False,
        is_new_account_pos_or_foreign=False,
        claim_id="cl6",
    )
    assert any(e.event_type.value == "payments.reg_e_error_resolved" for e in chain._events)
