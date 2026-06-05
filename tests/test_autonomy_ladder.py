"""AutonomyLadderGate tests — P1 attestation + AL-PROBE-06 irreversibility gate."""

from __future__ import annotations

import pytest

from payments_agent_audit.governance.autonomy_ladder import (
    Attestation,
    AutonomyLadderGate,
    AutonomyTier,
    PromotionRefused,
    PromotionRequest,
)
from payments_agent_audit.governance.rail_finality import UnknownRailError

REQUIRED = (
    "sovereign_veto_load_tested",
    "audit_ledger_min_window",
    "shadow_mode_min_window",
    "circuit_breaker_recent",
)
# The 4 lower-gate criteria plus the pre-auth-effective attestation that unblocks
# an irreversible-rail promotion in production.
FULL = (*REQUIRED, "pre_auth_control_effective")


def _independent_attestations() -> tuple[Attestation, ...]:
    return tuple(
        Attestation(
            criterion=c,
            satisfied=True,
            attested_by="mrm-lead",
            attester_role="second_line_mrm",
            attested_at="2026-06-05T00:00:00+00:00",
            evidence_ref=f"evidence://{c}",
        )
        for c in FULL
    )


def _req(**kw) -> PromotionRequest:
    base = dict(
        target_tier=AutonomyTier.A3_SUPERVISED_AUTONOMOUS,
        decision_class="instant_payout",
        program_id="prog-1",
        moves_money=True,
        rail_id="fednow",
        controls=frozenset({"pre_auth_ofac_screening", "post_hoc_veto"}),
        attestations=_independent_attestations(),
    )
    base.update(kw)
    return PromotionRequest(**base)


# --- AL-PROBE-06 irreversibility -----------------------------------------


def test_irreversible_rail_post_hoc_only_refused(chain) -> None:
    gate = AutonomyLadderGate(audit_chain=chain, mode="production")
    d = gate.evaluate(_req(controls=frozenset({"post_hoc_veto"})))
    assert d.granted is False
    assert d.irreversibility_refusal is True
    refusal = [
        e for e in chain._events if e.event_type.value == "payments.irreversible_promotion_refused"
    ]
    assert refusal and refusal[0].payload["rail_id"] == "fednow"


def test_irreversible_rail_with_pre_auth_control_passes(chain) -> None:
    gate = AutonomyLadderGate(audit_chain=chain, mode="production")
    d = gate.evaluate(_req(controls=frozenset({"pre_auth_ofac_screening"})))
    assert d.granted is True
    assert d.irreversibility_refusal is False


def test_named_pre_auth_without_attestation_refused_in_production(chain) -> None:
    """D1 regression: a NAMED pre-auth control with no independent attestation
    that it is wired/effective does NOT unblock an irreversible-rail promotion in
    production — closing the bare-string bypass."""
    gate = AutonomyLadderGate(audit_chain=chain, mode="production")
    # Only the 4 lower-gate criteria are attested; the pre-auth-effective
    # attestation is absent even though the control string is listed.
    four = tuple(
        Attestation(c, True, "mrm", "second_line_mrm", "2026-06-05T00:00:00+00:00", f"e://{c}")
        for c in REQUIRED
    )
    d = gate.evaluate(_req(controls=frozenset({"pre_auth_ofac_screening"}), attestations=four))
    assert d.granted is False
    assert d.irreversibility_refusal is True
    assert any("not independently attested" in f for f in d.failures)


def test_pre_auth_attestation_must_be_independent(chain) -> None:
    """A first-line attestation of the pre-auth control is insufficient in production."""
    gate = AutonomyLadderGate(audit_chain=chain, mode="production")
    atts = tuple(
        Attestation(c, True, "mrm", "second_line_mrm", "2026-06-05T00:00:00+00:00", f"e://{c}")
        for c in REQUIRED
    ) + (
        Attestation(
            "pre_auth_control_effective",
            True,
            "build-eng",
            "first_line",
            "2026-06-05T00:00:00+00:00",
            "e://pre_auth",
        ),
    )
    d = gate.evaluate(_req(controls=frozenset({"pre_auth_ofac_screening"}), attestations=atts))
    assert d.granted is False
    assert d.irreversibility_refusal is True


def test_advisory_named_pre_auth_unblocks() -> None:
    """In advisory mode (explicitly labeled advisory), a named pre-auth control
    unblocks via set membership — the legacy behavior, no attestation required."""
    from datetime import timedelta

    gate = AutonomyLadderGate(mode="advisory")
    d = gate.evaluate(
        _req(
            controls=frozenset({"pre_auth_ofac_screening"}),
            attestations=(),
            sovereign_veto_load_tested_days=10,
            audit_ledger_running=timedelta(days=120),
            shadow_mode_running=timedelta(days=45),
            circuit_breaker_test_recent=True,
        )
    )
    assert d.irreversibility_refusal is False
    assert d.granted is True


