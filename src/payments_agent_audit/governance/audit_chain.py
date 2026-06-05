"""Internally-Consistent Hash-Chained Audit Ledger.

Every governance event is appended to a chain where each entry contains the
SHA-256 hash of the previous entry. Modifying any past entry breaks the link
at that point and every entry that follows — detectable by an honest holder
of the current chain head.

**Framing.** This ledger is an *internally consistent* hash-chain by
construction (SHA-256 prev-hash links give detection, not prevention, within
the trust boundary). It is **not adversarially tamper-evident on its own**:
an attacker with full write access to the storage layer can regenerate the
entire chain end-to-end and the regenerated chain will pass ``verify()``. For
adversarial integrity, anchor the head to an external ``WitnessRegister`` the
deployer does not control alone (``witness_anchor.py``). In *production mode*
the witness register is mandatory and a missing one fails closed.

**Genesis seed — the corrected discipline (this is the load-bearing fix vs
the reference finserv implementation).** A chain may be *hardened* (a
deployer-keyed genesis event #0 is prepended, whose ``prev_hash`` is
``_compute_genesis_hash(deployer_id, chain_creation_iso)``) or *legacy* (no
genesis event; the first real event seeds from the ``"0"*64`` sentinel).
``verify()``/``verify_strict()`` **branch the genesis seed on which kind of
chain they are walking**: they recompute the deployer-keyed seed from the
genesis event's own payload when a hardened genesis event is present, and
fall back to the ``"0"*64`` sentinel otherwise. The reference finserv
implementation seeded ``"0"*64`` unconditionally, so a *clean hardened chain*
raised a false TAMPER. Both a hardened chain and a legacy chain verify True
here. The legacy sentinel is retained, never globally removed.

The implementation is stdlib-only.
"""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from payments_agent_audit.schemas.audit_event import (
    AuditEvent,
    AuditEventType,
    AutonomyLevel,
)

SCHEMA_VERSION = "1.0.0"

if TYPE_CHECKING:
    from payments_agent_audit.governance.ledger_store import LedgerStore
    from payments_agent_audit.governance.timestamp_source import TimestampSource
    from payments_agent_audit.governance.witness_anchor import WitnessRegister

GENESIS_HASH = "0" * 64
"""Legacy sentinel for the first entry's ``prev_hash`` (pre-hardening chains)."""

GENESIS_DOMAIN_SEPARATOR = "payments-agent-audit/genesis/v1"
GENESIS_AGENT_ID = "payments-audit-chain"
GENESIS_VERSION = "v1"
_GENESIS_NAMESPACE = uuid.UUID("4f1c2a9e-7b3d-4e6a-9c12-8a5f0b2d3e7c")


def _compute_genesis_hash(deployer_id: str, chain_creation_iso: str) -> str:
    """Deployer-keyed seed for a hardened chain's genesis ``prev_hash``.

    ``SHA-256(domain_separator/deployer_id/chain_creation_iso)``. Two chains
    with a different ``deployer_id`` (or ``chain_creation_iso``) produce
    different seeds, so an attacker without the deployer's identity cannot
    regenerate a chain from scratch and have its genesis match the
    legitimate deployer's declared identity.
    """
    payload = f"{GENESIS_DOMAIN_SEPARATOR}/{deployer_id}/{chain_creation_iso}".encode()
    return hashlib.sha256(payload).hexdigest()


def _is_hardened_genesis(event: AuditEvent) -> bool:
    """True when ``event`` is a deployer-keyed genesis event #0."""
    return (
        event.agent_id == GENESIS_AGENT_ID
        and event.event_type is AuditEventType.AGENT_STARTED
        and isinstance(event.payload, dict)
        and "deployer_id" in event.payload
        and "chain_creation_iso" in event.payload
        and event.payload.get("genesis_version") == GENESIS_VERSION
    )


class AuditChainTamperError(RuntimeError):
    """Raised by ``verify_strict`` when an inconsistency is detected.

    Names the failing sequence index and the failure mode so a
    regulator-facing investigation can pinpoint the corruption window.
    """


class ProductionModeError(RuntimeError):
    """Raised when production-mode invariants are unmet at construction."""


