"""SovereignVeto unit tests — corrected P2 (fail-closed prod + authenticated principal)."""

from __future__ import annotations

import pytest

from payments_agent_audit.governance.sovereign_veto import (
    ProductionModeError,
    SovereignVeto,
    VetoBlockedError,
    VetoReason,
)
from tests.conftest import FakeAuthorizer


def test_trigger_blocks_execution() -> None:
    v = SovereignVeto("agent")
    assert v.allow_execution() is True
    v.trigger(VetoReason.SANCTIONS_HIT, "ofac", "potential match")
    assert v.allow_execution() is False
    assert v.is_vetoed is True


def test_production_mode_requires_authorizer() -> None:
    with pytest.raises(ProductionModeError):
        SovereignVeto("agent", mode="production")


def test_production_mode_with_authorizer_starts() -> None:
    v = SovereignVeto("agent", authorizer=FakeAuthorizer(), mode="production")
    assert v.mode == "production"


def test_invalid_mode_rejected() -> None:
    with pytest.raises(ValueError):
        SovereignVeto("agent", mode="bogus")


def test_self_clear_forbidden_advisory() -> None:
    v = SovereignVeto("zeus")
    v.trigger(VetoReason.MANUAL_OPERATOR, "zeus", "x")
    with pytest.raises(VetoBlockedError, match="self-clearing forbidden"):
        v.clear("done", operator_id="zeus")


def test_self_clear_forbidden_even_with_permissive_authorizer() -> None:
    # Authorizer authenticates the credential to principal == agent_id.
    auth = FakeAuthorizer(valid_credentials={"tok": "zeus"}, allow=True)
    v = SovereignVeto("zeus", authorizer=auth, mode="production")
    v.trigger(VetoReason.MANUAL_OPERATOR, "monitor", "x")
    with pytest.raises(VetoBlockedError, match="self-clearing forbidden"):
        v.clear("done", credential="tok")


def test_clear_requires_credential_when_authorizer_wired() -> None:
    v = SovereignVeto("zeus", authorizer=FakeAuthorizer(), mode="production")
    v.trigger(VetoReason.MANUAL_OPERATOR, "monitor", "x")
    with pytest.raises(VetoBlockedError, match="requires a 'credential'"):
        v.clear("done", operator_id="operator-001")  # free string not accepted


def test_clear_rejects_unauthenticated_credential() -> None:
    v = SovereignVeto("zeus", authorizer=FakeAuthorizer(), mode="production")
    v.trigger(VetoReason.MANUAL_OPERATOR, "monitor", "x")
    with pytest.raises(VetoBlockedError, match="authentication failed"):
        v.clear("done", credential="bad-token")


def test_clear_rejected_when_authorizer_denies() -> None:
    auth = FakeAuthorizer(allow=False)
    v = SovereignVeto("zeus", authorizer=auth, mode="production")
    v.trigger(VetoReason.MANUAL_OPERATOR, "monitor", "x")
    with pytest.raises(VetoBlockedError, match="denied"):
        v.clear("done", credential="valid-token")


def test_authenticated_clear_succeeds_and_binds_principal() -> None:
    auth = FakeAuthorizer(valid_credentials={"tok": "principal-jane"}, allow=True)
    v = SovereignVeto("zeus", authorizer=auth, mode="production")
    v.trigger(VetoReason.SANCTIONS_HIT, "ofac", "match")
    cleared = v.clear("reviewed, false positive", credential="tok")
    assert len(cleared) == 1
    assert cleared[0].cleared_by == "principal-jane"  # principal, not a free string
    assert v.allow_execution() is True


def test_advisory_clear_requires_operator_id() -> None:
    v = SovereignVeto("zeus")
    v.trigger(VetoReason.MANUAL_OPERATOR, "op", "x")
    with pytest.raises(VetoBlockedError, match="non-empty operator_id"):
        v.clear("done", operator_id="")


def test_clear_specific_veto_id() -> None:
    v = SovereignVeto("zeus")
    r1 = v.trigger(VetoReason.MANUAL_OPERATOR, "op", "x")
    v.trigger(VetoReason.ANOMALY_DETECTED, "monitor", "y")
    v.clear("done", operator_id="op2", veto_id=r1.veto_id)
    assert v.is_vetoed is True  # the second veto is still active
    assert len(v.active_vetos()) == 1


def test_history_and_callbacks() -> None:
    triggered, cleared = [], []
    v = SovereignVeto("zeus", on_veto=triggered.append, on_clear=cleared.append)
    v.trigger(VetoReason.MANUAL_OPERATOR, "op", "x")
    v.clear("done", operator_id="op2")
    assert len(v.history()) == 1
    assert len(triggered) == 1 and len(cleared) == 1
