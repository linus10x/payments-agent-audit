"""Pluggable ledger storage — the ``LedgerStore`` Protocol seam.

The ``AuditChain`` does not own persistence; it delegates to a
``LedgerStore``. Two reference stores ship here:

  * ``InMemoryLedgerStore`` — a list-backed store for tests and
    single-process use. Fast iteration, no durability.
  * ``JsonlLedgerStore`` — an append-only JSONL file with a POSIX
    ``flock`` so multiple writers on one host serialize at the
    file-system layer (the chain's own ``RLock`` serializes within a
    process). Each line is replayed through ``AuditEvent.from_jsonl`` on
    load, so on-disk tampering is detected at read time.

For SEC 17a-4 / WORM deployments, supply a store backed by
write-once-read-many media; the chain contract is unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if sys.platform != "win32":
    import fcntl
else:  # pragma: no cover - exercised on Windows hosts only
    fcntl = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from collections.abc import Iterator

    from payments_agent_audit.schemas.audit_event import AuditEvent

GENESIS_HASH = "0" * 64


@runtime_checkable
class LedgerStore(Protocol):
    """Append-only storage for chained audit events."""

    def append(self, event: AuditEvent) -> None: ...

    def head_event_hash(self) -> str: ...

    def __iter__(self) -> Iterator[AuditEvent]: ...

    def __len__(self) -> int: ...


class InMemoryLedgerStore:
    """List-backed store. Fast, ephemeral; the default for the chain."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append(self, event: AuditEvent) -> None:
        self._events.append(event)

    def head_event_hash(self) -> str:
        if not self._events:
            return GENESIS_HASH
        return self._events[-1].event_hash

    def __iter__(self) -> Iterator[AuditEvent]:
        # Iterate over a snapshot so a concurrent append cannot mutate the
        # list mid-walk (the chain also holds its RLock during verify()).
        return iter(list(self._events))

    def __len__(self) -> int:
        return len(self._events)


class JsonlLedgerStore:
    """Append-only JSONL-file store with cross-process flock discipline."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._events: list[AuditEvent] = []
        self._load_existing()

    def _load_existing(self) -> None:
        from payments_agent_audit.schemas.audit_event import AuditEvent

        if not self.path.exists():
            return
        import json

        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            # from_jsonl raises AuditChainTamperError on a modified line.
            self._events.append(AuditEvent.from_jsonl(json.loads(line)))

    def append(self, event: AuditEvent) -> None:
        with open(self.path, "a", encoding="utf-8") as fh:
            if fcntl is not None:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                fh.write(event.to_jsonl() + "\n")
                fh.flush()
            finally:
                if fcntl is not None:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        self._events.append(event)

    def head_event_hash(self) -> str:
        if not self._events:
            return GENESIS_HASH
        return self._events[-1].event_hash

    def __iter__(self) -> Iterator[AuditEvent]:
        return iter(list(self._events))

    def __len__(self) -> int:
        return len(self._events)


__all__ = [
    "GENESIS_HASH",
    "InMemoryLedgerStore",
    "JsonlLedgerStore",
    "LedgerStore",
]
