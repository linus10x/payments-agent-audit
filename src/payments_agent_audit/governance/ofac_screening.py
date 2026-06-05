"""OFAC sanctions screening — strict-liability control (implemented, not doc-only).

U.S. sanctions are a **strict-liability** regime: a prohibited transaction is a
violation regardless of intent or knowledge. An autonomous payment agent that
moves money therefore cannot self-clear a potential sanctions match — a hit
must be held and dispositioned by an authorized human. This module implements:

  * a **pluggable list interface** (``SanctionsListProvider``) — the OFAC SDN /
    consolidated list is the deployer's to supply; **no list is bundled** (the
    list changes constantly and shipping a stale copy would be worse than
    shipping none). The library screens against whatever the deployer wires.
  * **fuzzy matching** — normalized-name comparison plus a stdlib similarity
    ratio, so near-matches and common obfuscations surface rather than slip
    past an exact-match filter. The threshold errs toward over-flagging
    (strict liability): false positives are dispositioned, missed true hits
    are violations.
  * a **hit-disposition workflow** — a potential match is held
    (``POTENTIAL_MATCH``) and can only be cleared by an authenticated human
    disposition (``FALSE_POSITIVE``) or escalated/blocked. The agent cannot
    disposition its own hit to cleared. Every screen and disposition is
    written to the audit chain.

Reg anchors (staged, primary-sourced in ``S3b_payment_regs_proposed.yaml``):
``ofac_sdn`` (SDN list + the IEEPA / 31 CFR 501 strict-liability basis). The
penalty-action golden corpus lives under ``tests/golden``.

This is reference IP for adoption, not a deployed control operating in
production. It is also **not legal advice** — sanctions screening calibration
and disposition are the deployer's compliance function's responsibility.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from difflib import SequenceMatcher
from enum import Enum
from typing import Protocol, runtime_checkable

from payments_agent_audit.schemas.audit_event import (
    AuditChain,
    AuditEventType,
    AutonomyLevel,
)

# Default review threshold. Strict liability → low threshold (over-flag).
DEFAULT_REVIEW_THRESHOLD = 0.82


@dataclass(frozen=True)
class SanctionedParty:
    """One entry on a sanctions list (deployer-supplied; nothing bundled)."""

    uid: str
    name: str
    aliases: tuple[str, ...] = ()
    programs: tuple[str, ...] = ()  # e.g. ("SDGT", "UKRAINE-EO13662")
    entity_type: str = "individual"  # individual | entity | vessel | aircraft


@runtime_checkable
class SanctionsListProvider(Protocol):
    """Pluggable source of sanctioned parties. No list is bundled.

    A deployer implements this against the live OFAC SDN + consolidated list
    (or a vendor feed). The library never ships list data.
    """

    def entries(self) -> Iterable[SanctionedParty]: ...


class Disposition(Enum):
    """Terminal disposition of a potential match (human decision)."""

    FALSE_POSITIVE = "false_positive"  # cleared after review
    TRUE_MATCH_BLOCKED = "true_match_blocked"  # payment blocked, funds held
    TRUE_MATCH_REJECTED = "true_match_rejected"  # payment rejected/returned
    ESCALATED = "escalated"  # routed to OFAC reporting / compliance officer


class ScreeningStatus(Enum):
    CLEAR = "clear"  # no potential match at/above threshold
    POTENTIAL_MATCH = "potential_match"  # held pending human disposition


@dataclass(frozen=True)
class CandidateMatch:
    party: SanctionedParty
    matched_value: str  # the screened string that matched (name or alias)
    score: float


@dataclass
class ScreeningResult:
    """Result of screening one name. Mutable only via ``disposition``."""

    screened_name: str
    status: ScreeningStatus
    candidates: tuple[CandidateMatch, ...] = ()
    disposition: Disposition | None = None
    dispositioned_by: str | None = None
    dispositioned_at: str | None = None
    disposition_reason: str | None = None
    screened_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def is_held(self) -> bool:
        """True while a potential match is undispositioned — payment must not
        proceed."""
        return self.status is ScreeningStatus.POTENTIAL_MATCH and self.disposition is None

    @property
    def is_cleared(self) -> bool:
        """True only when there was no match, or a human dispositioned the hit
        as a false positive."""
        if self.status is ScreeningStatus.CLEAR:
            return True
        return self.disposition is Disposition.FALSE_POSITIVE


class SanctionsScreeningError(RuntimeError):
    """Raised on an invalid disposition (e.g. agent self-clearing a hit)."""


def _normalize(name: str) -> str:
    """Lower-case, strip accents/punctuation, collapse whitespace."""
    decomposed = unicodedata.normalize("NFKD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in stripped.lower())
    return " ".join(cleaned.split())


def _similarity(a: str, b: str) -> float:
    """Normalized similarity in [0, 1]. Blends three signals so word-order
    changes (names are routinely reordered), token overlap, and minor edits
    all surface — under-flagging a sanctioned party is the costly failure:

      * a raw sequence ratio (catches typos / minor edits),
      * a *token-sort* ratio — compare the two names with their tokens sorted,
        so "Smirnov Vladimir" and "Vladimir Smirnov" score 1.0,
      * token-set Jaccard (shared-word overlap).
    """
    na, nb = _normalize(a), _normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    seq = SequenceMatcher(None, na, nb).ratio()
    sorted_a = " ".join(sorted(na.split()))
    sorted_b = " ".join(sorted(nb.split()))
    token_sort = SequenceMatcher(None, sorted_a, sorted_b).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jaccard = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    return max(seq, token_sort, 0.5 * seq + 0.5 * jaccard)


class OFACScreener:
    """Strict-liability OFAC screening with a hit-disposition workflow."""

    def __init__(
        self,
        list_provider: SanctionsListProvider,
        audit_chain: AuditChain | None = None,
        review_threshold: float = DEFAULT_REVIEW_THRESHOLD,
        agent_id: str = "ofac-screener",
    ) -> None:
        if not 0.0 < review_threshold <= 1.0:
            raise ValueError("review_threshold must be in (0, 1]")
        self._provider = list_provider
        self._audit_chain = audit_chain
        self.review_threshold = review_threshold
        self.agent_id = agent_id

    def screen(self, name: str, *, actor_id: str | None = None) -> ScreeningResult:
        """Screen ``name`` against the wired list. A potential match is HELD."""
        if not name or not name.strip():
            raise ValueError("name to screen must be non-empty")

        candidates: list[CandidateMatch] = []
        for party in self._provider.entries():
            best_value = party.name
            best_score = _similarity(name, party.name)
            for alias in party.aliases:
                s = _similarity(name, alias)
                if s > best_score:
                    best_score, best_value = s, alias
            if best_score >= self.review_threshold:
                candidates.append(
                    CandidateMatch(party=party, matched_value=best_value, score=best_score)
                )

        candidates.sort(key=lambda c: c.score, reverse=True)
        status = ScreeningStatus.POTENTIAL_MATCH if candidates else ScreeningStatus.CLEAR
        result = ScreeningResult(
            screened_name=name,
            status=status,
            candidates=tuple(candidates),
        )
        self._emit(
            AuditEventType.OFAC_SCREENED,
            {
                "screened_name": name,
                "status": status.value,
                "candidate_count": len(candidates),
                "top_score": candidates[0].score if candidates else 0.0,
                "review_threshold": self.review_threshold,
            },
            actor_id=actor_id,
        )
        return result

    def disposition(
        self,
        result: ScreeningResult,
        disposition: Disposition,
        operator_id: str,
        reason: str,
    ) -> ScreeningResult:
        """Apply a human disposition to a held potential match.

        Strict liability: the agent cannot disposition its own hit
        (``operator_id == agent_id`` is rejected), and only a human-supplied
        operator may clear a hit to ``FALSE_POSITIVE``. Records the disposition.
        """
        if result.status is not ScreeningStatus.POTENTIAL_MATCH:
            raise SanctionsScreeningError(
                f"only a POTENTIAL_MATCH can be dispositioned; status is {result.status.value}"
            )
        if result.disposition is not None:
            raise SanctionsScreeningError("this potential match is already dispositioned")
        if not operator_id or not operator_id.strip():
            raise SanctionsScreeningError("disposition requires a non-empty operator_id")
        if operator_id == self.agent_id:
            raise SanctionsScreeningError(
                f"self-disposition forbidden: operator {operator_id!r} equals agent_id; "
                "an agent cannot clear its own sanctions hit (strict liability)"
            )
        if not reason or not reason.strip():
            raise SanctionsScreeningError("disposition requires a documented reason")

        result.disposition = disposition
        result.dispositioned_by = operator_id
        result.dispositioned_at = datetime.now(UTC).isoformat()
        result.disposition_reason = reason
        self._emit(
            AuditEventType.OFAC_HIT_DISPOSITIONED,
            {
                "screened_name": result.screened_name,
                "disposition": disposition.value,
                "reason": reason,
                "candidate_uids": [c.party.uid for c in result.candidates],
            },
            actor_id=operator_id,
        )
        return result

    def _emit(
        self, event_type: AuditEventType, payload: dict[str, object], actor_id: str | None
    ) -> None:
        if self._audit_chain is None:
            return
        self._audit_chain.append(
            event_type=event_type,
            autonomy_level=AutonomyLevel.A2,
            agent_id=self.agent_id,
            payload=payload,
            actor_id=actor_id,
        )


__all__ = [
    "DEFAULT_REVIEW_THRESHOLD",
    "CandidateMatch",
    "Disposition",
    "OFACScreener",
    "SanctionedParty",
    "SanctionsListProvider",
    "SanctionsScreeningError",
    "ScreeningResult",
    "ScreeningStatus",
]
