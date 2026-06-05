"""Regulation E error-resolution gate (EFTA / 12 CFR 1005.11).

When a consumer asserts an error on an electronic fund transfer (an
unauthorized transfer, an incorrect amount, a missing/incorrect statement
entry), Regulation E sets a strict timeline:

  * the institution must **investigate and determine** whether an error
    occurred within **10 business days** of receiving the notice;
  * if it cannot complete the investigation in 10 business days it may take up
    to **45 calendar days**, but only if it **provisionally credits** the
    consumer's account for the disputed amount within the 10-day window;
  * the investigation extends to **90 calendar days** for new-account,
    point-of-sale, and foreign-initiated transfers (with provisional credit).

An autonomous agent disposing of a Reg E claim must respect these deadlines and
record the provisional-credit decision. This gate computes the applicable
deadline and flags whether provisional credit is required given the chosen
investigation window. It does not adjudicate the underlying claim — that is the
institution's. Reference IP, not legal advice; confirm the rule text against
the staged ``reg_e_efta`` anchor (canonical SSOT — cited, not re-added).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from payments_agent_audit.schemas.audit_event import (
    AuditChain,
    AuditEventType,
    AutonomyLevel,
)

# 12 CFR 1005.11(c)
INITIAL_INVESTIGATION_BUSINESS_DAYS = 10
EXTENDED_INVESTIGATION_DAYS = 45
# 12 CFR 1005.11(c)(3): for new-account, point-of-sale debit, and
# foreign-initiated transfers the institution has a longer initial window
# (20 business days) and a longer extended window (90 calendar days).
NEW_ACCOUNT_INITIAL_BUSINESS_DAYS = 20
NEW_ACCOUNT_POS_FOREIGN_DAYS = 90


class ErrorType(Enum):
    UNAUTHORIZED_TRANSFER = "unauthorized_transfer"
    INCORRECT_AMOUNT = "incorrect_amount"
    MISSING_STATEMENT_ENTRY = "missing_statement_entry"
    COMPUTATIONAL_ERROR = "computational_error"


class RegEError(RuntimeError):
    """Raised on an invalid Reg E error-resolution input."""


@dataclass(frozen=True)
class RegEResolutionResult:
    error_type: ErrorType
    notice_date: datetime
    investigation_deadline: datetime
    provisional_credit_required: bool
    provisional_credit_given: bool
    compliant: bool
    failures: tuple[str, ...]


class RegEErrorResolution:
    """Reg E error-resolution timeline + provisional-credit gate."""

    def __init__(
        self, audit_chain: AuditChain | None = None, agent_id: str = "reg-e-resolution"
    ) -> None:
        self._audit_chain = audit_chain
        self.agent_id = agent_id

    def resolve(
        self,
        *,
        error_type: ErrorType,
        notice_date: datetime,
        investigation_completion_date: datetime,
        provisional_credit_given: bool,
        is_new_account_pos_or_foreign: bool,
        claim_id: str,
        actor_id: str | None = None,
    ) -> RegEResolutionResult:
        """Evaluate Reg E timeline compliance for a single error claim.

        Business days are approximated as calendar days (deployers apply their
        banking-day calendar; this gate flags the requirement, it does not own
        the holiday calendar). New-account / POS / foreign transfers get the
        longer 20-business-day initial window and the 90-day extended window per
        12 CFR 1005.11(c)(3); all other claims get 10 / 45.
        """
        if is_new_account_pos_or_foreign:
            initial_days = NEW_ACCOUNT_INITIAL_BUSINESS_DAYS
            extended_days = NEW_ACCOUNT_POS_FOREIGN_DAYS
        else:
            initial_days = INITIAL_INVESTIGATION_BUSINESS_DAYS
            extended_days = EXTENDED_INVESTIGATION_DAYS

        initial_deadline = notice_date + timedelta(days=initial_days)
        completed_in_initial = investigation_completion_date <= initial_deadline
        extended_deadline = notice_date + timedelta(days=extended_days)

        failures: list[str] = []
        if completed_in_initial:
            deadline = initial_deadline
            provisional_required = False
        else:
            deadline = extended_deadline
            provisional_required = True
            if not provisional_credit_given:
                failures.append(
                    f"investigation extended beyond {initial_days} business days without "
                    f"provisional credit (required under 12 CFR 1005.11(c)(2)/(c)(3))"
                )
            if investigation_completion_date > extended_deadline:
                failures.append(
                    f"investigation completed after the {extended_days}-day extended deadline"
                )

        result = RegEResolutionResult(
            error_type=error_type,
            notice_date=notice_date,
            investigation_deadline=deadline,
            provisional_credit_required=provisional_required,
            provisional_credit_given=provisional_credit_given,
            compliant=not failures,
            failures=tuple(failures),
        )
        if self._audit_chain is not None:
            self._audit_chain.append(
                event_type=AuditEventType.REG_E_ERROR_RESOLVED,
                autonomy_level=AutonomyLevel.A2,
                agent_id=self.agent_id,
                payload={
                    "claim_id": claim_id,
                    "error_type": error_type.value,
                    "deadline_iso": deadline.isoformat(),
                    "provisional_credit_required": provisional_required,
                    "provisional_credit_given": provisional_credit_given,
                    "compliant": result.compliant,
                    "failures": list(result.failures),
                },
                actor_id=actor_id,
            )
        return result


__all__ = [
    "EXTENDED_INVESTIGATION_DAYS",
    "INITIAL_INVESTIGATION_BUSINESS_DAYS",
    "NEW_ACCOUNT_INITIAL_BUSINESS_DAYS",
    "NEW_ACCOUNT_POS_FOREIGN_DAYS",
    "ErrorType",
    "RegEError",
    "RegEErrorResolution",
    "RegEResolutionResult",
]
