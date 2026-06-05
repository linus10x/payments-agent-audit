"""
Sovereign Veto — Human-in-the-Loop Kill Switch (P2, corrected spec)
===================================================================

A configurable veto layer between agent decisions and execution. At A2 and
below every decision passes through the veto gate. The veto can be triggered
by a human operator, a risk state machine (ALERT+), a policy engine, or a
peer monitoring agent. Once triggered it is a HARD STOP until an authorized
human clears it with a documented reason. **No agent can clear its own veto.**

Corrections over the reference finserv primitive (AL-PROBE-02):

  * **Fail-closed production mode.** ``SovereignVeto(..., mode="production")``
    REFUSES to construct without a wired ``Authorizer`` — operator identity
    on the chain is worthless if anyone can assert it. The reference impl
    only logged a warning and started anyway.
  * **Operator bound to an authenticated principal.** In production, ``clear``
    does not accept a free-string ``operator_id``. The caller supplies a
    ``credential`` which the ``Authorizer`` resolves to a principal id
    (IdP/KMS). A clear with an unauthenticated/empty principal fails closed.
  * **Self-clear forbidden, always** — even with a permissive Authorizer.

Compliance anchors:
    - EU AI Act Article 14 — human oversight measures.
    - 12 CFR 1005 (Reg E) — authorized-transfer controls.
    - 31 CFR 1020.320 — SAR program governance (kill-switch on AML signal).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


class ProductionModeError(RuntimeError):
    """Raised when production-mode invariants are unmet at construction."""


@runtime_checkable
class Authorizer(Protocol):
    """Authorizes privileged operations and authenticates principals.

    ``authenticate`` resolves an opaque ``credential`` (an IdP token, a
    KMS-signed assertion, a mTLS identity) to a stable principal id, or
    ``None`` when the credential cannot be verified. ``authorize`` decides
    whether that principal may take ``action`` in ``context``. The audit
    chain can only TRUST a recorded operator identity when it arrived via
    this two-step path — a free-string operator_id is an unauthenticated
    assertion the deployer must reconcile out-of-band.
    """

    def authenticate(self, credential: str) -> str | None: ...

    def authorize(self, principal_id: str, action: str, context: dict[str, Any]) -> bool: ...


class VetoReason(Enum):
    RISK_LIMIT_BREACH = "risk_limit_breach"
    POLICY_VIOLATION = "policy_violation"
    ANOMALY_DETECTED = "anomaly_detected"
    MANUAL_OPERATOR = "manual_operator"
    PEER_AGENT_CHALLENGE = "peer_agent_challenge"
    COMPLIANCE_FLAG = "compliance_flag"
    SANCTIONS_HIT = "sanctions_hit"  # payments: OFAC potential-match hold


@dataclass
class VetoRecord:
    veto_id: str
    reason: VetoReason
    triggered_by: str
    description: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    cleared_by: str | None = None
    cleared_at: str | None = None
    clear_reason: str | None = None

    @property
    def is_active(self) -> bool:
        return self.cleared_by is None


class VetoBlockedError(RuntimeError):
    """Raised when execution is attempted while a veto is active, or when a
    clear is rejected (self-clear, failed authentication, or denied)."""


class SovereignVeto:
    """Veto gate for autonomous payment-agent decisions."""

    def __init__(
        self,
        agent_id: str,
        on_veto: Callable[[VetoRecord], None] | None = None,
        on_clear: Callable[[VetoRecord], None] | None = None,
        authorizer: Authorizer | None = None,
        mode: str = "advisory",
    ) -> None:
        if mode not in ("advisory", "production"):
            raise ValueError(f"mode must be 'advisory' or 'production', got {mode!r}")
        self.mode = mode
        self.agent_id = agent_id
        self._vetos: list[VetoRecord] = []
        self._on_veto = on_veto
        self._on_clear = on_clear
        self._authorizer = authorizer

        # P2 fail-closed: production refuses to start without an Authorizer.
        if mode == "production" and authorizer is None:
            raise ProductionModeError(
                f"SovereignVeto(agent_id={agent_id!r}, mode='production') "
                "requires a wired Authorizer: a veto whose clear() cannot "
                "authenticate the operator is theatre. Wire an IdP/KMS-backed "
                "Authorizer, or construct in the default advisory mode."
            )
        if authorizer is None:
            logger.warning(
                "SovereignVeto(agent_id=%r) constructed ADVISORY (no Authorizer); "
                "operator_id on the audit chain is an UNAUTHENTICATED assertion.",
                agent_id,
            )

    @property
    def is_vetoed(self) -> bool:
        return any(v.is_active for v in self._vetos)

    def allow_execution(self) -> bool:
        """Gate check — call before every agent action."""
        return not self.is_vetoed

    def trigger(self, reason: VetoReason, triggered_by: str, description: str) -> VetoRecord:
        record = VetoRecord(
            veto_id=str(uuid.uuid4()),
            reason=reason,
            triggered_by=triggered_by,
            description=description,
        )
        self._vetos.append(record)
        logger.critical(
            "SOVEREIGN VETO triggered | agent: %s | reason: %s | by: %s | %s",
            self.agent_id,
            reason.value,
            triggered_by,
            description,
        )
        if self._on_veto:
            self._on_veto(record)
        return record

    def clear(
        self,
        reason: str,
        *,
        operator_id: str | None = None,
        credential: str | None = None,
        veto_id: str | None = None,
    ) -> list[VetoRecord]:
        """Clear active veto(s). Only an authenticated human may clear.

        Identity resolution:

          * **Production / Authorizer wired:** supply ``credential``. It is
            resolved to a principal id via ``Authorizer.authenticate``; an
            unverifiable credential fails closed. The resolved principal —
            never a caller-asserted ``operator_id`` — is the operator of
            record and is then put through ``Authorizer.authorize``.
          * **Advisory (no Authorizer):** ``operator_id`` is a free string
            and is labeled advisory; self-clear is still hard-blocked.

        Raises ``VetoBlockedError`` on self-clear, failed authentication, or
        a denied authorization.
        """
        resolved_operator: str

        if self._authorizer is not None:
            if not credential:
                raise VetoBlockedError(
                    "clear() requires a 'credential' when an Authorizer is "
                    "wired: operator identity must be authenticated, not asserted"
                )
            principal = self._authorizer.authenticate(credential)
            if not principal:
                logger.critical("REJECTED clear — authentication failed | agent: %s", self.agent_id)
                raise VetoBlockedError("authentication failed: credential did not resolve")
            resolved_operator = principal
        else:
            if self.mode == "production":  # pragma: no cover - blocked at construction
                raise ProductionModeError("production mode without an Authorizer is unreachable")
            if not operator_id:
                raise VetoBlockedError("advisory clear() requires a non-empty operator_id")
            resolved_operator = operator_id

        # Self-clear rule — always enforced, even with a permissive Authorizer.
        if resolved_operator == self.agent_id:
            logger.critical(
                "REJECTED self-clearing | agent: %s | operator: %s",
                self.agent_id,
                resolved_operator,
            )
            raise VetoBlockedError(
                f"self-clearing forbidden: operator {resolved_operator!r} equals "
                "agent_id; no agent can clear its own veto"
            )

        if self._authorizer is not None:
            context: dict[str, Any] = {
                "agent_id": self.agent_id,
                "veto_id": veto_id,
                "reason": reason,
            }
            if not self._authorizer.authorize(resolved_operator, "clear_veto", context):
                logger.critical(
                    "REJECTED clear by Authorizer | agent: %s | operator: %s",
                    self.agent_id,
                    resolved_operator,
                )
                raise VetoBlockedError(
                    f"Authorizer denied clear_veto by principal {resolved_operator!r}"
                )

        now = datetime.now(UTC).isoformat()
        cleared = []
        for v in self._vetos:
            if v.is_active and (veto_id is None or v.veto_id == veto_id):
                v.cleared_by = resolved_operator
                v.cleared_at = now
                v.clear_reason = reason
                cleared.append(v)
                logger.info(
                    "VETO CLEARED | agent: %s | veto_id: %s | by: %s | reason: %s",
                    self.agent_id,
                    v.veto_id,
                    resolved_operator,
                    reason,
                )
                if self._on_clear:
                    self._on_clear(v)
        return cleared

    def active_vetos(self) -> list[VetoRecord]:
        return [v for v in self._vetos if v.is_active]

    def history(self) -> list[VetoRecord]:
        return list(self._vetos)


__all__ = [
    "Authorizer",
    "ProductionModeError",
    "SovereignVeto",
    "VetoBlockedError",
    "VetoReason",
    "VetoRecord",
]