def test_ach_not_subject_to_irreversibility_rule(chain) -> None:
    """ACH is non-final — post-hoc veto alone does NOT trigger the refusal."""
    gate = AutonomyLadderGate(audit_chain=chain, mode="production")
    d = gate.evaluate(_req(rail_id="ach", controls=frozenset({"post_hoc_veto"})))
    assert d.irreversibility_refusal is False
    assert d.granted is True  # attestations are present


def test_rtp_also_irreversible(chain) -> None:
    gate = AutonomyLadderGate(audit_chain=chain, mode="production")
    d = gate.evaluate(_req(rail_id="rtp", controls=frozenset({"post_hoc_veto"})))
    assert d.irreversibility_refusal is True


def test_non_money_moving_program_not_gated(chain) -> None:
    gate = AutonomyLadderGate(audit_chain=chain, mode="production")
    d = gate.evaluate(_req(moves_money=False, controls=frozenset({"post_hoc_veto"})))
    assert d.irreversibility_refusal is False


def test_unknown_rail_fails_closed(chain) -> None:
    gate = AutonomyLadderGate(audit_chain=chain, mode="production")
    with pytest.raises(UnknownRailError):
        gate.evaluate(_req(rail_id="carrier-pigeon", controls=frozenset({"post_hoc_veto"})))


# --- P1 attestation -------------------------------------------------------


def test_production_missing_attestation_refused(chain) -> None:
    gate = AutonomyLadderGate(audit_chain=chain, mode="production")
    d = gate.evaluate(_req(attestations=()))
    assert d.granted is False
    assert any("missing attestation" in f for f in d.failures)


def test_production_non_independent_attestation_refused(chain) -> None:
    gate = AutonomyLadderGate(audit_chain=chain, mode="production")
    first_line = tuple(
        Attestation(c, True, "build-eng", "first_line", "2026-06-05T00:00:00+00:00", f"e://{c}")
        for c in REQUIRED
    )
    d = gate.evaluate(_req(attestations=first_line))
    assert d.granted is False
    assert any("non-independent role" in f for f in d.failures)


def test_production_requires_audit_chain() -> None:
    with pytest.raises(ValueError):
        AutonomyLadderGate(mode="production")


def test_advisory_mode_accepts_booleans(chain) -> None:
    from datetime import timedelta

    gate = AutonomyLadderGate(mode="advisory")
    d = gate.evaluate(
        _req(
            controls=frozenset({"pre_auth_ofac_screening"}),
            attestations=(),
            sovereign_veto_load_tested_days=10,
            audit_ledger_running=timedelta(days=120),
            shadow_mode_running=timedelta(days=45),
            circuit_breaker_test_recent=True,
        )
    )
    assert d.granted is True


def test_advisory_mode_flags_insufficient_windows() -> None:
    from datetime import timedelta

    gate = AutonomyLadderGate(mode="advisory")
    d = gate.evaluate(
        _req(
            controls=frozenset({"pre_auth_ofac_screening"}),
            attestations=(),
            sovereign_veto_load_tested_days=0,
            audit_ledger_running=timedelta(days=10),
            shadow_mode_running=timedelta(days=5),
            circuit_breaker_test_recent=False,
        )
    )
    assert d.granted is False
    assert len(d.failures) == 4


def test_raise_if_refused() -> None:
    gate = AutonomyLadderGate(mode="advisory")
    d = gate.evaluate(_req(attestations=(), controls=frozenset({"post_hoc_veto"})))
    with pytest.raises(PromotionRefused):
        d.raise_if_refused()


def test_attestation_validates_fields() -> None:
    with pytest.raises(ValueError):
        Attestation("c", True, "", "second_line_mrm", "t", "e")
    with pytest.raises(ValueError):
        Attestation("c", True, "who", "second_line_mrm", "t", "")


def test_non_autonomous_tier_rejected(chain) -> None:
    gate = AutonomyLadderGate(audit_chain=chain, mode="production")
    d = gate.evaluate(_req(target_tier=AutonomyTier.A2_DELEGATED))
    assert d.granted is False
    assert any("not an autonomous-writer tier" in f for f in d.failures)


def test_a4_also_gated(chain) -> None:
    gate = AutonomyLadderGate(audit_chain=chain, mode="production")
    d = gate.evaluate(
        _req(
            target_tier=AutonomyTier.A4_PRODUCTION_AUTONOMOUS, controls=frozenset({"post_hoc_veto"})
        )
    )
    assert d.irreversibility_refusal is True


def test_tier_semantic_properties() -> None:
    assert AutonomyTier.A0_INFORMATIONAL.can_write is False
    assert AutonomyTier.A1_ASSISTED.requires_human_approval is True
    assert AutonomyTier.A2_DELEGATED.requires_envelope is True
    assert AutonomyTier.A3_SUPERVISED_AUTONOMOUS.is_autonomous_writer is True
