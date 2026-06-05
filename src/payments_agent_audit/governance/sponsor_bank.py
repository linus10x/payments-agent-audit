"""Sponsor-bank / BaaS oversight gate (regulated-entity-of-record).

In a Banking-as-a-Service arrangement a fintech program operates *under* a
sponsor bank that remains the regulated entity of record. The June 2023
Interagency Guidance on Third-Party Relationships: Risk Management (OCC
Bulletin 2023-17 / FDIC FIL-29-2023 / Fed SR 23-4) holds the bank responsible
for risk management across the full life cycle of the relationship. The
Synapse collapse (2024) showed the concrete failure mode: when ledger
ownership and end-user fund reconciliation are ambiguous between the
middleware/fintech and the bank, end users lose access to their money.

This gate records, for an autonomous BaaS payment program, the structural
facts that the sponsor-bank oversight depends on, and refuses to attest
oversight when they are missing:

  * the named **regulated entity of record** (the sponsor bank),
  * who **owns the end-user ledger / reconciliation** (bank vs middleware),
  * whether **FBO/custodial reconciliation** is performed and by whom,
  * whether the bank's **third-party risk-management program** covers this
    program (per the Interagency Guidance).

Reference IP, not legal advice. Reg anchor (staged, primary-sourced):
``baas_sponsor_bank``.
"""

from __future__ import annotations

from dataclasses import dataclass

from payments_agent_audit.schemas.audit_event import (
    AuditChain,
    AuditEventType,
    AutonomyLevel,
)


class SponsorBankOversightError(RuntimeError):
    """Raised when required oversight facts are missing."""


@dataclass(frozen=True)
class BaaSProgramProfile:
    program_id: str
    regulated_entity_of_record: str  # the sponsor bank
    ledger_owner: str  # "sponsor_bank" | "middleware" | "fintech" | "unclear"
    fbo_reconciliation_performed: bool
    reconciliation_owner: str
    third_party_risk_program_covers: bool


@dataclass(frozen=True)
class OversightResult:
    program_id: str
    attestable: bool
    findings: tuple[str, ...]


class SponsorBankOversight:
    """Gate that checks BaaS oversight structural facts."""

    def __init__(
        self, audit_chain: AuditChain | None = None, agent_id: str = "sponsor-bank-oversight"
    ) -> None:
        self._audit_chain = audit_chain
        self.agent_id = agent_id

    def assess(
        self, profile: BaaSProgramProfile, *, actor_id: str | None = None
    ) -> OversightResult:
        findings: list[str] = []
        if not profile.regulated_entity_of_record.strip():
            findings.append("no named regulated entity of record (sponsor bank)")
        if profile.ledger_owner.strip().lower() in ("", "unclear"):
            findings.append(
                "end-user ledger ownership is unclear — the Synapse failure mode "
                "(reconciliation ambiguity between bank and middleware)"
            )
        if not profile.fbo_reconciliation_performed:
            findings.append("FBO/custodial reconciliation is not performed")
        if not profile.reconciliation_owner.strip():
            findings.append("no named owner for reconciliation")
        if not profile.third_party_risk_program_covers:
            findings.append(
                "the sponsor bank's third-party risk-management program does not "
                "cover this program (Interagency Guidance, June 2023)"
            )
        result = OversightResult(
            program_id=profile.program_id,
            attestable=not findings,
            findings=tuple(findings),
        )
        if self._audit_chain is not None:
            self._audit_chain.append(
                event_type=AuditEventType.SPONSOR_BANK_OVERSIGHT,
                autonomy_level=AutonomyLevel.A2,
                agent_id=self.agent_id,
                payload={
                    "program_id": profile.program_id,
                    "regulated_entity_of_record": profile.regulated_entity_of_record,
                    "ledger_owner": profile.ledger_owner,
                    "attestable": result.attestable,
                    "findings": list(result.findings),
                },
                actor_id=actor_id,
            )
        return result


__all__ = [
    "BaaSProgramProfile",
    "OversightResult",
    "SponsorBankOversight",
    "SponsorBankOversightError",
]
