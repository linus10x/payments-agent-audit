"""EffectiveChallengeHarness — model-risk "effective challenge" (P5, corrected spec).

"Effective challenge" is a core model-risk-management principle in U.S.
supervisory guidance — introduced by SR 11-7 / OCC Bulletin 2011-12 and carried
forward in subsequent revisions of that guidance — requiring a credible,
independent test of the primary model. When the primary model is a frontier API
the institution does not control, the standard parallel-implementation
challenger is unavailable. This harness runs a deployer-supplied challenger
against the primary on a fixed eval set and emits a ``ChallengeReport`` a
second-line model-risk function can attach to a validation file. (Confirm the
current governing MRM guidance against the primary source; this library
describes the durable principle, not a specific supervisory letter's status.)

Corrections over the reference finserv primitive (AL-PROBE-05):

  * **(a) ENFORCE in code.** The challenger callable's identity must differ
    from the primary's. ``challenger is primary`` is rejected at construction —
    a self-challenge produces ``disagreement_rate == 0`` and a rubber-stamp
    ``accept_primary``, which is exactly the failure effective challenge
    exists to prevent. The reference impl accepted it.
  * **(b) RECORD as attestation.** Independence (not same owner / vendor family
    / prompt template) is an *operator-supplied claim*, not something the code
    can detect. The harness REQUIRES an ``IndependenceAttestation`` naming WHO
    chose the challenger and WHEN, and writes it to the chain. When the
    attestation does not assert full independence, the recommendation is
    forced away from ``accept_primary`` — a model owner cannot self-challenge
    to a clean pass. Vendor-family/template independence is attested, not
    code-detected; the library says so and does not fabricate a detector.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from payments_agent_audit.schemas.audit_event import (
    AuditChain,
    AuditEventType,
    AutonomyLevel,
)

_METHODOLOGY_ID = "effective_challenge_v1"
_DEFAULT_ACCEPT_THRESHOLD = 0.05
_DEFAULT_INVESTIGATE_THRESHOLD = 0.30
_MAX_DISAGREEMENT_EXAMPLES = 20

Recommendation = Literal["accept_primary", "investigate", "escalate"]
ModelCallable = Callable[[str], Any]


class ChallengerIndependenceError(RuntimeError):
    """Raised when the challenger is not independent of the primary (P5a)."""


@dataclass(frozen=True)
class IndependenceAttestation:
    """Operator-supplied claim about challenger independence (P5b).

    These are *attestations*, not detections. The harness cannot inspect a
    frontier vendor's family or a prompt template; the MRM function asserts
    them and signs for them. ``who_selected`` + ``selected_at`` bind the
    selection to a named human and a time, written to the chain.
    """

    who_selected: str  # named human / role who chose the challenger
    selected_at: str  # ISO-8601 timestamp of the selection decision
    not_same_owner: bool
    not_same_vendor_family: bool
    not_same_prompt_template: bool
    note: str = ""

    @property
    def is_independent(self) -> bool:
        return self.not_same_owner and self.not_same_vendor_family and self.not_same_prompt_template

    def __post_init__(self) -> None:
        if not self.who_selected or not self.who_selected.strip():
            raise ValueError("IndependenceAttestation.who_selected must name a human/role")
        if not self.selected_at or not self.selected_at.strip():
            raise ValueError("IndependenceAttestation.selected_at must be an ISO-8601 timestamp")


@dataclass(frozen=True)
class ChallengeReport:
    """Artifact second-line MRM attaches to a validation file."""

    primary_accuracy: float
    challenger_accuracy: float
    disagreement_rate: float
    disagreement_examples: list[tuple[Any, Any, Any]] = field(default_factory=list)
    methodology: str = _METHODOLOGY_ID
    eval_set_hash: str = ""
    recommendation: Recommendation = "accept_primary"
    independence_asserted: bool = False
    independence_forced_downgrade: bool = False


class EffectiveChallengeHarness:
    """Effective-challenge harness (model risk management) for frontier-API primaries."""

    def __init__(
        self,
        *,
        primary_model: ModelCallable,
        challenger_model: ModelCallable,
        eval_set: list[tuple[Any, Any]],
        independence: IndependenceAttestation,
        audit_chain: AuditChain | None = None,
        accept_threshold: float = _DEFAULT_ACCEPT_THRESHOLD,
        investigate_threshold: float = _DEFAULT_INVESTIGATE_THRESHOLD,
        autonomy_level: AutonomyLevel = AutonomyLevel.A2,
    ) -> None:
        # P5a — ENFORCE: the challenger cannot be the primary. Identity
        # equality is the unfakeable case; vendor-family/template sameness is
        # the operator's attestation below.
        if challenger_model is primary_model:
            raise ChallengerIndependenceError(
                "challenger_model is the SAME callable as primary_model: a "
                "self-challenge yields disagreement_rate=0 and a rubber-stamp "
                "accept_primary. Supply an independent challenger."
            )
        self.primary_model = primary_model
        self.challenger_model = challenger_model
        self.eval_set = eval_set
        self.independence = independence
        self.audit_chain = audit_chain
        self.accept_threshold = accept_threshold
        self.investigate_threshold = investigate_threshold
        self.autonomy_level = autonomy_level

    def run(
        self,
        *,
        agent_id: str = "effective_challenge_harness",
        actor_id: str | None = None,
    ) -> ChallengeReport:
        """Evaluate both models on the eval set. Returns a ``ChallengeReport``."""
        if not self.eval_set:
            raise ValueError("eval_set must contain at least one (input, expected) pair")

        primary_correct = 0
        challenger_correct = 0
        disagreements: list[tuple[Any, Any, Any]] = []
        disagreement_count = 0

        for input_value, expected in self.eval_set:
            primary_output = self.primary_model(input_value)
            challenger_output = self.challenger_model(input_value)
            if primary_output == expected:
                primary_correct += 1
            if challenger_output == expected:
                challenger_correct += 1
            if primary_output != challenger_output:
                disagreement_count += 1
                if len(disagreements) < _MAX_DISAGREEMENT_EXAMPLES:
                    disagreements.append((input_value, primary_output, challenger_output))

        n = len(self.eval_set)
        disagreement_rate = disagreement_count / n
        base_reco = self._recommend(disagreement_rate)

        # P5b — a non-independent challenger cannot yield a clean accept_primary.
        forced_downgrade = False
        recommendation: Recommendation = base_reco
        if base_reco == "accept_primary" and not self.independence.is_independent:
            recommendation = "investigate"
            forced_downgrade = True

        report = ChallengeReport(
            primary_accuracy=primary_correct / n,
            challenger_accuracy=challenger_correct / n,
            disagreement_rate=disagreement_rate,
            disagreement_examples=disagreements,
            methodology=_METHODOLOGY_ID,
            eval_set_hash=self._hash_eval_set(),
            recommendation=recommendation,
            independence_asserted=self.independence.is_independent,
            independence_forced_downgrade=forced_downgrade,
        )

        if self.audit_chain is not None:
            self._emit_model_validated(report=report, agent_id=agent_id, actor_id=actor_id)
        return report

    def _recommend(self, disagreement_rate: float) -> Recommendation:
        if disagreement_rate <= self.accept_threshold:
            return "accept_primary"
        if disagreement_rate <= self.investigate_threshold:
            return "investigate"
        return "escalate"

    def _hash_eval_set(self) -> str:
        serialized = json.dumps([[i, e] for i, e in self.eval_set], sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _emit_model_validated(
        self, *, report: ChallengeReport, agent_id: str, actor_id: str | None
    ) -> None:
        if self.audit_chain is None:
            return
        payload: dict[str, Any] = {
            "methodology": report.methodology,
            "n_eval_rows": len(self.eval_set),
            "primary_accuracy": report.primary_accuracy,
            "challenger_accuracy": report.challenger_accuracy,
            "disagreement_rate": report.disagreement_rate,
            "eval_set_hash": report.eval_set_hash,
            "recommendation": report.recommendation,
            "independence": {
                "who_selected": self.independence.who_selected,
                "selected_at": self.independence.selected_at,
                "not_same_owner": self.independence.not_same_owner,
                "not_same_vendor_family": self.independence.not_same_vendor_family,
                "not_same_prompt_template": self.independence.not_same_prompt_template,
                "is_independent": self.independence.is_independent,
                "note": self.independence.note,
            },
            "independence_forced_downgrade": report.independence_forced_downgrade,
            "disagreement_examples_count": len(report.disagreement_examples),
        }
        self.audit_chain.append(
            event_type=AuditEventType.MODEL_VALIDATED,
            autonomy_level=self.autonomy_level,
            agent_id=agent_id,
            payload=payload,
            actor_id=actor_id,
        )


__all__ = [
    "ChallengeReport",
    "ChallengerIndependenceError",
    "EffectiveChallengeHarness",
    "IndependenceAttestation",
    "ModelCallable",
    "Recommendation",
]
