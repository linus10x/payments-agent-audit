"""Payment-rail finality / irreversibility model — first-class dimension.

Different rails have fundamentally different *reversibility*, and that single
property changes what autonomous-governance controls are adequate. An
instant-rail credit (FedNow, RTP) is **final and irrevocable by network rule**
the moment it settles: there is no clawback, no return window, no chargeback.
A post-hoc veto on such a rail governs nothing — by the time the veto fires
the money is gone. By contrast ACH (Nacha) is **not final**: the Nacha
Operating Rules provide return and reversal windows, so a post-hoc control
still has a window to act. Card rails carry chargeback/dispute rights.

This module classifies rails and exposes ``is_irreversible``. The autonomy
ladder consumes it to gate level-promotion: an irreversible-write program must
not reach A3/A4 on post-hoc veto alone (see ``autonomy_ladder`` and
AL-PROBE-06). **ACH is modeled as non-final separately — the instant-rail
finality rule does NOT apply to ACH.**

Reg anchors (staged in ``S3b_payment_regs_proposed.yaml`` with primary-source
URLs; cited here, authored from the staged anchors not from memory):
``fednow`` (FedNow finality), ``rtp`` (RTP Operating Rules irrevocability),
``nacha_ach`` (return/reversal windows). Confirm the precise rule text against
the staged primary sources before relying on these classifications.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Finality(Enum):
    """How reversible a settled payment on this rail is."""

    IRREVOCABLE = "irrevocable"
    """Final by network/operating rule once settled. No return, clawback, or
    chargeback (e.g. FedNow credit, RTP credit, Fedwire). A post-hoc control
    has no window to act."""

    RETURN_WINDOW = "return_window"
    """Not final: a return/reversal window exists (e.g. ACH per the Nacha
    Operating Rules). A post-hoc control still has a window to act."""

    CHARGEBACK = "chargeback"
    """Dispute/chargeback rights exist (card networks). Reversible within the
    dispute lifecycle, on different terms than an ACH return."""


@dataclass(frozen=True)
class RailProfile:
    """A payment rail and its finality classification."""

    rail_id: str
    display_name: str
    finality: Finality
    reg_anchor: str  # key into the staged reg-anchor set
    note: str = ""

    @property
    def is_irreversible(self) -> bool:
        """True when a settled payment cannot be reversed by the originator —
        the property that makes post-hoc veto inadequate."""
        return self.finality is Finality.IRREVOCABLE


# Reference registry. Classifications follow the staged primary-source anchors;
# deployers should confirm against their network's current operating rules.
_RAILS: dict[str, RailProfile] = {
    "fednow": RailProfile(
        rail_id="fednow",
        display_name="FedNow Service (instant credit)",
        finality=Finality.IRREVOCABLE,
        reg_anchor="fednow",
        note="Instant credit push; final/irrevocable on settlement per FedNow rules.",
    ),
    "rtp": RailProfile(
        rail_id="rtp",
        display_name="RTP (The Clearing House, instant credit)",
        finality=Finality.IRREVOCABLE,
        reg_anchor="rtp",
        note="Credit push; irrevocable per the RTP Operating Rules.",
    ),
    "fedwire": RailProfile(
        rail_id="fedwire",
        display_name="Fedwire Funds Service",
        finality=Finality.IRREVOCABLE,
        reg_anchor="fednow",  # closest staged anchor; wire finality is rule-based
        note="Wire transfer; final on settlement.",
    ),
    "ach": RailProfile(
        rail_id="ach",
        display_name="ACH (Nacha)",
        finality=Finality.RETURN_WINDOW,
        reg_anchor="nacha_ach",
        note="NOT final: Nacha return/reversal windows apply. The instant-rail "
        "finality rule does NOT apply to ACH.",
    ),
    "card": RailProfile(
        rail_id="card",
        display_name="Card network (credit/debit)",
        finality=Finality.CHARGEBACK,
        reg_anchor="card_acquirer_rules",
        note="Chargeback/dispute rights apply.",
    ),
}


class UnknownRailError(KeyError):
    """Raised when a rail id is not in the registry."""


def get_rail(rail_id: str) -> RailProfile:
    """Look up a rail profile. Raises ``UnknownRailError`` if unknown —
    fail closed rather than silently treating an unknown rail as reversible."""
    try:
        return _RAILS[rail_id]
    except KeyError as exc:
        raise UnknownRailError(
            f"unknown rail {rail_id!r}; known rails: {sorted(_RAILS)}. "
            "An unknown rail is treated as a hard error, not as reversible."
        ) from exc


def is_irreversible(rail_id: str) -> bool:
    """True when settled payments on ``rail_id`` are irrevocable by rule."""
    return get_rail(rail_id).is_irreversible


def known_rails() -> tuple[str, ...]:
    return tuple(sorted(_RAILS))


__all__ = [
    "Finality",
    "RailProfile",
    "UnknownRailError",
    "get_rail",
    "is_irreversible",
    "known_rails",
]
