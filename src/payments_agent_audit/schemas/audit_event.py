"""
Audit Event Schema — Tamper-Detecting Hash-Chain Logging (within-trust-boundary)
================================================================================

Canonical schema for audit events in regulated payments AI-agent systems.
Each event is chained to the previous via SHA-256, making any retroactive
tampering detectable on verification *within the trust boundary that produced
the chain*. For external tamper-EVIDENCE (cryptographic anchoring to a
third-party witness register such as Sigstore Rekor or OpenTimestamps), pair
the chain with the ``WitnessRegister`` seam (``governance/witness_anchor.py``).

Design principles:
    - Every agent action that changes payment state produces an audit event.
    - Events are append-only — never mutated after creation (``frozen=True``).
    - Hash chain: ``event_hash = SHA-256(canonical_fields incl. prev_hash)``.
    - A verifier can replay the chain and detect any inserted/modified event.
    - The genesis seed is *branched*: a deployer-keyed hardened chain seeds
      from ``_compute_genesis_hash`` while a legacy chain seeds from the
      ``"0"*64`` sentinel — see ``governance/audit_chain.py``.

Compliance notes (payments scope):
    - 31 CFR 1010.430 / 1022.210 — BSA recordkeeping; the 5-year retention
      floor in this library reflects 31 CFR 1010.430(d).
    - 31 CFR 1020.320 — SAR filing and confidentiality.
    - EFTA / Regulation E (12 CFR 1005) — electronic fund transfer records.
    - PCI DSS 4.0.1 — log integrity for cardholder-data environments.

``AuditChain`` is defined in ``governance.audit_chain`` (so it can consume the
pluggable Protocol seams) and re-exported here for convenience.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class AuditEventType(Enum):
    """Classification of audit events by category."""

    # Agent lifecycle
    AGENT_STARTED = "agent.started"
    AGENT_STOPPED = "agent.stopped"
    AGENT_ERROR = "agent.error"

    # Decision events
    DECISION_MADE = "decision.made"
    DECISION_VETOED = "decision.vetoed"
    DECISION_OVERRIDDEN = "decision.overridden"

    # Risk events
    RISK_ESCALATION = "risk.escalation"
    RISK_DEESCALATION = "risk.deescalation"
    HALT_TRIGGERED = "risk.halt"

    # Human-in-the-loop
    HUMAN_APPROVED = "human.approved"
    HUMAN_REJECTED = "human.rejected"
    HUMAN_OVERRIDE = "human.override"

    # Governance
    VETO_APPLIED = "governance.veto"
    POLICY_VIOLATION = "governance.policy_violation"
    COMPLIANCE_CHECK = "governance.compliance_check"
    PROMOTION_REFUSED = "governance.promotion_refused"  # autonomy-ladder gate refusal

    # Model risk management (effective-challenge harness)
    MODEL_VALIDATED = "mrm.model_validated"

    # External anchoring (WitnessRegister)
    WITNESS_ANCHOR = "audit_chain.witness_anchor"

    # Payments-specific
    OFAC_SCREENED = "payments.ofac_screened"  # OFAC SDN/consolidated screening — 31 CFR 501
    OFAC_HIT_DISPOSITIONED = "payments.ofac_hit_dispositioned"  # hit-disposition workflow
    SAR_FILED = "payments.sar_filed"  # BSA/AML — 31 CFR 1020.320
    TRAVEL_RULE_RECORDED = "payments.travel_rule_recorded"  # 31 CFR 1010.410(f)
    REG_E_ERROR_RESOLVED = "payments.reg_e_error_resolved"  # 12 CFR 1005.11
    RAIL_FINALITY_ASSESSED = "payments.rail_finality_assessed"  # finality classification
    IRREVERSIBLE_PROMOTION_REFUSED = "payments.irreversible_promotion_refused"  # AL-PROBE-06
    SPONSOR_BANK_OVERSIGHT = "payments.sponsor_bank_oversight"  # BaaS third-party oversight


class AutonomyLevel(Enum):
    """Autonomy classification per the A0->A4 ladder (wire format)."""

    A0 = "A0"  # Informational — agent reads and recommends, no write authority
    A1 = "A1"  # Assisted — agent drafts, human approves every write
    A2 = "A2"  # Delegated — agent writes in a hard envelope, sampled review
    A3 = "A3"  # Supervised Autonomous — in-scope autonomous writes, sovereign veto, live ledger
    A4 = "A4"  # Production Autonomous — A3 plus orchestration and operator-validated escalation


@dataclass(frozen=True)
class AuditEvent:
    """Immutable audit record. Hash is computed on construction.

    The dataclass is ``frozen=True`` — every field is read-only
    post-construction. Two construction paths exist:

      * ``AuditEvent.create(...)`` — for *new* events. Computes the hash
        from the field values and freezes the result.
      * ``AuditEvent.from_jsonl(dict)`` — for *replay* of stored events.
        Reconstructs the event with the stored ``event_hash``, recomputes
        the hash against the reconstructed fields, and raises
        ``AuditChainTamperError`` on mismatch. The chain is self-verifying
        on load, not only on explicit ``verify()``.

    The bare ``AuditEvent(...)`` constructor still works: with no
    ``event_hash`` supplied it computes one. Replay code that passes a
    stored ``event_hash`` MUST call ``from_jsonl`` so the recomputation
    gate fires.
    """

    event_type: AuditEventType
    autonomy_level: AutonomyLevel
    agent_id: str
    payload: dict[str, Any]
    prev_hash: str

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    actor_id: str | None = None
    schema_version: str = "1.0.0"
    event_hash: str = ""

    def __post_init__(self) -> None:
        # On a frozen dataclass the only permitted post-init write is via
        # ``object.__setattr__``. Compute the hash only when the caller did
        # not supply one — replay paths construct via ``from_jsonl`` which
        # passes the stored hash AND validates the recomputation.
        if not self.event_hash:
            object.__setattr__(self, "event_hash", self._compute_hash())

    @classmethod
    def create(
        cls,
        *,
        event_type: AuditEventType,
        autonomy_level: AutonomyLevel,
        agent_id: str,
        payload: dict[str, Any],
        prev_hash: str,
        event_id: str | None = None,
        timestamp: str | None = None,
        actor_id: str | None = None,
        schema_version: str = "1.0.0",
    ) -> AuditEvent:
        """Construct a *new* event. Computes ``event_hash`` and freezes."""
        kwargs: dict[str, Any] = {
            "event_type": event_type,
            "autonomy_level": autonomy_level,
            "agent_id": agent_id,
            "payload": payload,
            "prev_hash": prev_hash,
            "actor_id": actor_id,
            "schema_version": schema_version,
        }
        if event_id is not None:
            kwargs["event_id"] = event_id
        if timestamp is not None:
            kwargs["timestamp"] = timestamp
        return cls(**kwargs)

    @classmethod
    def from_jsonl(cls, data: dict[str, Any]) -> AuditEvent:
        """Replay a stored event. Recomputes and raises on mismatch."""
        # Lazy import — ``audit_chain`` imports ``schemas.audit_event`` at
        # module load, so the reverse import stays lazy to avoid a cycle.
        from payments_agent_audit.governance.audit_chain import (
            AuditChainTamperError,
        )

        stored_event_hash = str(data["event_hash"])
        event = cls(
            event_type=AuditEventType(data["event_type"]),
            autonomy_level=AutonomyLevel(data["autonomy_level"]),
            agent_id=str(data["agent_id"]),
            payload=dict(data["payload"]),
            prev_hash=str(data["prev_hash"]),
            event_id=str(data["event_id"]),
            timestamp=str(data["timestamp"]),
            actor_id=None if data.get("actor_id") is None else str(data["actor_id"]),
            schema_version=str(data.get("schema_version", "1.0.0")),
            event_hash=stored_event_hash,
        )
        recomputed = event._compute_hash()
        if recomputed != stored_event_hash:
            raise AuditChainTamperError(
                f"event_hash mismatch on replay (event_id={event.event_id!r}): "
                f"stored={stored_event_hash!r}, recomputed={recomputed!r} — "
                "the on-disk line has been modified after writing"
            )
        return event

    def _compute_hash(self) -> str:
        payload = {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "autonomy_level": self.autonomy_level.value,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "actor_id": self.actor_id,
            "prev_hash": self.prev_hash,
            "schema_version": self.schema_version,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "autonomy_level": self.autonomy_level.value,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "actor_id": self.actor_id,
            "prev_hash": self.prev_hash,
            "event_hash": self.event_hash,
            "schema_version": self.schema_version,
        }

    def to_jsonl(self) -> str:
        """Single JSONL line for append-only log files."""
        return json.dumps(self.to_dict(), sort_keys=True)


def __getattr__(name: str) -> Any:
    # Re-export AuditChain lazily to avoid a circular import at package init.
    if name == "AuditChain":
        from payments_agent_audit.governance.audit_chain import AuditChain

        return AuditChain
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["AuditChain", "AuditEvent", "AuditEventType", "AutonomyLevel"]  # noqa: F822  # AuditChain resolved via __getattr__
