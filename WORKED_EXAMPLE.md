# Worked example — the irreversible-rail decision class, end to end

This is the thesis of `payments-agent-audit` made concrete. An autonomous agent
tries to move money on an instant rail; the library refuses to trust it that far
until a real pre-authorization control exists, holds a near-match against the
sanctions list, and records every step on a tamper-evident ledger. Everything
below uses the **real public API** and runs with **stdlib only** — no network,
no bundled list data, no external services.

Two runnable scripts back this document:

```bash
pip install -e ".[dev,test-property]"
PYTHONPATH=src python3 examples/instant_rail_promotion_refusal.py   # parts 1–3
PYTHONPATH=src python3 examples/ofac_screen_and_disposition.py      # part 3 (OFAC) + 4
```

---

## 1. The decision class: an irreversible rail

The single property that makes payments different from other regulated decisions
is **reversibility**. A credit on an instant rail — FedNow (Reg J, 12 CFR Part 210
Subpart C) or RTP (TCH Operating Rules) — is *final and irrevocable the moment it
settles*. A control that fires *after* authorization governs nothing on such a
rail: the money is already gone. ACH carries a return/reversal window; card rails
carry chargeback rights. A governance framework that treats all rails the same is
wrong about the one thing that matters most.

So `payments-agent-audit` makes finality a **first-class input** to the autonomy
decision. `rail_finality.py` classifies a rail; the level-gate in
`autonomy_ladder.py` then applies a rule the other libraries do not have:
**an irreversible-write program cannot reach A3/A4 on a post-hoc control alone.**

## 2. An agent attempts an autonomous instant-rail payment

`examples/instant_rail_promotion_refusal.py` asks the gate to promote a FedNow
instant-payout bot to **A3 (supervised-autonomous)**. To isolate the
irreversibility rule as the *sole* cause of refusal, every **lower-gate** criterion
is independently attested as satisfied by a second-line MRM owner:

```python
from payments_agent_audit.governance.audit_chain import AuditChain
from payments_agent_audit.governance.autonomy_ladder import (
    Attestation, AutonomyLadderGate, AutonomyTier, PromotionRequest,
)

chain = AuditChain(deployer_id="acme-pay-prod")
gate = AutonomyLadderGate(audit_chain=chain, mode="production")

lower_gate = tuple(
    Attestation(criterion=c, satisfied=True, attested_by="mrm-lead",
                attester_role="second_line_mrm",
                attested_at="2026-06-05T00:00:00+00:00",
                evidence_ref=f"evidence://{c}")
    for c in ("sovereign_veto_load_tested", "audit_ledger_min_window",
              "shadow_mode_min_window", "circuit_breaker_recent")
)

# A FedNow instant-payout bot whose ONLY control acts AFTER authorization.
request = PromotionRequest(
    target_tier=AutonomyTier.A3_SUPERVISED_AUTONOMOUS,
    decision_class="instant_payout",
    program_id="fednow-payout-bot",
    moves_money=True,
    rail_id="fednow",                          # final-by-rule
    controls=frozenset({"post_hoc_veto"}),     # acts AFTER authorization
    attestations=lower_gate,
)
decision = gate.evaluate(request)
```

## 3. AL-PROBE-06 refuses promotion — and the OFAC screen holds a near-match

**The gate refuses.** Not because autonomy is forbidden, but because the program's
only control acts *after* an irreversible credit settles. Add a genuine, attested
**pre-authorization** control and the same program becomes promotable:

```
=== Post-hoc-veto-only on FedNow ===
granted                = False
irreversibility_refusal = True
  - IRREVERSIBILITY REFUSAL: program 'fednow-payout-bot' moves money on FedNow Service (instant credit) (final-by-rule), and its only controls act after authorization (['post_hoc_veto']). An irreversible-write program must carry an attested pre-authorization control (one of ['beneficiary_allowlist', 'confirmation_of_payee', 'dual_control_release', 'pre_auth_ofac_screening', 'pre_send_amount_envelope', 'pre_send_velocity_envelope']) before A3/A4.

=== With an attested pre-authorization control ===
granted                = True
irreversibility_refusal = False

Ledger verified — refusal recorded as IRREVERSIBLE_PROMOTION_REFUSED.
```

A complementary control sits one layer down: even an A2+ agent **cannot move
money past a sanctions hit**. `examples/ofac_screen_and_disposition.py` runs a
clear name, then a near-match (word order reversed, against an in-memory stand-in
feed — the library bundles no SDN data). The near-match is **HELD** under strict
liability, and the agent is barred from clearing its own hit:

```
=== Screen: 'Jane Doe' ===
status     = clear
is_held    = False
is_cleared = True

=== Screen: 'Smirnoff Vladimir' ===
status     = potential_match
is_held    = True   <- payment MUST NOT proceed
top match  = Vladimir Smirnov (score 0.909)

Self-disposition rejected: self-disposition forbidden: operator 'ofac-screener' equals agent_id; an agent cannot clear its own sanctions hit (strict liability)
```

## 4. The audit entry — and the human disposition

Only an **authenticated human** may disposition a held screen. When an analyst
clears it as a false positive, the screen is released and the action is written
to the ledger alongside the screens themselves:

```
=== After human disposition ===
disposition    = false_positive
dispositioned_by = analyst-jane
is_held        = False
is_cleared     = True

Ledger verified — screens + disposition recorded.
```

## 5. Demotion / refusal, recorded

Both flows close by verifying the hash-chain ledger. The promotion refusal is
recorded as an `IRREVERSIBLE_PROMOTION_REFUSED` event; the OFAC screens and the
human disposition are each their own ledger entries. `chain.verify()` returns
`True` only if no entry has been altered or the chain regenerated — so the *record
of the refusal* is as tamper-evident as the refusal itself. A program that loses
its pre-authorization control is demoted on the same rule that blocked it here:
the climb is one rung at a time on evidence; the demotion is mechanical the moment
the evidence lapses.

---

**This is reference IP, not legal advice, and not a deployed control.** It ships
no sanctions-list data and runs in no institution's payment flow. Sanctions-match
calibration, SAR disposition, and Reg E adjudication are the deploying institution's
compliance function's responsibility. See [`AUTONOMY_LADDER.md`](AUTONOMY_LADDER.md)
for how these primitives map to the A0→A4 framework, and
[autonomy-ladder.io](https://autonomy-ladder.io) for the framework itself.
