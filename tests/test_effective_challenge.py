"""EffectiveChallengeHarness tests — corrected P5 (no self-challenge + attestation)."""

from __future__ import annotations

import pytest

from payments_agent_audit.governance.effective_challenge_harness import (
    ChallengerIndependenceError,
    EffectiveChallengeHarness,
    IndependenceAttestation,
)

EVAL = [("a", "ok"), ("b", "ok"), ("c", "no"), ("d", "ok")]


def _att(independent: bool = True) -> IndependenceAttestation:
    return IndependenceAttestation(
        who_selected="mrm-lead-jane",
        selected_at="2026-06-05T00:00:00+00:00",
        not_same_owner=independent,
        not_same_vendor_family=independent,
        not_same_prompt_template=independent,
        note="challenger is a different-vendor heuristic",
    )


def test_self_challenge_rejected() -> None:
    f = lambda x: "ok"  # noqa: E731
    with pytest.raises(ChallengerIndependenceError):
        EffectiveChallengeHarness(
            primary_model=f, challenger_model=f, eval_set=EVAL, independence=_att()
        )


def test_independent_challenger_runs() -> None:
    primary = lambda x: "ok"  # noqa: E731
    challenger = lambda x: "ok"  # noqa: E731 -- different object, agrees
    h = EffectiveChallengeHarness(
        primary_model=primary, challenger_model=challenger, eval_set=EVAL, independence=_att()
    )
    report = h.run()
    assert report.disagreement_rate == 0.0
    assert report.recommendation == "accept_primary"
    assert report.independence_asserted is True


def test_non_independent_blocks_clean_accept() -> None:
    """A model owner cannot self-challenge to a clean accept_primary."""
    primary = lambda x: "ok"  # noqa: E731
    challenger = lambda x: "ok"  # noqa: E731
    h = EffectiveChallengeHarness(
        primary_model=primary,
        challenger_model=challenger,
        eval_set=EVAL,
        independence=_att(independent=False),
    )
    report = h.run()
    assert report.disagreement_rate == 0.0
    assert report.recommendation == "investigate"  # forced away from accept_primary
    assert report.independence_forced_downgrade is True


def test_high_disagreement_escalates() -> None:
    primary = lambda x: "ok"  # noqa: E731
    challenger = lambda x: "different"  # noqa: E731
    h = EffectiveChallengeHarness(
        primary_model=primary, challenger_model=challenger, eval_set=EVAL, independence=_att()
    )
    report = h.run()
    assert report.disagreement_rate == 1.0
    assert report.recommendation == "escalate"


def test_emits_model_validated_to_chain(chain) -> None:
    primary = lambda x: "ok"  # noqa: E731
    challenger = lambda x: "ok" if x != "c" else "no"  # noqa: E731
    h = EffectiveChallengeHarness(
        primary_model=primary,
        challenger_model=challenger,
        eval_set=EVAL,
        independence=_att(),
        audit_chain=chain,
    )
    h.run()
    mv = [e for e in chain._events if e.event_type.value == "mrm.model_validated"]
    assert mv
    assert mv[0].payload["independence"]["who_selected"] == "mrm-lead-jane"


def test_empty_eval_set_raises() -> None:
    h = EffectiveChallengeHarness(
        primary_model=lambda x: "ok",
        challenger_model=lambda x: "no",
        eval_set=[],
        independence=_att(),
    )
    with pytest.raises(ValueError):
        h.run()


def test_eval_set_hash_is_stable() -> None:
    h1 = EffectiveChallengeHarness(
        primary_model=lambda x: "a",
        challenger_model=lambda x: "b",
        eval_set=EVAL,
        independence=_att(),
    )
    h2 = EffectiveChallengeHarness(
        primary_model=lambda x: "x",
        challenger_model=lambda x: "y",
        eval_set=EVAL,
        independence=_att(),
    )
    assert h1.run().eval_set_hash == h2.run().eval_set_hash


def test_attestation_requires_who_and_when() -> None:
    with pytest.raises(ValueError):
        IndependenceAttestation("", "2026-06-05", True, True, True)
    with pytest.raises(ValueError):
        IndependenceAttestation("who", "", True, True, True)


def test_disagreement_examples_capped() -> None:
    eval_set = [(str(i), "ok") for i in range(50)]
    h = EffectiveChallengeHarness(
        primary_model=lambda x: "ok",
        challenger_model=lambda x: "no",
        eval_set=eval_set,
        independence=_att(),
    )
    report = h.run()
    assert len(report.disagreement_examples) == 20  # capped