class AuditChain:
    """Append-only, hash-chained audit ledger with a branched genesis seed.

    Default (advisory) usage::

        chain = AuditChain(log_file=Path("audit.jsonl"))
        chain.append(event_type=..., autonomy_level=..., agent_id=..., payload=...)
        assert chain.verify()

    Hardened usage (deployer-keyed genesis)::

        chain = AuditChain(deployer_id="acme-pay-prod")

    Production usage (fail-closed: a witness register is mandatory)::

        chain = AuditChain(
            deployer_id="acme-pay-prod",
            witness_register=RekorWitness(),
            mode="production",
        )
    """

    GENESIS_HASH = GENESIS_HASH

    def __init__(
        self,
        log_file: Path | None = None,
        ledger_store: LedgerStore | None = None,
        timestamp_source: TimestampSource | None = None,
        witness_register: WitnessRegister | None = None,
        deployer_id: str | None = None,
        chain_creation_iso: str | None = None,
        mode: str = "advisory",
    ) -> None:
        from payments_agent_audit.governance.ledger_store import (
            InMemoryLedgerStore,
            JsonlLedgerStore,
        )
        from payments_agent_audit.governance.timestamp_source import LocalClock

        if mode not in ("advisory", "production"):
            raise ValueError(f"mode must be 'advisory' or 'production', got {mode!r}")
        self.mode = mode

        # PRODUCTION MODE (P3 fail-closed): a witness register is mandatory.
        # The internally-consistent chain alone is not adversarially
        # tamper-evident; production refuses to start without the external
        # anchor that makes end-to-end regeneration detectable.
        if mode == "production" and witness_register is None:
            raise ProductionModeError(
                "production mode requires a witness_register: an internally-"
                "consistent hash-chain is not adversarially tamper-evident "
                "without an external anchor. Wire OpenTimestamps / Rekor / a "
                "regulator log, or construct in the default advisory mode."
            )

        self._external_store: bool = ledger_store is not None
        self._store: LedgerStore = ledger_store or InMemoryLedgerStore()
        self._timestamp_source: TimestampSource = timestamp_source or LocalClock()
        self._witness_register: WitnessRegister | None = witness_register

        # RLock (not Lock): anchor_to_witness re-enters append to chain the
        # receipt; a plain Lock would deadlock.
        self._append_lock = threading.RLock()

        self._deployer_id: str | None = deployer_id
        self._chain_creation_iso: str | None
        if deployer_id is not None:
            self._chain_creation_iso = chain_creation_iso or datetime.now(UTC).isoformat()
        else:
            self._chain_creation_iso = chain_creation_iso

        self.log_file: Path | None
        if self._external_store:
            self.log_file = None
        else:
            self.log_file = log_file
            if self.log_file is not None:
                # Reuse the JSONL store so replay+flock discipline is shared.
                self._store = JsonlLedgerStore(self.log_file)
                self._external_store = False

        # Seed the hardened genesis event #0 when a deployer_id was supplied
        # and the chain is empty. Done after any replay so a re-opened chain
        # keeps its original genesis rather than getting a new one prepended.
        if deployer_id is not None and len(self._store) == 0:
            self._seed_genesis_event()

        # Back-compat: a replayed chain whose first event uses the legacy
        # sentinel is accepted but flagged for re-creation under a deployer_id.
        self._warn_if_legacy_seed()

    # ---------------------------------------------------------------- #
    # Genesis seeding                                                  #
    # ---------------------------------------------------------------- #

    def _seed_genesis_event(self) -> None:
        assert self._deployer_id is not None
        assert self._chain_creation_iso is not None
        deployer_id = self._deployer_id
        chain_creation_iso = self._chain_creation_iso

        seed = _compute_genesis_hash(deployer_id, chain_creation_iso)
        # Deterministic event_id so an independent re-construction of the
        # same logical chain produces the same event #0 (cross-host verify).
        event_id = str(
            uuid.uuid5(
                _GENESIS_NAMESPACE,
                f"{GENESIS_DOMAIN_SEPARATOR}/{deployer_id}/{chain_creation_iso}",
            )
        )
        payload: dict[str, Any] = {
            "deployer_id": deployer_id,
            "chain_creation_iso": chain_creation_iso,
            "genesis_version": GENESIS_VERSION,
        }
        genesis_event = AuditEvent.create(
            event_type=AuditEventType.AGENT_STARTED,
            autonomy_level=AutonomyLevel.A0,
            agent_id=GENESIS_AGENT_ID,
            payload=payload,
            prev_hash=seed,
            event_id=event_id,
            timestamp=chain_creation_iso,
            schema_version=SCHEMA_VERSION,
        )
        self._store.append(genesis_event)

    def _warn_if_legacy_seed(self) -> None:
        events = list(self._store)
        if not events:
            return
        first = events[0]
        if first.prev_hash == GENESIS_HASH and not _is_hardened_genesis(first):
            warnings.warn(
                "AuditChain uses the legacy GENESIS_HASH sentinel "
                "(prev_hash='0'*64) as its seed. Hardened chains derive a "
                "per-deployer genesis hash so an attacker cannot regenerate "
                "a chain from scratch and match the legitimate deployer "
                "identity. Re-create with an explicit deployer_id to upgrade.",
                DeprecationWarning,
                stacklevel=3,
            )

    def _verification_seed(self) -> str:
        """Branch the genesis seed for verification (the corrected P3 fix).

        Recompute the deployer-keyed seed from the genesis event's own
        payload when a hardened genesis event #0 is present; otherwise fall
        back to the legacy ``"0"*64`` sentinel. This is what lets BOTH a
        hardened chain and a legacy chain verify True.
        """
        events = list(self._store)
        if events and _is_hardened_genesis(events[0]):
            payload = events[0].payload
            return _compute_genesis_hash(
                str(payload["deployer_id"]),
                str(payload["chain_creation_iso"]),
            )
        return GENESIS_HASH

    # ---------------------------------------------------------------- #
    # Accessors                                                        #
    # ---------------------------------------------------------------- #

    @property
    def _events(self) -> list[AuditEvent]:
        return list(self._store)

    @property
    def length(self) -> int:
        return len(self._store)

    # ---------------------------------------------------------------- #
    # Append + verify                                                  #
    # ---------------------------------------------------------------- #

    def append(
        self,
        event_type: AuditEventType,
        autonomy_level: AutonomyLevel,
        agent_id: str,
        payload: dict[str, Any],
        actor_id: str | None = None,
    ) -> AuditEvent:
        """Append a new event to the chain and persist it.

        The TSA stamp (when a TSA source is wired) binds the attested time
        to a canonical pre-timestamp digest of the event's identifying
        fields, not to empty bytes. Held under ``_append_lock`` to close the
        TOCTOU window between reading the head and appending.
        """
        with self._append_lock:
            event_id = str(uuid.uuid4())
            prev_hash = self._store.head_event_hash()

            canonical = json.dumps(
                {
                    "event_id": event_id,
                    "event_type": event_type.value,
                    "autonomy_level": autonomy_level.value,
                    "agent_id": agent_id,
                    "payload": payload,
                    "actor_id": actor_id,
                    "prev_hash": prev_hash,
                    "schema_version": SCHEMA_VERSION,
                },
                sort_keys=True,
            ).encode()
            pre_digest = hashlib.sha256(canonical).digest()

            ts_response = self._timestamp_source.stamp(pre_digest)
            timestamp_iso = ts_response.asserted_at.isoformat()
            if ts_response.tsr_token_b64 is not None:
                payload = {**payload, "_tsr_token_b64": ts_response.tsr_token_b64}

            event = AuditEvent.create(
                event_type=event_type,
                autonomy_level=autonomy_level,
                agent_id=agent_id,
                payload=payload,
                prev_hash=prev_hash,
                event_id=event_id,
                actor_id=actor_id,
                timestamp=timestamp_iso,
                schema_version=SCHEMA_VERSION,
            )
            self._store.append(event)
            return event

    def verify(self) -> bool:
        """Replay the chain and verify every hash. False if tampered.

        Soft-failure variant. Seeds from the branched genesis seed so a
        clean hardened chain verifies True (the reference impl raised a
        false TAMPER here).
        """
        with self._append_lock:
            prev = self._verification_seed()
            for event in self._store:
                if event.event_hash != event._compute_hash():
                    return False
                if event.prev_hash != prev:
                    return False
                prev = event.event_hash
            return True

    def verify_strict(self) -> None:
        """Raise ``AuditChainTamperError`` on any inconsistency.

        Detects ``event_hash mismatch`` (entry fields changed after write)
        and ``prev_hash mismatch`` (chain link broken), seeding from the
        same branched genesis seed as ``verify``.
        """
        with self._append_lock:
            prev = self._verification_seed()
            for index, event in enumerate(self._store):
                if event.event_hash != event._compute_hash():
                    raise AuditChainTamperError(
                        f"event_hash mismatch at index {index} (event_id={event.event_id!r})"
                    )
                if event.prev_hash != prev:
                    raise AuditChainTamperError(
                        f"prev_hash mismatch at index {index} "
                        f"(event_id={event.event_id!r}): "
                        f"expected {prev!r}, got {event.prev_hash!r}"
                    )
                prev = event.event_hash

    def chain_head(self) -> str:
        """Current ``event_hash`` of the last entry; genesis seed if empty."""
        return self._store.head_event_hash()

    def anchor_to_witness(self) -> AuditEvent | None:
        """Anchor the head to the wired witness register; chain the receipt."""
        if self._witness_register is None:
            return None
        from payments_agent_audit.governance.witness_anchor import (
            anchor_to_witness as _anchor,
        )

        return _anchor(audit_chain=self, witness=self._witness_register)


__all__ = [
    "GENESIS_AGENT_ID",
    "GENESIS_DOMAIN_SEPARATOR",
    "GENESIS_HASH",
    "GENESIS_VERSION",
    "AuditChain",
    "AuditChainTamperError",
    "ProductionModeError",
    "_compute_genesis_hash",
]
