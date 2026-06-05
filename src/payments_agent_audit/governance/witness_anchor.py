"""External witness anchoring — the ``WitnessRegister`` Protocol seam.

A hash-chain is *internally consistent* by construction: an attacker with
full write access to the storage layer can regenerate the entire chain
end-to-end, and the regenerated chain passes ``verify()``. To make the
chain adversarially tamper-EVIDENT, the chain head must be periodically
anchored to an external register the deployer does not control alone:
OpenTimestamps, Sigstore Rekor, a regulator-side append-only log, or a
notarized blockchain anchor.

``anchor_to_witness`` publishes the current head to the wired register and
writes the receipt back into the chain as a ``WITNESS_ANCHOR`` event, so
the receipt is itself hash-chained — tampering with the receipt requires
tampering with every entry after it.

In a *production-mode* chain (``mode="production"``) a missing witness
register fails closed: the chain refuses to start. See
``audit_chain.AuditChain``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from payments_agent_audit.governance.audit_chain import AuditChain
    from payments_agent_audit.schemas.audit_event import AuditEvent


@runtime_checkable
class WitnessRegister(Protocol):
    """An external append-only register that the deployer does not own alone."""

    def submit(self, chain_head: str) -> str:
        """Publish ``chain_head``; return an opaque receipt identifier."""
        ...


def anchor_to_witness(*, audit_chain: AuditChain, witness: WitnessRegister) -> AuditEvent:
    """Anchor the chain head to ``witness`` and chain the receipt."""
    from payments_agent_audit.schemas.audit_event import (
        AuditEventType,
        AutonomyLevel,
    )

    head = audit_chain.chain_head()
    receipt = witness.submit(head)
    return audit_chain.append(
        event_type=AuditEventType.WITNESS_ANCHOR,
        autonomy_level=AutonomyLevel.A0,
        agent_id="payments-audit-chain",
        payload={"anchored_head": head, "witness_receipt": receipt},
    )


__all__ = ["WitnessRegister", "anchor_to_witness"]
