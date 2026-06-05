"""
DEFCON Risk-State Machine — Payments Reference (P4, corrected spec)
==================================================================

A risk-state degradation machine for autonomous payment agents. Five levels
(NORMAL through HALT) with hysteresis-controlled transitions: escalation is
immediate, de-escalation requires multiple consecutive confirmations
(prevents flapping under volatile fraud/settlement conditions).

**Corrected P4 — transition-direction guard.** No actor can move
``HALT → NORMAL`` (or any de-escalation out of HALT) in one *unguarded* call.
``evaluate()`` — the automatic path — refuses to de-escalate out of HALT at
all. The only way down from HALT is ``manual_override`` on the
Authorizer-gated path, and even there a direct ``HALT → NORMAL`` jump in a
single call is rejected: de-escalation out of HALT must step to the adjacent
level (HALT → DANGER), so a recovering operator passes through the
intermediate review states rather than snapping the system fully open. The
reference cre primitive lacked any such guard.

IMPORTANT — ILLUSTRATIVE THRESHOLDS. All numeric thresholds below are
EXAMPLES for a payments program (fraud rate, daily-loss rate, sanctions-feed
availability, consecutive settlement failures). Calibrate to your rails,
volumes, and risk appetite before deploying. They are not drawn from any
production system.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from payments_agent_audit.governance.sovereign_veto import Authorizer, ProductionModeError
from payments_agent_audit.schemas.audit_event import (
    AuditChain,
    AuditEventType,
    AutonomyLevel,
)

logger = logging.getLogger(__name__)


class DEFCONOverrideRejectedError(RuntimeError):
    """Raised when a manual_override is rejected by the Authorizer or the
    transition-direction guard."""


class DEFCON(Enum):
    """Risk levels from lowest (NORMAL) to highest (HALT)."""

    NORMAL = 1
    CAUTION = 2
    ALERT = 3
    DANGER = 4
    HALT = 5

    def __ge__(self, other: DEFCON) -> bool:
        return self.value >= other.value

    def __gt__(self, other: DEFCON) -> bool:
        return self.value > other.value

    def __le__(self, other: DEFCON) -> bool:
        return self.value <= other.value

    def __lt__(self, other: DEFCON) -> bool:
        return self.value < other.value


# --- Illustrative payments thresholds (calibrate before deploying) ---------
FRAUD_RATE_HALT = 0.05  # >=5% of transactions flagged fraudulent -> HALT
FRAUD_RATE_DANGER = 0.03
FRAUD_RATE_ALERT = 0.015
FRAUD_RATE_CAUTION = 0.008

DAILY_LOSS_HALT = 0.06
DAILY_LOSS_DANGER = 0.04

CONSECUTIVE_SETTLEMENT_FAIL_ALERT = 6
CONSECUTIVE_SETTLEMENT_FAIL_CAUTION = 4

HYSTERESIS_CONFIRMATIONS = 3


@dataclass
class PaymentRiskMetrics:
    """Snapshot of payment-program risk indicators evaluated each cycle."""

    fraud_rate: float  # 0.0–1.0 fraction of transactions flagged fraudulent
    daily_loss_rate: float  # 0.0–1.0 net loss as a fraction of daily volume
    consecutive_settlement_failures: int
    sanctions_feed_available: bool = True  # OFAC/sanctions screening feed reachable
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class DEFCONMachine:
    """Payments DEFCON machine with hysteresis + a transition-direction guard.

    A wired ``AuditChain`` records every transition. ``mode="production"``
    requires a wired ``Authorizer`` (manual de-escalation must be
    authenticatable) and refuses to construct without one.
    """

    def __init__(
        self,
        audit_chain: AuditChain | None = None,
        authorizer: Authorizer | None = None,
        mode: str = "advisory",
    ) -> None:
        if mode not in ("advisory", "production"):
            raise ValueError(f"mode must be 'advisory' or 'production', got {mode!r}")
        self.mode = mode
        self._current_level: DEFCON = DEFCON.NORMAL
        self._pending_target: DEFCON | None = None
        self._confirmation_count: int = 0
        self._audit_chain = audit_chain
        self._authorizer = authorizer

        if mode == "production" and authorizer is None:
            raise ProductionModeError(
                "DEFCONMachine(mode='production') requires a wired Authorizer: "
                "manual de-escalation out of HALT must be authenticatable."
            )
        if authorizer is None:
            logger.warning(
                "DEFCONMachine constructed ADVISORY (no Authorizer); operator_id "
                "on manual_override is an UNAUTHENTICATED assertion."
            )

    @property
    def level(self) -> DEFCON:
        return self._current_level

    def evaluate(self, metrics: PaymentRiskMetrics) -> DEFCON:
        """Evaluate risk metrics and update the level (the automatic path).

        Escalation is immediate; de-escalation needs HYSTERESIS_CONFIRMATIONS
        consecutive lower evaluations. **Cannot de-escalate out of HALT** —
        that requires manual_override (the transition-direction guard).
        """
        if self._current_level == DEFCON.HALT:
            logger.warning("System is HALTED. Only manual_override can de-escalate.")
            return DEFCON.HALT

        target = self._compute_target(metrics)

        if target > self._current_level:
            self._confirm_transition(target, metrics, trigger="escalation")
        elif target < self._current_level:
            if self._pending_target != target:
                self._pending_target = target
                self._confirmation_count = 1
            else:
                self._confirmation_count += 1
            if self._confirmation_count >= HYSTERESIS_CONFIRMATIONS:
                self._confirm_transition(target, metrics, trigger="de-escalation")
        else:
            self._pending_target = None
            self._confirmation_count = 0

        return self._current_level

    def manual_override(
        self,
        target: DEFCON,
        operator_id: str,
        reason: str,
        *,
        credential: str | None = None,
        metrics: PaymentRiskMetrics | None = None,
    ) -> DEFCON:
        """Human-in-the-loop override. Required for any de-escalation from HALT.

        Transition-direction guard: a de-escalation OUT OF HALT may only step
        to the adjacent level (HALT → DANGER); a single-call ``HALT → NORMAL``
        (or any multi-step de-escalation out of HALT) is rejected, forcing the
        operator through the intermediate review states.

        When an Authorizer is wired, ``credential`` is authenticated to a
        principal which must pass ``authorize``; the resolved principal is the
        operator of record.
        """
        from_level = self._current_level

        # Transition-direction guard (the corrected P4 invariant).
        leaving_halt = from_level == DEFCON.HALT and target.value < DEFCON.HALT.value
        if leaving_halt and target.value != DEFCON.HALT.value - 1:
            raise DEFCONOverrideRejectedError(
                f"de-escalation out of HALT must step to the adjacent level "
                f"({DEFCON.DANGER.name}); a direct HALT -> {target.name} jump "
                "is forbidden. Step down through the intermediate review states."
            )

        resolved_operator = operator_id
        if self._authorizer is not None:
            if not credential:
                raise DEFCONOverrideRejectedError(
                    "manual_override requires a 'credential' when an Authorizer "
                    "is wired: the operator must be authenticated"
                )
            principal = self._authorizer.authenticate(credential)
            if not principal:
                raise DEFCONOverrideRejectedError("authentication failed for manual_override")
            resolved_operator = principal
            context: dict[str, Any] = {
                "from_level": from_level.name,
                "target_level": target.name,
                "reason": reason,
            }
            if not self._authorizer.authorize(resolved_operator, "defcon_manual_override", context):
                logger.critical(
                    "REJECTED manual_override | operator: %s | target: %s",
                    resolved_operator,
                    target.name,
                )
                raise DEFCONOverrideRejectedError(
                    f"Authorizer denied defcon_manual_override by {resolved_operator!r}"
                )

        trigger = f"MANUAL_OVERRIDE by {resolved_operator}: {reason}"
        snap = metrics or PaymentRiskMetrics(
            fraud_rate=0.0, daily_loss_rate=0.0, consecutive_settlement_failures=0
        )
        self._confirm_transition(target, snap, trigger=trigger, actor_id=resolved_operator)
        return self._current_level

    # ------------------------------------------------------------------ #

    def _compute_target(self, m: PaymentRiskMetrics) -> DEFCON:
        # A sanctions-feed outage cannot be screened around — HALT writes
        # until screening is restored (an irreversible-rail program must not
        # move money it cannot OFAC-screen).
        if not m.sanctions_feed_available:
            return DEFCON.HALT
        if m.fraud_rate >= FRAUD_RATE_HALT or m.daily_loss_rate >= DAILY_LOSS_HALT:
            return DEFCON.HALT
        if m.fraud_rate >= FRAUD_RATE_DANGER or m.daily_loss_rate >= DAILY_LOSS_DANGER:
            return DEFCON.DANGER
        if (
            m.fraud_rate >= FRAUD_RATE_ALERT
            or m.consecutive_settlement_failures >= CONSECUTIVE_SETTLEMENT_FAIL_ALERT
        ):
            return DEFCON.ALERT
        if (
            m.fraud_rate >= FRAUD_RATE_CAUTION
            or m.consecutive_settlement_failures >= CONSECUTIVE_SETTLEMENT_FAIL_CAUTION
        ):
            return DEFCON.CAUTION
        return DEFCON.NORMAL

    def _confirm_transition(
        self,
        target: DEFCON,
        metrics: PaymentRiskMetrics,
        trigger: str,
        actor_id: str | None = None,
    ) -> None:
        from_level = self._current_level
        self._current_level = target
        self._pending_target = None
        self._confirmation_count = 0

        if target == DEFCON.HALT:
            event_type = AuditEventType.HALT_TRIGGERED
        elif target.value > from_level.value:
            event_type = AuditEventType.RISK_ESCALATION
        else:
            event_type = AuditEventType.RISK_DEESCALATION

        payload: dict[str, Any] = {
            "from_level": from_level.name,
            "to_level": target.name,
            "trigger": trigger,
            "metrics_snapshot": {
                "fraud_rate": metrics.fraud_rate,
                "daily_loss_rate": metrics.daily_loss_rate,
                "consecutive_settlement_failures": metrics.consecutive_settlement_failures,
                "sanctions_feed_available": metrics.sanctions_feed_available,
            },
        }
        if self._audit_chain is not None:
            self._audit_chain.append(
                event_type=event_type,
                autonomy_level=AutonomyLevel.A2,
                agent_id="defcon-state-machine",
                payload=payload,
                actor_id=actor_id,
            )
        logger.info("DEFCON transition: %s -> %s | %s", from_level.name, target.name, trigger)


__all__ = [
    "DEFCON",
    "DEFCONMachine",
    "DEFCONOverrideRejectedError",
    "PaymentRiskMetrics",
]
