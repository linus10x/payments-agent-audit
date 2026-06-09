#!/usr/bin/env python3
"""OFAC screen -> hold -> human disposition, end to end.

U.S. sanctions are a strict-liability regime: a prohibited transaction is a
violation regardless of intent. An autonomous agent therefore cannot self-clear
a potential match — a hit is HELD and only an authenticated human may
disposition it. This walks one clear screen and one held hit through to a
human-recorded FALSE_POSITIVE, with every step written to the audit ledger.

You supply the list. The OFAC SDN / consolidated list changes constantly, so
NOTHING is bundled — you implement SanctionsListProvider against your live feed.
This demo wires a tiny in-memory stand-in so the flow runs offline.

Run:
    PYTHONPATH=src python3 examples/ofac_screen_and_disposition.py
"""

from __future__ import annotations

from payments_agent_audit.governance.audit_chain import AuditChain
from payments_agent_audit.governance.ofac_screening import (
    Disposition,
    OFACScreener,
    SanctionedParty,
    SanctionsScreeningError,
)


class DemoSDNFeed:
    """A stand-in SanctionsListProvider. In production this reads your live
    OFAC SDN / consolidated feed; the library never ships list data."""

    def entries(self) -> list[SanctionedParty]:
        return [
            SanctionedParty(
                uid="SDN-0001",
                name="Vladimir Smirnov",
                aliases=("Smirnov Vladimir", "V. Smirnov"),
                programs=("UKRAINE-EO13662",),
                entity_type="individual",
            ),
        ]


def main() -> None:
    chain = AuditChain(deployer_id="acme-pay-prod")
    screener = OFACScreener(list_provider=DemoSDNFeed(), audit_chain=chain)

    # 1) A name with no list match clears.
    clear = screener.screen("Jane Doe")
    print("=== Screen: 'Jane Doe' ===")
    print(f"status     = {clear.status.value}")
    print(f"is_held    = {clear.is_held}")
    print(f"is_cleared = {clear.is_cleared}")
    assert clear.is_cleared is True
    assert clear.is_held is False

    # 2) A near-match (word order reversed) surfaces and is HELD.
    hit = screener.screen("Smirnoff Vladimir")
    print("\n=== Screen: 'Smirnoff Vladimir' ===")
    print(f"status     = {hit.status.value}")
    print(f"is_held    = {hit.is_held}   <- payment MUST NOT proceed")
    print(f"top match  = {hit.candidates[0].party.name} (score {hit.candidates[0].score:.3f})")
    assert hit.is_held is True

    # 3) An agent CANNOT clear its own hit (strict liability).
    try:
        screener.disposition(
            hit, Disposition.FALSE_POSITIVE, operator_id="ofac-screener", reason="self-clear"
        )
        raise AssertionError("self-disposition should have been rejected")
    except SanctionsScreeningError as exc:
        print(f"\nSelf-disposition rejected: {exc}")

    # 4) A human dispositions it.
    screener.disposition(
        hit,
        Disposition.FALSE_POSITIVE,
        operator_id="analyst-jane",
        reason="DOB and nationality mismatch on review",
    )
    print("\n=== After human disposition ===")
    print(f"disposition    = {hit.disposition.value}")
    print(f"dispositioned_by = {hit.dispositioned_by}")
    print(f"is_held        = {hit.is_held}")
    print(f"is_cleared     = {hit.is_cleared}")
    assert hit.is_held is False
    assert hit.is_cleared is True

    # Every screen and disposition is on the tamper-evident ledger.
    assert chain.verify() is True
    print("\nLedger verified — screens + disposition recorded.")


if __name__ == "__main__":
    main()
