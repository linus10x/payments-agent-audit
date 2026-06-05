"""Sponsor-bank / BaaS oversight tests."""

from __future__ import annotations

from payments_agent_audit.governance.sponsor_bank import (
    BaaSProgramProfile,
    SponsorBankOversight,
)


def _profile(**kw) -> BaaSProgramProfile:
    base = dict(
        program_id="baas-1",
        regulated_entity_of_record="Sponsor Bank N.A.",
        ledger_owner="sponsor_bank",
        fbo_reconciliation_performed=True,
        reconciliation_owner="Sponsor Bank ops",
        third_party_risk_program_covers=True,
    )
    base.update(kw)
    return BaaSProgramProfile(**base)


def test_complete_profile_attestable() -> None:
    r = SponsorBankOversight().assess(_profile())
    assert r.attestable is True
    assert r.findings == ()


def test_unclear_ledger_not_attestable() -> None:
    r = SponsorBankOversight().assess(_profile(ledger_owner="unclear"))
    assert r.attestable is False
    assert any("ledger ownership is unclear" in f for f in r.findings)


def test_missing_entity_of_record_flagged() -> None:
    r = SponsorBankOversight().assess(_profile(regulated_entity_of_record=""))
    assert r.attestable is False


def test_no_reconciliation_flagged() -> None:
    r = SponsorBankOversight().assess(
        _profile(fbo_reconciliation_performed=False, reconciliation_owner="")
    )
    assert r.attestable is False
    assert len(r.findings) >= 2


def test_third_party_program_gap_flagged() -> None:
    r = SponsorBankOversight().assess(_profile(third_party_risk_program_covers=False))
    assert r.attestable is False


def test_emits_to_chain(chain) -> None:
    SponsorBankOversight(audit_chain=chain).assess(_profile())
    assert any(e.event_type.value == "payments.sponsor_bank_oversight" for e in chain._events)
