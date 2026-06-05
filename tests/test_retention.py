"""Retention-floor tests — 5-year BSA floor, not a 90-day default."""

from __future__ import annotations

from datetime import timedelta

from payments_agent_audit.governance.retention import (
    AUDIT_CHAIN_RETENTION_FLOOR,
    BSA_RECORD_RETENTION,
    meets_retention_floor,
)


def test_bsa_floor_is_five_years() -> None:
    assert timedelta(days=5 * 365) == BSA_RECORD_RETENTION
    assert AUDIT_CHAIN_RETENTION_FLOOR == BSA_RECORD_RETENTION


def test_ninety_days_fails_floor() -> None:
    assert meets_retention_floor(timedelta(days=90)) is False


def test_five_years_meets_floor() -> None:
    assert meets_retention_floor(timedelta(days=5 * 365)) is True


def test_seven_years_meets_floor() -> None:
    assert meets_retention_floor(timedelta(days=7 * 365)) is True
