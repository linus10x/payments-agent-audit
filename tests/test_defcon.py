"""DEFCONMachine unit tests — corrected P4 transition-direction guard."""

from __future__ import annotations

import pytest

from payments_agent_audit.governance.defcon import (
    DEFCON,
    DEFCONMachine,
    DEFCONOverrideRejectedError,
    PaymentRiskMetrics,
)
from payments_agent_audit.governance.sovereign_veto import ProductionModeError
from tests.conftest import FakeAuthorizer

NORMAL = PaymentRiskMetrics(fraud_rate=0.0, daily_loss_rate=0.0, consecutive_settlement_failures=0)


def test_normal_baseline() -> None:
    m = DEFCONMachine()
    assert m.evaluate(NORMAL) is DEFCON.NORMAL


def test_escalation_is_immediate() -> None:
    m = DEFCONMachine()
    m.evaluate(PaymentRiskMetrics(0.01, 0.0, 0))  # CAUTION band (>=0.008, <0.015)
    assert m.level is DEFCON.CAUTION
    m.evaluate(PaymentRiskMetrics(0.06, 0.0, 0))  # HALT band
    assert m.level is DEFCON.HALT


def test_sanctions_feed_outage_forces_halt() -> None:
    m = DEFCONMachine()
    m.evaluate(PaymentRiskMetrics(0.0, 0.0, 0, sanctions_feed_available=False))
    assert m.level is DEFCON.HALT


def test_auto_deescalation_from_halt_blocked() -> None:
    m = DEFCONMachine()
    m.evaluate(PaymentRiskMetrics(0.06, 0.0, 0))
    assert m.level is DEFCON.HALT
    for _ in range(5):
        m.evaluate(NORMAL)
    assert m.level is DEFCON.HALT  # only manual_override can de-escalate


def test_hysteresis_deescalation_requires_confirmations() -> None:
    m = DEFCONMachine()
    m.evaluate(PaymentRiskMetrics(0.035, 0.0, 0))  # DANGER
    assert m.level is DEFCON.DANGER
    m.evaluate(NORMAL)
    assert m.level is DEFCON.DANGER  # 1/3
    m.evaluate(NORMAL)
    assert m.level is DEFCON.DANGER  # 2/3
    m.evaluate(NORMAL)
    assert m.level is DEFCON.NORMAL  # 3/3 confirmed


def test_direct_halt_to_normal_jump_forbidden() -> None:
    m = DEFCONMachine()
    m.evaluate(PaymentRiskMetrics(0.06, 0.0, 0))
    with pytest.raises(DEFCONOverrideRejectedError, match="adjacent level"):
        m.manual_override(DEFCON.NORMAL, "op", "recovered")


def test_halt_to_danger_adjacent_step_allowed() -> None:
    m = DEFCONMachine()
    m.evaluate(PaymentRiskMetrics(0.06, 0.0, 0))
    m.manual_override(DEFCON.DANGER, "op", "stepping down")
    assert m.level is DEFCON.DANGER


def test_production_mode_requires_authorizer() -> None:
    with pytest.raises(ProductionModeError):
        DEFCONMachine(mode="production")


def test_manual_override_requires_credential_in_production() -> None:
    m = DEFCONMachine(authorizer=FakeAuthorizer(), mode="production")
    m.evaluate(PaymentRiskMetrics(0.06, 0.0, 0))
    with pytest.raises(DEFCONOverrideRejectedError, match="requires a 'credential'"):
        m.manual_override(DEFCON.DANGER, "op", "x")


def test_manual_override_rejects_bad_credential() -> None:
    m = DEFCONMachine(authorizer=FakeAuthorizer(), mode="production")
    m.evaluate(PaymentRiskMetrics(0.06, 0.0, 0))
    with pytest.raises(DEFCONOverrideRejectedError, match="authentication failed"):
        m.manual_override(DEFCON.DANGER, "op", "x", credential="bad")


def test_manual_override_denied_by_authorizer() -> None:
    m = DEFCONMachine(authorizer=FakeAuthorizer(allow=False), mode="production")
    m.evaluate(PaymentRiskMetrics(0.06, 0.0, 0))
    with pytest.raises(DEFCONOverrideRejectedError, match="denied"):
        m.manual_override(DEFCON.DANGER, "op", "x", credential="valid-token")


def test_authenticated_override_records_to_chain(chain) -> None:
    auth = FakeAuthorizer(valid_credentials={"tok": "principal-bob"})
    m = DEFCONMachine(audit_chain=chain, authorizer=auth, mode="production")
    m.evaluate(PaymentRiskMetrics(0.06, 0.0, 0))
    m.manual_override(DEFCON.DANGER, "op", "stepping down", credential="tok")
    halt_events = [e for e in chain._events if e.event_type.value == "risk.halt"]
    assert halt_events
    deesc = [e for e in chain._events if e.event_type.value == "risk.deescalation"]
    assert deesc and deesc[-1].actor_id == "principal-bob"


def test_invalid_mode_rejected() -> None:
    with pytest.raises(ValueError):
        DEFCONMachine(mode="bogus")


def test_defcon_ordering() -> None:
    assert DEFCON.HALT > DEFCON.NORMAL
    assert DEFCON.NORMAL < DEFCON.CAUTION
    assert DEFCON.ALERT >= DEFCON.ALERT
    assert DEFCON.CAUTION <= DEFCON.DANGER


def test_consecutive_settlement_failures_escalate() -> None:
    m = DEFCONMachine()
    m.evaluate(PaymentRiskMetrics(0.0, 0.0, 6))
    assert m.level is DEFCON.ALERT
