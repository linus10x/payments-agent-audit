"""OFACScreener tests — implemented strict-liability control, pluggable list."""

from __future__ import annotations

import pytest

from payments_agent_audit.governance.ofac_screening import (
    Disposition,
    OFACScreener,
    SanctionsScreeningError,
    ScreeningStatus,
)
from tests.conftest import StaticSanctionsList


def _screener(sanctions_list, **kw) -> OFACScreener:
    return OFACScreener(sanctions_list, **kw)


def test_exact_match_flagged(sanctions_list) -> None:
    s = _screener(sanctions_list)
    r = s.screen("Vladimir Smirnov")
    assert r.status is ScreeningStatus.POTENTIAL_MATCH
    assert r.is_held is True
    assert r.candidates[0].score == pytest.approx(1.0)


def test_fuzzy_near_match_flagged(sanctions_list) -> None:
    s = _screener(sanctions_list)
    r = s.screen("Vladimir Smirnoff")  # one-letter variant
    assert r.status is ScreeningStatus.POTENTIAL_MATCH
    assert r.candidates[0].score >= 0.82


def test_word_order_match(sanctions_list) -> None:
    s = _screener(sanctions_list)
    r = s.screen("Smirnov Vladimir")
    assert r.status is ScreeningStatus.POTENTIAL_MATCH


def test_accent_and_case_normalized(sanctions_list) -> None:
    s = _screener(sanctions_list)
    r = s.screen("vladímir smirnov")
    assert r.status is ScreeningStatus.POTENTIAL_MATCH


def test_unrelated_name_clears(sanctions_list) -> None:
    s = _screener(sanctions_list)
    r = s.screen("Jane Q Public")
    assert r.status is ScreeningStatus.CLEAR
    assert r.is_cleared is True
    assert r.is_held is False


def test_alias_match(sanctions_list) -> None:
    s = _screener(sanctions_list)
    r = s.screen("BIS SA")
    assert r.status is ScreeningStatus.POTENTIAL_MATCH


def test_self_disposition_forbidden(sanctions_list) -> None:
    s = _screener(sanctions_list, agent_id="ofac-bot")
    r = s.screen("Vladimir Smirnov")
    with pytest.raises(SanctionsScreeningError, match="self-disposition forbidden"):
        s.disposition(r, Disposition.FALSE_POSITIVE, "ofac-bot", "clearing")


def test_disposition_requires_reason(sanctions_list) -> None:
    s = _screener(sanctions_list)
    r = s.screen("Vladimir Smirnov")
    with pytest.raises(SanctionsScreeningError, match="documented reason"):
        s.disposition(r, Disposition.FALSE_POSITIVE, "analyst", "")


def test_disposition_requires_operator(sanctions_list) -> None:
    s = _screener(sanctions_list)
    r = s.screen("Vladimir Smirnov")
    with pytest.raises(SanctionsScreeningError, match="non-empty operator_id"):
        s.disposition(r, Disposition.FALSE_POSITIVE, "", "reason")


def test_clear_disposition_marks_cleared(sanctions_list) -> None:
    s = _screener(sanctions_list)
    r = s.screen("Vladimir Smirnov")
    assert r.is_cleared is False
    s.disposition(r, Disposition.FALSE_POSITIVE, "analyst-jane", "DOB mismatch, different person")
    assert r.is_cleared is True
    assert r.dispositioned_by == "analyst-jane"


def test_true_match_blocked_not_cleared(sanctions_list) -> None:
    s = _screener(sanctions_list)
    r = s.screen("Vladimir Smirnov")
    s.disposition(r, Disposition.TRUE_MATCH_BLOCKED, "analyst-jane", "confirmed SDN")
    assert r.is_cleared is False


def test_cannot_disposition_clear_result(sanctions_list) -> None:
    s = _screener(sanctions_list)
    r = s.screen("Totally Unrelated Person")
    with pytest.raises(SanctionsScreeningError, match="only a POTENTIAL_MATCH"):
        s.disposition(r, Disposition.FALSE_POSITIVE, "analyst", "reason")


def test_double_disposition_rejected(sanctions_list) -> None:
    s = _screener(sanctions_list)
    r = s.screen("Vladimir Smirnov")
    s.disposition(r, Disposition.FALSE_POSITIVE, "analyst", "first")
    with pytest.raises(SanctionsScreeningError, match="already dispositioned"):
        s.disposition(r, Disposition.TRUE_MATCH_BLOCKED, "analyst", "second")


def test_screen_emits_to_chain(sanctions_list, chain) -> None:
    s = _screener(sanctions_list, audit_chain=chain)
    r = s.screen("Vladimir Smirnov")
    s.disposition(r, Disposition.FALSE_POSITIVE, "analyst-jane", "reviewed")
    screened = [e for e in chain._events if e.event_type.value == "payments.ofac_screened"]
    dispo = [e for e in chain._events if e.event_type.value == "payments.ofac_hit_dispositioned"]
    assert screened and dispo
    assert dispo[0].actor_id == "analyst-jane"


def test_empty_name_rejected(sanctions_list) -> None:
    s = _screener(sanctions_list)
    with pytest.raises(ValueError):
        s.screen("  ")


def test_invalid_threshold_rejected(sanctions_list) -> None:
    with pytest.raises(ValueError):
        OFACScreener(sanctions_list, review_threshold=1.5)


def test_no_list_is_bundled() -> None:
    """The library ships no list — an empty provider clears everything."""
    empty = StaticSanctionsList([])
    s = OFACScreener(empty)
    assert s.screen("Vladimir Smirnov").status is ScreeningStatus.CLEAR


def test_threshold_boundary_is_inclusive(sanctions_list) -> None:
    """A score exactly AT the threshold must flag (>=, not >): strict liability
    cannot let an exact-threshold match slip."""
    s = OFACScreener(sanctions_list, review_threshold=1.0)
    r = s.screen("Vladimir Smirnov")  # exact match -> score 1.0 == threshold
    assert r.status is ScreeningStatus.POTENTIAL_MATCH


def test_higher_threshold_reduces_flags(sanctions_list) -> None:
    strict = OFACScreener(sanctions_list, review_threshold=0.99)
    # one-letter variant should now fall below the stricter threshold
    r = strict.screen("Vladimir Smirnoof")
    assert r.status is ScreeningStatus.CLEAR
