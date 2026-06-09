#!/usr/bin/env python3
"""AL-PROBE-06 — instant-rail promotion refusal, end to end.

A FedNow instant-payout bot asks to be promoted to A3 (supervised-autonomous).
Every *lower* gate criterion is independently attested as satisfied, so the
irreversibility gate is the sole cause of refusal: the program's only control
acts AFTER authorization, and a FedNow credit is final the moment it settles —
a post-hoc veto governs nothing on that rail.

Run:
    PYTHONPATH=src python3 examples/instant_rail_promotion_refusal.py
"""

from __future__ import annotations

from payments_agent_audit.governance.audit_chain import AuditChain
from payments_agent_audit.governance.autonomy_ladder import (
    Attestation,
    AutonomyLadderGate,
    AutonomyTier,
    PromotionRequest,
)


def main() -> None:
    chain = AuditChain(deployer_id="acme-pay-prod")
    gate = AutonomyLadderGate(audit_chain=chain, mode="production")

    # The four lower-gate criteria, each independently attested (2nd-line MRM),
    # so the irreversibility gate is the ONLY thing left to refuse on.
    lower_gate = tuple(
        Attestation(
            criterion=c,
            satisfied=True,
            attested_by="mrm-lead",
            attester_role="second_line_mrm",
            attested_at="2026-06-05T00:00:00+00:00",
            evidence_ref=f"evidence://{c}",
        )
        for c in (
            "sovereign_veto_load_tested",
            "audit_ledger_min_window",
            "shadow_mode_min_window",
            "circuit_breaker_recent",
        )
    )

    # A FedNow instant-payout bot whose ONLY control is a post-hoc veto.
    refused = PromotionRequest(
        target_tier=AutonomyTier.A3_SUPERVISED_AUTONOMOUS,
        decision_class="instant_payout",
        program_id="fednow-payout-bot",
        moves_money=True,
        rail_id="fednow",  # final-by-rule
        controls=frozenset({"post_hoc_veto"}),  # acts AFTER authorization
        attestations=lower_gate,
    )
    decision = gate.evaluate(refused)
    print("=== Post-hoc-veto-only on FedNow ===")
    print(f"granted                = {decision.granted}")
    print(f"irreversibility_refusal = {decision.irreversibility_refusal}")
    for f in decision.failures:
        print(f"  - {f}")
    assert decision.granted is False
    assert decision.irreversibility_refusal is True

    # Add a genuine PRE-authorization control, independently attested as
    # wired/effective, and the same program is promotable.
    pre_auth = lower_gate + (
        Attestation(
            criterion="pre_auth_control_effective",
            satisfied=True,
            attested_by="audit-lead",
            attester_role="third_line_audit",
            attested_at="2026-06-05T00:00:00+00:00",
            evidence_ref="evidence://pre_auth_control_effective",
        ),
    )
    promotable = PromotionRequest(
        target_tier=AutonomyTier.A3_SUPERVISED_AUTONOMOUS,
        decision_class="instant_payout",
        program_id="fednow-payout-bot",
        moves_money=True,
        rail_id="fednow",
        controls=frozenset({"post_hoc_veto", "pre_send_amount_envelope"}),
        attestations=pre_auth,
    )
    granted = gate.evaluate(promotable)
    print("\n=== With an attested pre-authorization control ===")
    print(f"granted                = {granted.granted}")
    print(f"irreversibility_refusal = {granted.irreversibility_refusal}")
    assert granted.granted is True
    assert granted.irreversibility_refusal is False

    # The refusal was recorded to the tamper-evident ledger.
    chain.verify()
    print("\nLedger verified — refusal recorded as IRREVERSIBLE_PROMOTION_REFUSED.")


if __name__ == "__main__":
    main()
