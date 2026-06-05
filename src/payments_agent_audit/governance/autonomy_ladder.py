"""Autonomy Ladder A0 → A4 with an irreversibility promotion gate (P1 + AL-PROBE-06).

Five named maturity tiers and an explicit A2 → A3 / A3 → A4 promotion gate.
A2 → A3 is the regulator-visible boundary.

**P1 — independent attestation, not caller-asserted booleans.** The reference
finserv gate trusted a record of raw ``bool`` flags (anyone could pass
``sovereign_veto_load_tested=True``). This gate consumes ``Attestation``
records that name WHO attested, their independence ROLE, WHEN, and an
evidence reference. In production mode an attestation from a *first-line-only*
role is insufficient — promotion evidence must be attested by an independent
second-line (MRM) or third-line (internal audit) function, mirroring SR 11-7
three-lines-of-defense. An advisory-mode gate still accepts bare booleans but
is **labeled advisory** in code and docs.

**AL-PROBE-06 — irreversibility gate.** A program that moves money on an
irreversible-by-rule rail (FedNow/RTP credit; ``rail_finality.is_irreversible``)
must NOT be promoted to A3/A4 when its only pre-execution control is a post-hoc
veto: once an instant-rail credit settles it is final, so a veto that fires
after authorization governs nothing. Promotion is REFUSED unless the program
carries a genuine **pre-authorization** control (e.g. pre-auth OFAC screening,
a pre-send amount/velocity envelope, dual-control release). The refusal is
recorded to the audit chain as ``IRREVERSIBLE_PROMOTION_REFUSED``. ACH and
other rails with a return/reversal window are NOT subject to this rule.

Regulatory anchors: EU AI Act Art. 14 (human oversight), NIST AI RMF (Govern),
SR 11-7 / OCC three-lines-of-defense.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum

from payments_agent_audit.governance.rail_finality import get_rail, is_irreversible
from payments_agent_audit.schemas.audit_event import (
    AuditChain,
    AuditEventType,
    AutonomyLevel,
)


class AutonomyTier(Enum):
    """Five-tier Autonomy Ladder runtime scaffold (payments semantics)."""

    A0_INFORMATIONAL = "A0"
    """Agent reads and recommends. No write authority. (e.g. surfacing a
    flagged transaction to a BSA analyst.)"""

    A1_ASSISTED = "A1"
    """Agent drafts; a human approves every write. (e.g. drafting a SAR
    narrative for analyst signature.)"""

    A2_DELEGATED = "A2"
    """Agent writes for low-risk decisions inside a hard envelope; human
    samples and reviews all out-of-envelope cases. (e.g. auto-clearing
    low-score alerts within a calibrated band.) A2 → A3 is the
    regulator-visible boundary."""

    A3_SUPERVISED_AUTONOMOUS = "A3"
    """Agent writes for an in-scope decision class autonomously; sovereign veto
    non-overridable; ledger live; human supervises by exception. On
    irreversible rails this requires a pre-authorization control."""

    A4_PRODUCTION_AUTONOMOUS = "A4"
    """A3 plus inter-agent orchestration and operator-validated escalation."""

    @property
    def can_write(self) -> bool:
        return self is not AutonomyTier.A0_INFORMATIONAL

    @property
    def requires_human_approval(self) -> bool:
        return self is AutonomyTier.A1_ASSISTED

    @property
    def requires_envelope(self) -> bool:
        return self is AutonomyTier.A2_DELEGATED

    @property
    def is_autonomous_writer(self) -> bool:
        """A3+ — writes autonomously; the tiers the irreversibility gate guards."""
        return self in (
            AutonomyTier.A3_SUPERVISED_AUTONOMOUS,
            AutonomyTier.A4_PRODUCTION_AUTONOMOUS,
        )


# Independence roles, ordered by three-lines-of-defense distance from the build.
_INDEPENDENT_ROLES = frozenset({"second_line_mrm", "third_line_audit", "independent_validator"})


@dataclass(frozen=True)
class Attestation:
    """An independently-attested promotion criterion (P1).

    A bare boolean is not evidence. This binds the claim to a named attester,
    their three-lines-of-defense ROLE, a timestamp, and an evidence reference.
    """

    criterion: str
    satisfied: bool
    attested_by: str
    attester_role: str  # first_line | second_line_mrm | third_line_audit | independent_validator
    attested_at: str
    evidence_ref: str

    @property
    def is_independent(self) -> bool:
        return self.attester_role in _INDEPENDENT_ROLES

    def __post_init__(self) -> None:
        if not self.attested_by.strip():
            raise ValueError("Attestation.attested_by must name a human/role")
        if not self.evidence_ref.strip():
            raise ValueError("Attestation.evidence_ref must reference the evidence artifact")


# Pre-authorization control vocabulary — controls that act BEFORE money moves.
# A post-hoc veto is deliberately absent: it acts after authorization.
PRE_AUTH_CONTROLS = frozenset(
    {
        "pre_auth_ofac_screening",
        "pre_send_amount_envelope",
        "pre_send_velocity_envelope",
        "dual_control_release",
        "beneficiary_allowlist",
        "confirmation_of_payee",
    }
)
POST_HOC_ONLY_CONTROLS = frozenset({"post_hoc_veto", "post_settlement_review", "next_day_recon"})


@dataclass(frozen=True)
class PromotionRequest:
    """A request to promote a payment program to A3 or A4."""

    target_tier: AutonomyTier
    decision_class: str
    program_id: str
    moves_money: bool
    rail_id: str
    controls: frozenset[str]
    attestations: tuple[Attestation, ...]

    sovereign_veto_load_tested_days: int = 0  # legacy advisory inputs retained
    audit_ledger_running: timedelta = field(default_factory=lambda: timedelta(0))
    shadow_mode_running: timedelta = field(default_factory=lambda: timedelta(0))
    circuit_breaker_test_recent: bool = False

    @property
    def pre_auth_controls(self) -> frozenset[str]:
        return self.controls & PRE_AUTH_CONTROLS

    @property
    def only_post_hoc(self) -> bool:
        """True when the program has NO pre-authorization control (its only
        controls act after authorization)."""
        return len(self.pre_auth_controls) == 0


class PromotionRefused(RuntimeError):  # noqa: N818 - public name parity
    """Raised when a promotion is refused."""


@dataclass(frozen=True)
class PromotionDecision:
    """Structured result of a promotion-gate evaluation."""

    granted: bool
    target_tier: AutonomyTier
    failures: tuple[str, ...]
    irreversibility_refusal: bool = False

    def raise_if_refused(self) -> None:
        if not self.granted:
            raise PromotionRefused(
                f"promotion to {self.target_tier.value} refused: " + " · ".join(self.failures)
            )


_MIN_AUDIT_LEDGER_DAYS = 90
_MIN_SHADOW_MODE_DAYS = 30


class AutonomyLadderGate:
    """Promotion gate enforcing P1 attestation and AL-PROBE-06 irreversibility.

    ``mode="advisory"`` accepts bare booleans and is labeled advisory.
    ``mode="production"`` requires independent attestations and a wired
    ``audit_chain`` so refusals are recorded.
    """

    _REQUIRED_CRITERIA = (
        "sovereign_veto_load_tested",
        "audit_ledger_min_window",
        "shadow_mode_min_window",
        "circuit_breaker_recent",
    )

    def __init__(self, audit_chain: AuditChain | None = None, mode: str = "advisory") -> None:
        if mode not in ("advisory", "production"):
            raise ValueError(f"mode must be 'advisory' or 'production', got {mode!r}")
        if mode == "production" and audit_chain is None:
            raise ValueError(
                "production mode requires a wired audit_chain so promotion "
                "refusals (incl. irreversibility refusals) are recorded"
            )
        self.mode = mode
        self._audit_chain = audit_chain

    def evaluate(self, request: PromotionRequest) -> PromotionDecision:
        """Evaluate a promotion request. Records refusals to the chain.

        Returns a ``PromotionDecision`` enumerating every failure (not just
        the first) so the program team sees all gaps in one pass.
        """
        failures: list[str] = []
        irreversibility_refusal = False

        if not request.target_tier.is_autonomous_writer:
            failures.append(
                f"target tier {request.target_tier.value} is not an autonomous-writer "
                "tier (gate applies to A3/A4)"
            )

        # AL-PROBE-06 — the irreversibility gate.
        if request.moves_money and request.target_tier.is_autonomous_writer:
            rail = get_rail(request.rail_id)  # fail closed on unknown rail
            if is_irreversible(request.rail_id) and request.only_post_hoc:
                irreversibility_refusal = True
                failures.append(
                    f"IRREVERSIBILITY REFUSAL: program {request.program_id!r} moves money on "
                    f"{rail.display_name} (final-by-rule), and its only controls act after "
                    f"authorization ({sorted(request.controls)}). An irreversible-write program "
                    f"must carry a pre-authorization control "
                    f"(one of {sorted(PRE_AUTH_CONTROLS)}) before A3/A4."
                )

        # P1 — independent attestation of the four promotion criteria.
        failures.extend(self._attestation_failures(request))

        granted = not failures
        self._record(request, granted, failures, irreversibility_refusal)
        return PromotionDecision(
            granted=granted,
            target_tier=request.target_tier,
            failures=tuple(failures),
            irreversibility_refusal=irreversibility_refusal,
        )

    def _attestation_failures(self, request: PromotionRequest) -> list[str]:
        failures: list[str] = []
        by_criterion = {a.criterion: a for a in request.attestations}

        if self.mode == "production":
            for criterion in self._REQUIRED_CRITERIA:
                att = by_criterion.get(criterion)
                if att is None:
                    failures.append(f"missing attestation for {criterion!r}")
                    continue
                if not att.satisfied:
                    failures.append(f"attestation for {criterion!r} is not satisfied")
                elif not att.is_independent:
                    failures.append(
                        f"attestation for {criterion!r} is from a non-independent role "
                        f"({att.attester_role!r}); production promotion requires "
                        f"second-line MRM or third-line audit attestation"
                    )
        else:
            # Advisory mode: accept the legacy boolean/timedelta inputs but the
            # caller is told (in docs + the decision) this path is advisory.
            if request.sovereign_veto_load_tested_days <= 0:
                failures.append("sovereign_veto not load-tested (advisory input)")
            if request.audit_ledger_running < timedelta(days=_MIN_AUDIT_LEDGER_DAYS):
                failures.append(
                    f"audit_ledger running {request.audit_ledger_running.days}d; "
                    f"minimum {_MIN_AUDIT_LEDGER_DAYS}d (advisory input)"
                )
            if request.shadow_mode_running < timedelta(days=_MIN_SHADOW_MODE_DAYS):
                failures.append(
                    f"shadow_mode running {request.shadow_mode_running.days}d; "
                    f"minimum {_MIN_SHADOW_MODE_DAYS}d (advisory input)"
                )
            if not request.circuit_breaker_test_recent:
                failures.append("circuit_breaker test not recent (advisory input)")
        return failures

    def _record(
        self,
        request: PromotionRequest,
        granted: bool,
        failures: list[str],
        irreversibility_refusal: bool,
    ) -> None:
        if self._audit_chain is None:
            return
        if granted:
            return  # callers emit their own promotion-granted events as needed
        event_type = (
            AuditEventType.IRREVERSIBLE_PROMOTION_REFUSED
            if irreversibility_refusal
            else AuditEventType.PROMOTION_REFUSED
        )
        self._audit_chain.append(
            event_type=event_type,
            autonomy_level=AutonomyLevel.A2,
            agent_id="autonomy-ladder-gate",
            payload={
                "program_id": request.program_id,
                "decision_class": request.decision_class,
                "target_tier": request.target_tier.value,
                "rail_id": request.rail_id,
                "moves_money": request.moves_money,
                "controls": sorted(request.controls),
                "irreversibility_refusal": irreversibility_refusal,
                "failures": failures,
                "mode": self.mode,
            },
        )


__all__ = [
    "POST_HOC_ONLY_CONTROLS",
    "PRE_AUTH_CONTROLS",
    "Attestation",
    "AutonomyLadderGate",
    "AutonomyTier",
    "PromotionDecision",
    "PromotionRefused",
    "PromotionRequest",
]
