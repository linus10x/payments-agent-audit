"""Golden corpus — real public matters as parametrized fixtures (§7 credibility tier).

Each fixture asserts how THIS library's controls would have flagged or governed
a real enforcement action / litigation / incident. Matters of record only; every
fixture carries a primary-source URL (or unverified flag). The corpus is the
credibility tier: it is what makes the audit undismissable.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
import yaml

from payments_agent_audit.governance.audit_chain import AuditChain
from payments_agent_audit.governance.autonomy_ladder import (
    Attestation,
    AutonomyLadderGate,
    AutonomyTier,
    PromotionRequest,
)
from payments_agent_audit.governance.ofac_screening import (
    OFACScreener,
    SanctionedParty,
    ScreeningStatus,
)
from payments_agent_audit.governance.reg_e import ErrorType, RegEErrorResolution
from payments_agent_audit.governance.sar_workflow import SARWorkflowAudit, SARWorkflowError
from payments_agent_audit.governance.sponsor_bank import (
    BaaSProgramProfile,
    SponsorBankOversight,
)
from tests.conftest import StaticSanctionsList

CREATED = "2026-06-05T00:00:00+00:00"
_CORPUS = yaml.safe_load((Path(__file__).parent / "corpus.yaml").read_text())


def _all_entries() -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    for bucket, entries in _CORPUS.items():
        for e in entries:
            out.append((f"{bucket}/{e['id']}", e))
    return out


ENTRIES = _all_entries()


def test_corpus_loaded() -> None:
    assert len(ENTRIES) >= 10, "golden corpus should carry the curated set of matters"


@pytest.mark.parametrize("entry", [e for _, e in ENTRIES], ids=[i for i, _ in ENTRIES])
def test_every_fixture_has_primary_source(entry: dict) -> None:
    assert entry.get("url") or entry.get("unverified") is True, (
        f"fixture {entry['id']} must carry a primary-source URL or be marked unverified"
    )
    assert entry.get("summary"), "fixture must carry a matter-of-record summary"


def _full_attestations() -> tuple[Attestation, ...]:
    return tuple(
        Attestation(c, True, "mrm", "second_line_mrm", CREATED, f"e://{c}")
        for c in (
            "sovereign_veto_load_tested",
            "audit_ledger_min_window",
            "shadow_mode_min_window",
            "circuit_breaker_recent",
        )
    )


@pytest.mark.parametrize("entry", [e for _, e in ENTRIES], ids=[i for i, _ in ENTRIES])
def test_control_would_have_governed_the_matter(entry: dict) -> None:
    """Drive the mapped control with the matter's facts and assert the
    governing outcome (flag / refuse / non-compliant)."""
    control = entry["control"]
    chain = AuditChain(deployer_id="golden", chain_creation_iso=CREATED)

    if control == "ofac_screen":
        provider = StaticSanctionsList([SanctionedParty(uid=entry["id"], name=entry["sdn_name"])])
        screener = OFACScreener(provider, audit_chain=chain)
        result = screener.screen(entry["screen_name"])
        assert result.status is ScreeningStatus.POTENTIAL_MATCH
        assert result.is_held is True

    elif control == "sar_timeliness":
        sw = SARWorkflowAudit(audit_chain=chain)
        r = sw.check_timeliness(
            detection_date=datetime.fromisoformat(entry["detection_iso"]),
            proposed_filing_date=datetime.fromisoformat(entry["proposed_filing_iso"]),
            suspect_identified=entry["suspect_identified"],
            case_id=entry["id"],
        )
        assert r.meets_deadline is entry["expect_meets_deadline"]

    elif control == "sar_disposition":
        sw = SARWorkflowAudit(audit_chain=chain)
        with pytest.raises(SARWorkflowError):
            sw.validate_alert_disposition(entry["vague_rationale"])

    elif control == "reg_e":
        re_gate = RegEErrorResolution(audit_chain=chain)
        r = re_gate.resolve(
            error_type=ErrorType.UNAUTHORIZED_TRANSFER,
            notice_date=datetime.fromisoformat(entry["notice_iso"]),
            investigation_completion_date=datetime.fromisoformat(entry["completion_iso"]),
            provisional_credit_given=entry["provisional_credit"],
            is_new_account_pos_or_foreign=False,
            claim_id=entry["id"],
        )
        assert r.compliant is entry["expect_compliant"]

    elif control == "irreversibility":
        gate = AutonomyLadderGate(audit_chain=chain, mode="production")
        req = PromotionRequest(
            target_tier=AutonomyTier.A3_SUPERVISED_AUTONOMOUS,
            decision_class="instant_payout",
            program_id=entry["id"],
            moves_money=True,
            rail_id=entry["rail_id"],
            controls=frozenset({"post_hoc_veto"}),
            attestations=_full_attestations(),
        )
        decision = gate.evaluate(req)
        assert decision.granted is False
        assert decision.irreversibility_refusal is True

    elif control == "sponsor_bank":
        gate = SponsorBankOversight(audit_chain=chain)
        result = gate.assess(
            BaaSProgramProfile(
                program_id=entry["id"],
                regulated_entity_of_record="Partner Bank",
                ledger_owner=entry["ledger_owner"],
                fbo_reconciliation_performed=False,
                reconciliation_owner="",
                third_party_risk_program_covers=False,
            )
        )
        assert result.attestable is False
        assert any("ledger ownership is unclear" in f for f in result.findings)

    else:  # pragma: no cover - guards against an unmapped control value
        pytest.fail(f"unmapped control {control!r} in fixture {entry['id']}")
