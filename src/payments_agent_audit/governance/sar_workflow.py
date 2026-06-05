"""BSA/AML SAR workflow — timeliness, Travel Rule, transaction-monitoring gate.

Three controls for an autonomous AML/payments agent:

  * **SAR timeliness** — a SAR must be filed within **30 calendar days** of
    initial detection of facts that may constitute a basis for filing; if no
    suspect is identified on the date of detection, the deadline extends to
    **60 calendar days** (31 CFR 1020.320(b)(3)). The gate computes the
    deadline and flags whether a proposed filing date meets it.
  * **Travel Rule** — for transmittals of funds of **$3,000 or more**, the
    transmittor's financial institution must record and pass specified
    originator/beneficiary information (31 CFR 1010.410(f)). The gate validates
    that the required fields travel with an in-scope transmittal.
  * **Transaction-monitoring disposition** — an AI alert disposition must carry
    a non-vague rationale; an agent may not auto-close an alert with a generic
    string ("model decision", "score below threshold"). Vague dispositions are
    rejected so the chain records a real basis.

Every decision is written to the audit chain. SAR records retain for five
years (see ``retention``). Confidentiality of SAR existence (31 CFR
1020.320(e)) is the deployer's operational responsibility — this library does
not expose SAR contents beyond hashed references.

Reg anchors (staged, primary-sourced): ``sar_timeliness``, ``travel_rule``,
``bsa_aml`` (canonical SSOT — cited, not re-added). Confirm the exact rule
text against the staged sources. Reference IP, not legal advice.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from payments_agent_audit.schemas.audit_event import (
    AuditChain,
    AuditEventType,
    AutonomyLevel,
)

# 31 CFR 1020.320(b)(3)
SAR_FILING_DEADLINE_DAYS = 30
SAR_FILING_DEADLINE_NO_SUSPECT_DAYS = 60
# 31 CFR 1010.410(f)
TRAVEL_RULE_THRESHOLD_USD = 3000

_VAGUE_RATIONALE_FRAGMENTS = (
    "model decision",
    "score below threshold",
    "no further action",
    "see attached",
    "as discussed",
    "per policy",
)

_REQUIRED_TRAVEL_RULE_FIELDS = (
    "originator_name",
    "originator_account",
    "originator_address",
    "amount",
    "beneficiary_name",
    "beneficiary_account",
)


class SARDecisionSurface(Enum):
    ALERT_DISPOSITION = "alert_disposition"
    FILE_DECISION = "file_decision"
    NARRATIVE_DRAFT = "narrative_draft"


class SARWorkflowError(RuntimeError):
    """Raised on a vague rationale or an invalid SAR/Travel-Rule input."""


@dataclass(frozen=True)
class SARTimelinessResult:
    detection_date: datetime
    proposed_filing_date: datetime
    deadline: datetime
    suspect_identified: bool
    meets_deadline: bool
    days_remaining: int


@dataclass(frozen=True)
class TravelRuleResult:
    amount_usd: float
    in_scope: bool
    missing_fields: tuple[str, ...]
    compliant: bool


class SARWorkflowAudit:
    """SAR timeliness + Travel Rule + alert-disposition gate."""

    def __init__(
        self, audit_chain: AuditChain | None = None, agent_id: str = "sar-workflow"
    ) -> None:
        self._audit_chain = audit_chain
        self.agent_id = agent_id

    def check_timeliness(
        self,
        *,
        detection_date: datetime,
        proposed_filing_date: datetime,
        suspect_identified: bool,
        case_id: str,
        actor_id: str | None = None,
    ) -> SARTimelinessResult:
        """Compute the SAR filing deadline and whether the proposed date meets it."""
        window = (
            SAR_FILING_DEADLINE_DAYS if suspect_identified else SAR_FILING_DEADLINE_NO_SUSPECT_DAYS
        )
        deadline = detection_date + timedelta(days=window)
        meets = proposed_filing_date <= deadline
        days_remaining = (deadline - proposed_filing_date).days
        result = SARTimelinessResult(
            detection_date=detection_date,
            proposed_filing_date=proposed_filing_date,
            deadline=deadline,
            suspect_identified=suspect_identified,
            meets_deadline=meets,
            days_remaining=days_remaining,
        )
        self._emit(
            AuditEventType.SAR_FILED,
            {
                "case_id": case_id,
                "deadline_iso": deadline.isoformat(),
                "window_days": window,
                "suspect_identified": suspect_identified,
                "meets_deadline": meets,
                "days_remaining": days_remaining,
            },
            actor_id=actor_id,
        )
        return result

    def check_travel_rule(
        self,
        *,
        amount_usd: float,
        fields: dict[str, Any],
        transmittal_id: str,
        actor_id: str | None = None,
    ) -> TravelRuleResult:
        """Validate Travel-Rule field completeness for an in-scope transmittal."""
        in_scope = amount_usd >= TRAVEL_RULE_THRESHOLD_USD
        missing: tuple[str, ...] = ()
        if in_scope:
            missing = tuple(
                f for f in _REQUIRED_TRAVEL_RULE_FIELDS if not str(fields.get(f, "")).strip()
            )
        result = TravelRuleResult(
            amount_usd=amount_usd,
            in_scope=in_scope,
            missing_fields=missing,
            compliant=(not in_scope) or (len(missing) == 0),
        )
        self._emit(
            AuditEventType.TRAVEL_RULE_RECORDED,
            {
                "transmittal_id": transmittal_id,
                "amount_usd": amount_usd,
                "in_scope": in_scope,
                "missing_fields": list(missing),
                "compliant": result.compliant,
            },
            actor_id=actor_id,
        )
        return result

    def validate_alert_disposition(self, rationale: str) -> None:
        """Reject a vague alert-disposition rationale (raises on failure)."""
        if not rationale or not rationale.strip():
            raise SARWorkflowError("alert disposition requires a documented rationale")
        low = rationale.lower()
        for frag in _VAGUE_RATIONALE_FRAGMENTS:
            if frag in low:
                raise SARWorkflowError(
                    f"vague alert-disposition rationale (contains {frag!r}); "
                    "a SAR-program disposition must record a specific basis"
                )

    def _emit(
        self, event_type: AuditEventType, payload: dict[str, Any], actor_id: str | None
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
    "SAR_FILING_DEADLINE_DAYS",
    "SAR_FILING_DEADLINE_NO_SUSPECT_DAYS",
    "TRAVEL_RULE_THRESHOLD_USD",
    "SARDecisionSurface",
    "SARTimelinessResult",
    "SARWorkflowAudit",
    "SARWorkflowError",
    "TravelRuleResult",
]
