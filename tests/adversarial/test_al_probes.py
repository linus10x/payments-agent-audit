"""AL-PROBES — committed adversarial reproductions of the corrected primitives.

Each probe reconstructs the EXACT failing construction the corrected §2 spec
defends against, so a PASS is reproducible and reviewable (the original
ephemeral /tmp probes are gone — these are the committed replacements). The
five AL-PROBE-01..05 mirror the JPMC catalog's primitive probes; AL-PROBE-06
is NEW to this library — the rail-finality / irreversibility gate.

Run: ``pytest tests/adversarial/test_al_probes.py -v``
"""

from __future__ import annotations

import pytest

from payments_agent_audit.governance.audit_chain import (
    GENESIS_HASH,
    AuditChain,
    AuditChainTamperError,
    _compute_genesis_hash,
)
from payments_agent_audit.governance.autonomy_ladder import (
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
from payments_agent_audit.governance.effective_challenge_harness import (
    ChallengerIndependenceError,
    EffectiveChallengeHarness,
    IndependenceAttestation,
)
from payments_agent_audit.governance.sovereign_veto import (
    SovereignVeto,
    VetoBlockedError,
    VetoReason,
)
from tests.conftest import FakeAuthorizer

CREATED = "2026-06-05T00:00:00+00:00"


# ====================================================================== #
# AL-PROBE-01 — Level-gate: promote-without-lower-gates is REFUSED        #
# ====================================================================== #


def test_al_probe_01_promotion_without_gates_refused() -> None:
    """Attack: request A3 with no independent attestations of the lower-level
    controls. Pass = promotion refused (the gate does not trust an empty or
    caller-asserted evidence set)."""
    chain = AuditChain(deployer_id="probe", chain_creation_iso=CREATED)
    gate = AutonomyLadderGate(audit_chain=chain, mode="production")
    req = PromotionRequest(
        target_tier=AutonomyTier.A3_SUPERVISED_AUTONOMOUS,
        decision_class="instant_payout",
        program_id="attacker-prog",
        moves_money=True,
        rail_id="ach",  # reversible, so isolate the attestation failure
        controls=frozenset({"pre_auth_ofac_screening"}),
        attestations=(),  # <-- no lower-gate evidence
    )
    decision = gate.evaluate(req)
    assert decision.granted is False
    assert any("missing attestation" in f for f in decision.failures)
    # refusal recorded
    assert any(e.event_type.value == "governance.promotion_refused" for e in chain._events)


# ====================================================================== #
# AL-PROBE-02 — Sovereign veto: un-self-clearable, authenticated operator #
# ====================================================================== #


def test_al_probe_02_veto_unselfclearable_authenticated() -> None:
    """Attack: the vetoed agent tries to clear its own veto; and an attacker
    asserts a free-string operator without authentication. Pass = self-clear
    blocked, free-string clear blocked, only an authenticated principal clears."""
    auth = FakeAuthorizer(valid_credentials={"jane-token": "principal-jane"}, allow=True)
    veto = SovereignVeto("payment-agent", authorizer=auth, mode="production")
    veto.trigger(VetoReason.SANCTIONS_HIT, "ofac-monitor", "OFAC potential match")

    # (a) self-clear blocked even though jane-token would authenticate.
    self_auth = FakeAuthorizer(valid_credentials={"self": "payment-agent"}, allow=True)
    veto_self = SovereignVeto("payment-agent", authorizer=self_auth, mode="production")
    veto_self.trigger(VetoReason.SANCTIONS_HIT, "ofac-monitor", "match")
    with pytest.raises(VetoBlockedError, match="self-clearing forbidden"):
        veto_self.clear("clearing", credential="self")

    # (b) a free-string operator without a credential is rejected.
    with pytest.raises(VetoBlockedError, match="requires a 'credential'"):
        veto.clear("clearing", operator_id="totally-the-cco")

    # (c) only an authenticated principal clears, and it is the operator of record.
    cleared = veto.clear("reviewed; false positive", credential="jane-token")
    assert cleared[0].cleared_by == "principal-jane"
    assert veto.allow_execution() is True


# ====================================================================== #
# AL-PROBE-03 — Ledger: hardened chain verifies; tamper + regen detected  #
# ====================================================================== #


def test_al_probe_03_hardened_chain_does_not_false_tamper() -> None:
    """Attack surface = the reference defect: a clean deployer-keyed chain
    raised a FALSE tamper because verify() seeded '0'*64 unconditionally.
    Pass = the hardened chain verifies True, and its genesis seed is the
    deployer-keyed hash, not the sentinel."""
    from payments_agent_audit.schemas.audit_event import AuditEventType, AutonomyLevel

    chain = AuditChain(deployer_id="acme-pay-prod", chain_creation_iso=CREATED)
    chain.append(
        event_type=AuditEventType.OFAC_SCREENED,
        autonomy_level=AutonomyLevel.A2,
        agent_id="ofac",
        payload={"name": "x"},
    )
    assert chain.verify() is True  # NOT a false tamper
    chain.verify_strict()
    genesis = chain._events[0]
    assert genesis.prev_hash == _compute_genesis_hash("acme-pay-prod", CREATED)
    assert genesis.prev_hash != GENESIS_HASH


def test_al_probe_03b_inplace_tamper_and_regeneration_detected() -> None:
    """In-place tamper -> detected. End-to-end regeneration -> head diverges
    from the witnessed head."""
    from payments_agent_audit.schemas.audit_event import AuditEventType, AutonomyLevel

    chain = AuditChain(deployer_id="acme-pay-prod", chain_creation_iso=CREATED)
    for i in range(3):
        chain.append(AuditEventType.SAR_FILED, AutonomyLevel.A2, "sar", {"i": i})
    honest_head = chain.chain_head()

    # in-place tamper
    object.__setattr__(chain._events[2], "payload", {"i": 999})
    with pytest.raises(AuditChainTamperError):
        chain.verify_strict()

    # regeneration: a freshly-built chain is internally consistent but its head
    # does not match the witnessed honest head.
    forged = AuditChain(deployer_id="acme-pay-prod", chain_creation_iso=CREATED)
    forged.append(AuditEventType.SAR_FILED, AutonomyLevel.A2, "sar", {"i": 0, "evil": True})
    assert forged.verify() is True
    assert forged.chain_head() != honest_head


def test_al_probe_03c_legacy_chain_still_verifies() -> None:
    """The corrected seed branch must not break legacy chains: a legacy
    (sentinel-seeded) chain still verifies True."""
    import warnings

    from payments_agent_audit.schemas.audit_event import AuditEventType, AutonomyLevel

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        legacy = AuditChain()
        legacy.append(AuditEventType.SAR_FILED, AutonomyLevel.A2, "sar", {"i": 0})
        assert legacy.verify() is True


# ====================================================================== #
# AL-PROBE-04 — DEFCON: illegal one-call HALT->NORMAL fails safe          #
# ====================================================================== #


def test_al_probe_04_illegal_defcon_transition_fails_safe() -> None:
    """Attack: drive to HALT, then try a single-call HALT->NORMAL (both via
    the automatic path and via manual_override). Pass = automatic path refuses
    to leave HALT; manual one-shot HALT->NORMAL is rejected."""
    machine = DEFCONMachine()
    machine.evaluate(
        PaymentRiskMetrics(fraud_rate=0.06, daily_loss_rate=0.0, consecutive_settlement_failures=0)
    )
    assert machine.level is DEFCON.HALT

    # automatic de-escalation cannot leave HALT
    for _ in range(5):
        machine.evaluate(PaymentRiskMetrics(0.0, 0.0, 0))
    assert machine.level is DEFCON.HALT

    # one-call HALT -> NORMAL via override is rejected (transition-direction guard)
    with pytest.raises(DEFCONOverrideRejectedError, match="adjacent lower level"):
        machine.manual_override(DEFCON.NORMAL, "operator", "we are fine now")
    assert machine.level is DEFCON.HALT


# ====================================================================== #
# AL-PROBE-05 — Effective challenge: self-challenge is rejected           #
# ====================================================================== #


def test_al_probe_05_self_challenge_rejected() -> None:
    """Attack: a model owner wires the primary as its own challenger to get a
    clean accept_primary. Pass = construction rejected; and a non-independent
    (attested) challenger cannot reach accept_primary either."""
    primary = lambda x: "approve"  # noqa: E731
    with pytest.raises(ChallengerIndependenceError):
        EffectiveChallengeHarness(
            primary_model=primary,
            challenger_model=primary,  # same object
            eval_set=[("loan-1", "approve")],
            independence=IndependenceAttestation("owner", CREATED, True, True, True),
        )

    # A separate-but-non-independent challenger that always agrees cannot
    # produce a clean accept_primary.
    challenger = lambda x: "approve"  # noqa: E731
    harness = EffectiveChallengeHarness(
        primary_model=primary,
        challenger_model=challenger,
        eval_set=[("loan-1", "approve")],
        independence=IndependenceAttestation(
            "owner",
            CREATED,
            not_same_owner=False,
            not_same_vendor_family=False,
            not_same_prompt_template=False,
        ),
    )
    report = harness.run()
    assert report.recommendation != "accept_primary"
    assert report.independence_forced_downgrade is True


# ====================================================================== #
# AL-PROBE-06 — NEW: irreversible-rail program refused A3/A4 on post-hoc  #
#               veto only; refusal recorded; ACH modeled non-final        #
# ====================================================================== #


def test_al_probe_06_instant_rail_post_hoc_only_refused_and_recorded() -> None:
    """Attack: promote an instant-rail (FedNow) payout program to A3 whose
    ONLY pre-execution control is a post-hoc veto. Pass = promotion refused,
    the refusal is recorded in the ledger as IRREVERSIBLE_PROMOTION_REFUSED."""
    chain = AuditChain(deployer_id="acme-pay-prod", chain_creation_iso=CREATED)
    gate = AutonomyLadderGate(audit_chain=chain, mode="production")

    # Fully attested on every lower gate — so the ONLY reason to refuse is the
    # irreversibility rule, proving the gate is the thing doing the work.
    attestations = tuple(
        Attestation(c, True, "mrm-lead", "second_line_mrm", CREATED, f"e://{c}")
        for c in (
            "sovereign_veto_load_tested",
            "audit_ledger_min_window",
            "shadow_mode_min_window",
            "circuit_breaker_recent",
        )
    )
    req = PromotionRequest(
        target_tier=AutonomyTier.A3_SUPERVISED_AUTONOMOUS,
        decision_class="instant_payout",
        program_id="fednow-payout-bot",
        moves_money=True,
        rail_id="fednow",
        controls=frozenset({"post_hoc_veto"}),  # post-hoc only
        attestations=attestations,
    )
    decision = gate.evaluate(req)
    assert decision.granted is False
    assert decision.irreversibility_refusal is True
    refusals = [
        e for e in chain._events if e.event_type.value == "payments.irreversible_promotion_refused"
    ]
    assert refusals, "the refusal must be recorded in the ledger"
    assert refusals[0].payload["program_id"] == "fednow-payout-bot"
    assert refusals[0].payload["rail_id"] == "fednow"


def test_al_probe_06_attested_pre_auth_control_unblocks_promotion() -> None:
    """The same program WITH a pre-authorization control that is independently
    ATTESTED as wired/effective is promotable — the gate blocks post-hoc-only and
    bare-string pre-auth claims, not genuine pre-authorization."""
    chain = AuditChain(deployer_id="acme-pay-prod", chain_creation_iso=CREATED)
    gate = AutonomyLadderGate(audit_chain=chain, mode="production")
    attestations = tuple(
        Attestation(c, True, "audit-lead", "third_line_audit", CREATED, f"e://{c}")
        for c in (
            "sovereign_veto_load_tested",
            "audit_ledger_min_window",
            "shadow_mode_min_window",
            "circuit_breaker_recent",
            "pre_auth_control_effective",  # the pre-auth control is attested wired
        )
    )
    req = PromotionRequest(
        target_tier=AutonomyTier.A3_SUPERVISED_AUTONOMOUS,
        decision_class="instant_payout",
        program_id="fednow-payout-bot",
        moves_money=True,
        rail_id="fednow",
        controls=frozenset({"pre_auth_ofac_screening", "post_hoc_veto"}),
        attestations=attestations,
    )
    decision = gate.evaluate(req)
    assert decision.granted is True
    assert decision.irreversibility_refusal is False


def test_al_probe_06_named_but_unattested_pre_auth_refused() -> None:
    """D1 regression in the probe pack: naming a pre-auth control WITHOUT an
    independent attestation that it is wired does NOT unblock — the bare-string
    bypass is closed."""
    chain = AuditChain(deployer_id="acme-pay-prod", chain_creation_iso=CREATED)
    gate = AutonomyLadderGate(audit_chain=chain, mode="production")
    four = tuple(
        Attestation(c, True, "mrm-lead", "second_line_mrm", CREATED, f"e://{c}")
        for c in (
            "sovereign_veto_load_tested",
            "audit_ledger_min_window",
            "shadow_mode_min_window",
            "circuit_breaker_recent",
        )
    )
    req = PromotionRequest(
        target_tier=AutonomyTier.A3_SUPERVISED_AUTONOMOUS,
        decision_class="instant_payout",
        program_id="fednow-payout-bot",
        moves_money=True,
        rail_id="fednow",
        controls=frozenset({"pre_auth_ofac_screening"}),  # named but unattested
        attestations=four,
    )
    decision = gate.evaluate(req)
    assert decision.granted is False
    assert decision.irreversibility_refusal is True


def test_al_probe_06_ach_modeled_non_final_separately() -> None:
    """ACH is NOT instant-final: the instant-rail finality rule does NOT apply.
    A post-hoc-only ACH program is not refused ON IRREVERSIBILITY grounds (the
    return/reversal window leaves a post-hoc control something to act on)."""
    chain = AuditChain(deployer_id="acme-pay-prod", chain_creation_iso=CREATED)
    gate = AutonomyLadderGate(audit_chain=chain, mode="production")
    attestations = tuple(
        Attestation(c, True, "mrm-lead", "second_line_mrm", CREATED, f"e://{c}")
        for c in (
            "sovereign_veto_load_tested",
            "audit_ledger_min_window",
            "shadow_mode_min_window",
            "circuit_breaker_recent",
        )
    )
    req = PromotionRequest(
        target_tier=AutonomyTier.A3_SUPERVISED_AUTONOMOUS,
        decision_class="ach_batch",
        program_id="ach-batch-bot",
        moves_money=True,
        rail_id="ach",
        controls=frozenset({"post_hoc_veto"}),  # post-hoc only, but ACH is reversible
        attestations=attestations,
    )
    decision = gate.evaluate(req)
    assert decision.irreversibility_refusal is False
    assert decision.granted is True
    assert not any(
        e.event_type.value == "payments.irreversible_promotion_refused" for e in chain._events
    )
