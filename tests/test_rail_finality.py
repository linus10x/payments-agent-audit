"""Rail-finality tests — instant rails irreversible, ACH non-final."""

from __future__ import annotations

import pytest

from payments_agent_audit.governance.rail_finality import (
    Finality,
    UnknownRailError,
    get_rail,
    is_irreversible,
    known_rails,
)


@pytest.mark.parametrize("rail", ["fednow", "rtp", "fedwire"])
def test_instant_and_wire_rails_irreversible(rail: str) -> None:
    assert is_irreversible(rail) is True
    assert get_rail(rail).finality is Finality.IRREVOCABLE


def test_ach_is_not_final() -> None:
    assert is_irreversible("ach") is False
    assert get_rail("ach").finality is Finality.RETURN_WINDOW


def test_card_is_chargeback_reversible() -> None:
    assert is_irreversible("card") is False
    assert get_rail("card").finality is Finality.CHARGEBACK


def test_unknown_rail_fails_closed() -> None:
    with pytest.raises(UnknownRailError):
        get_rail("smoke-signal")
    with pytest.raises(UnknownRailError):
        is_irreversible("smoke-signal")


def test_known_rails_listed() -> None:
    rails = known_rails()
    assert "fednow" in rails and "ach" in rails
    assert rails == tuple(sorted(rails))


def test_each_rail_carries_reg_anchor() -> None:
    for rail in known_rails():
        assert get_rail(rail).reg_anchor
