"""Pluggable time anchoring — the ``TimestampSource`` Protocol seam.

The chain binds a timestamp to each event. ``LocalClock`` reads the host
wall clock (free, but only as trustworthy as the host). A deployer needing
a trusted time anchor wires an RFC 3161 TSA source that returns a signed
timestamp token (``tsr_token_b64``) bound to the event's pre-digest; the
token is stashed in the event payload so a verifier can re-check the
``messageImprint`` from the on-disk event alone.

This module ships ``LocalClock`` only — the RFC 3161 codec is a deployer
integration point, kept out of the zero-dependency core.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class TimestampResponse:
    """Result of a ``TimestampSource.stamp`` call.

    ``asserted_at`` is the time bound to the event. ``tsr_token_b64`` is a
    base64 RFC 3161 timestamp token when the source is a TSA, else ``None``
    (no side-channel key is injected when no TSA was contacted).
    """

    asserted_at: datetime
    tsr_token_b64: str | None = None


@runtime_checkable
class TimestampSource(Protocol):
    """Binds a trusted time to a 32-byte pre-digest of an event."""

    def stamp(self, pre_digest: bytes) -> TimestampResponse: ...


class LocalClock:
    """Host wall-clock source. Free; trustworthy only to the host's degree."""

    def stamp(self, pre_digest: bytes) -> TimestampResponse:  # noqa: ARG002
        return TimestampResponse(asserted_at=datetime.now(UTC), tsr_token_b64=None)


__all__ = ["LocalClock", "TimestampResponse", "TimestampSource"]
