"""Property-based tests for the finality algebra, the irreversibility gate,
DEFCON transition-direction algebra, veto un-self-clearability, and OFAC
matching (the volume tier, §7).
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from payments_agent_audit.governance.audit_chain import AuditChain
from payments_agent_audit.governance.autonomy_ladder import (
    PRE_AUTH_CONTROLS,
    Attestation,
    AutonomyLadderGate,
    AutonomyTier,
    PromotionRequest,
)
from payments_agent_audit.governance.defcon import (
    DEFCON,
    DEFCONMachine,
    DEFCONOverrideRejectedError,
    PaymentRiskMetrics,
)
from payments_agent_audit.governance.ofac_screening import (
    OFACScreener,
    SanctionedParty,
    ScreeningStatus,
)
from payments_agent_audit.governance.rail_finality import is_irreversible, known_rails
from payments_agent_audit.governance.sovereign_veto import (
    SovereignVeto,
    VetoBlockedError,
    VetoReason,
)
from tests.conftest import StaticSanctionsList

CREATED = "2026-06-05T00:00:00+00:00"
_FULL_ATT = tuple(
    Attestation(c, True, "mrm", "second_line_mrm", CREATED, f"e://{c}")
    for c in (
        "sovereign_veto_load_tested",
        "audit_ledger_min_window",
        "shadow_mode_min_window",
        "circuit_breaker_recent",
        "pre_auth_control_effective",  # so a named pre-auth control unblocks in production
    )
)

# Controls that on their own act after authorization.
_POST_HOC = ["post_hoc_veto", "post_settlement_review", "next_day_recon"]


@settings(max_examples=300)
@given(
    rail=st.sampled_from(list(known_rails())),
    pre_auth=st.lists(st.sampled_from(sorted(PRE_AUTH_CONTROLS)), max_size=3),
    post=st.lists(st.sampled_from(_POST_HOC), min_size=1, max_size=3),
    tier=st.sampled_from(
        [AutonomyTier.A3_SUPERVISED_AUTONOMOUS, AutonomyTier.A4_PRODUCTION_AUTONOMOUS]
    ),
)
def test_irreversibility_algebra(rail, pre_auth, post, tier) -> None:
    """The refusal fires IFF the rail is irreversible AND there is no
    pre-authorization control — independent of how many post-hoc controls
    are stacked. ACH/card (reversible) never trigger the irreversibility refusal."""
    chain = AuditChain(deployer_id="prop", chain_creation_iso=CREATED)
    gate = AutonomyLadderGate(audit_chain=chain, mode="production")
    controls = frozenset(pre_auth + post)
    req = PromotionRequest(
        target_tier=tier,
        decision_class="x",
        program_id="p",
        moves_money=True,
        rail_id=rail,
        controls=controls,
        attestations=_FULL_ATT,
    )
    decision = gate.evaluate(req)
    expected_refusal = is_irreversible(rail) and len(set(pre_auth)) == 0
    assert decision.irreversibility_refusal is expected_refusal
    # When there is no irreversibility refusal and full attestations exist,
    # the promotion is granted.
    if not expected_refusal:
        assert decision.granted is True


@settings(max_examples=300)
@given(
    fraud=st.floats(min_value=0.0, max_value=0.2),
    loss=st.floats(min_value=0.0, max_value=0.2),
    fails=st.integers(min_value=0, max_value=12),
    feed=st.booleans(),
)
def test_defcon_escalation_is_monotone_and_halt_is_sticky(fraud, loss, fails, feed) -> None:
    m = DEFCONMachine()
    level = m.evaluate(
        PaymentRiskMetrics(
            fraud_rate=fraud,
            daily_loss_rate=loss,
            consecutive_settlement_failures=fails,
            sanctions_feed_available=feed,
        )
    )
    # sanctions-feed outage always forces HALT
    if not feed:
        assert level is DEFCON.HALT
    # once HALT, automatic evaluation can never leave it
    if level is DEFCON.HALT:
        for _ in range(4):
            m.evaluate(PaymentRiskMetrics(0.0, 0.0, 0))
        assert m.level is DEFCON.HALT


@settings(max_examples=200)
@given(target=st.sampled_from([DEFCON.NORMAL, DEFCON.CAUTION, DEFCON.ALERT]))
def test_halt_deescalation_must_be_adjacent(target) -> None:
    """From HALT, any manual_override target below DANGER is rejected."""
    m = DEFCONMachine()
    m.evaluate(PaymentRiskMetrics(0.06, 0.0, 0))
    assert m.level is DEFCON.HALT
    try:
        m.manual_override(target, "op", "x")
        raise AssertionError("expected rejection")
    except DEFCONOverrideRejectedError:
        pass


@settings(max_examples=200)
@given(agent_id=st.text(min_size=1, max_size=16))
def test_agent_can_never_self_clear(agent_id) -> None:
    v = SovereignVeto(agent_id)
    v.trigger(VetoReason.MANUAL_OPERATOR, "monitor", "x")
    try:
        v.clear("done", operator_id=agent_id)
        raise AssertionError("self-clear should be blocked")
    except VetoBlockedError:
        pass


@settings(max_examples=200)
@given(
    sanctioned=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Zs")), min_size=4, max_size=20
    )
)
def test_exact_name_always_flags(sanctioned) -> None:
    """An exact (normalized) name match always produces a held potential match."""
    name = sanctioned.strip()
    if not name:
        return
    provider = StaticSanctionsList([SanctionedParty(uid="x", name=name)])
    screener = OFACScreener(provider)
    result = screener.screen(name)
    assert result.status is ScreeningStatus.POTENTIAL_MATCH
    assert result.is_held is True
