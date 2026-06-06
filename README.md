# payments-agent-audit

**Governance patterns for autonomous AI agents in regulated payments.**

> **STAGED — pre-publication.** Built and verified locally; not yet published.
> No public remote, release tag, or DOI exists until owner sign-off (see
> `docs/DOI_PLAN.md`). Test/coverage figures below describe this local build.

Reference IP for adoption — tested patterns a payments program can
build on, not a control operating in production. Zero runtime
dependencies (stdlib only), typed, MIT-licensed.

This library carries the five Autonomy-Ladder governance primitives built to a
corrected specification, plus payments-specific controls: a real OFAC sanctions
screening workflow, BSA/AML SAR timeliness and the Travel Rule, Regulation E
error resolution, sponsor-bank / BaaS oversight, and a **first-class rail-finality
/ irreversibility dimension** that gates how far an instant-payment program may be
trusted to act autonomously.

---

## Why payments needs its own library

The single property that makes payments different is **reversibility**. An
instant-rail credit — FedNow (12 CFR Part 210, Subpart C) or RTP (TCH Operating
Rules) — is *final and irrevocable the moment it settles*. A control that fires
*after* authorization governs nothing on such a rail: the money is already gone.
ACH (the Nacha Operating Rules) is different — it has a return/reversal window, so
a post-hoc control still has something to act on. Card rails carry chargeback
rights. **A governance framework that treats all rails the same is wrong about
the one thing that matters most.**

This library makes finality a first-class input and refuses to promote an
irreversible-write program to a high autonomy level on a post-hoc veto alone.

## Implemented vs. Patterned (read this first)

This project is honest about what is code and what is a documented pattern. Public
claims match implemented reality.

| Capability | Status | Notes |
|---|---|---|
| Autonomy-ladder promotion gate (A0–A4) + irreversibility refusal | **Implemented** | `autonomy_ladder.py`; tested, incl. AL-PROBE-06 |
| Sovereign veto (fail-closed production mode, authenticated principal) | **Implemented** | `sovereign_veto.py` |
| Hash-chain audit ledger (branched genesis seed; tamper + regeneration detection) | **Implemented** | `audit_chain.py` |
| DEFCON risk-state machine (transition-direction guard) | **Implemented** | `defcon.py`; thresholds are illustrative |
| Effective-challenge harness (rejects self-challenge; independence attestation) | **Implemented** | `effective_challenge_harness.py` |
| **OFAC sanctions screening** (fuzzy match + hit disposition) | **Implemented** | `ofac_screening.py`; runs against a **pluggable list — no list is bundled** |
| BSA/AML SAR timeliness + Travel Rule + alert-disposition | **Implemented** | `sar_workflow.py` |
| Regulation E error resolution | **Implemented** | `reg_e.py` |
| Sponsor-bank / BaaS oversight | **Implemented** | `sponsor_bank.py` |
| Rail-finality classification (FedNow/RTP/Fedwire/ACH/card) | **Implemented** | `rail_finality.py` |
| External witness anchoring (OpenTimestamps / Rekor) | **Patterned** | `WitnessRegister` is an interface; deployer wires the register |
| RFC 3161 trusted timestamps | **Patterned** | `TimestampSource` interface; `LocalClock` ships, TSA is a deployer integration |

The five primitives are **real, tested reference patterns** — not a deployed
control wrapped in an org assurance apparatus. Use them as reference IP for
adoption, never as "a control operating in production."

## The five primitives (built to the corrected standard)

1. **Level-gate (A0→A4)** — refuses promotion when lower-level controls are
   unmet, and in production mode requires **independent attestation** (second-line
   MRM / third-line audit) of each criterion rather than trusting caller-asserted
   booleans. It also runs the **irreversibility gate** below.
2. **Sovereign veto** — a wired `Authorizer` is **mandatory** in production mode
   (refuses to start without one); the operator who clears a veto is an
   **authenticated principal** resolved from a credential, never a free string; an
   agent cannot clear its own veto.
3. **Hash-chain ledger** — the genesis seed is **branched**: a deployer-keyed
   hardened chain and a legacy chain *both* verify True, while in-place tampering
   and end-to-end regeneration are both detected (the latter via an external
   witness anchor, which is mandatory in production mode).
4. **DEFCON state machine** — a **transition-direction guard**: the automatic
   path cannot de-escalate out of HALT, and a manual override out of HALT may only
   step to the adjacent level, so a recovering program passes back through the
   review states instead of snapping fully open.
5. **Effective-challenge harness** — rejects a challenger that **is** the primary
   (a self-challenge is a rubber stamp), and records an operator-supplied
   **independence attestation** (who chose the challenger, when, and whether it is
   the same owner / vendor family / prompt template). A non-independent challenger
   cannot yield a clean `accept_primary`.

## AL-PROBE-06 — the irreversibility gate (new to this library)

```python
from payments_agent_audit.governance.audit_chain import AuditChain
from payments_agent_audit.governance.autonomy_ladder import (
    AutonomyLadderGate, AutonomyTier, PromotionRequest, Attestation,
)

chain = AuditChain(deployer_id="acme-pay-prod")
gate = AutonomyLadderGate(audit_chain=chain, mode="production")

# The four lower-gate criteria, each independently attested (2nd-line MRM /
# 3rd-line audit) — so the irreversibility gate is the SOLE cause of refusal:
lower_gate_attestations = tuple(
    Attestation(c, satisfied=True, attested_by="mrm-lead", attester_role="second_line_mrm",
                attested_at="2026-06-05T00:00:00+00:00", evidence_ref=f"evidence://{c}")
    for c in ("sovereign_veto_load_tested", "audit_ledger_min_window",
              "shadow_mode_min_window", "circuit_breaker_recent")
)

# A FedNow instant-payout bot whose ONLY control is a post-hoc veto.
request = PromotionRequest(
    target_tier=AutonomyTier.A3_SUPERVISED_AUTONOMOUS,
    decision_class="instant_payout",
    program_id="fednow-payout-bot",
    moves_money=True,
    rail_id="fednow",                            # final-by-rule
    controls=frozenset({"post_hoc_veto"}),       # acts AFTER authorization
    attestations=lower_gate_attestations,        # every LOWER gate is satisfied
)

decision = gate.evaluate(request)
assert decision.granted is False                 # REFUSED
assert decision.irreversibility_refusal is True  # ...on irreversibility grounds
# The refusal is recorded to the ledger as IRREVERSIBLE_PROMOTION_REFUSED.
```

Add a genuine **pre-authorization** control (pre-auth OFAC screening, a pre-send
amount/velocity envelope, dual-control release, confirmation-of-payee) and the
same program is promotable. The gate blocks post-hoc-only autonomy on irreversible
rails — not autonomy itself. **ACH is modeled non-final separately**: the
instant-rail finality rule does not apply to it.

## OFAC screening (a real control, not a doc)

```python
from payments_agent_audit.governance.ofac_screening import OFACScreener, Disposition

# You supply the list — the OFAC SDN/consolidated list changes constantly and
# nothing is bundled. Implement SanctionsListProvider against your live feed.
screener = OFACScreener(list_provider=my_sdn_feed, audit_chain=chain)

result = screener.screen("Vladimir Smirnoff")     # fuzzy / word-order aware
if result.is_held:                                # strict liability: do not proceed
    # An agent CANNOT clear its own hit. A human dispositions it:
    screener.disposition(result, Disposition.FALSE_POSITIVE,
                         operator_id="analyst-jane", reason="DOB mismatch")
```

## Install & test

```bash
pip install -e ".[dev,test-property]"
pytest tests/ --cov=src/payments_agent_audit --cov-fail-under=90
pytest tests/adversarial/ -v          # the six AL-PROBES (11 test functions)
python3 scripts/mutation_pass.py      # surgical mutation pass over the invariants
```

As of this build: **185 tests pass at 98.97% coverage.** Four assurance tiers back
the claims, each a discrete count:

- **Property tier** — a Hypothesis suite generating up to 2,300 cases per run
  (a ceiling, not a floor) across the ledger, finality, gate, veto, and OFAC invariants.
- **Golden-corpus tier** — 11 real, primary-sourced enforcement / litigation /
  incident matters as parametrized fixtures (each carries a primary-source URL).
- **Adversarial tier** — the six AL-PROBES, 11 committed test functions under
  `tests/adversarial/`.
- **Mutation tier** — a surgical pass that kills all 23 targeted mutants of the
  load-bearing invariants.

See `docs/` for the full assurance map.

## Documentation

- `ARCHITECTURE.md` — the control/audit planes and the Protocol seams
- `ASSURANCE-GUIDE.md` — the assurance-catalog map and the AL-PROBES
- `FAILURE-MODES.md` — adversarial failure modes and what is/isn't defended
- `LIMITATIONS.md` — known boundaries and non-scope
- `DISCLAIMER.md` — reference IP, not legal advice
- `docs/research/primary_source_research_2026-06-05.md` — reg + corpus provenance
- `CITATION.cff` — how to cite; DOI plan in `docs/DOI_PLAN.md`

## Regulatory anchors

Anchors are sourced to primary materials and staged for the canonical regulatory
list (see `docs/research/`). Confirm any statute/CFR citation against the cited
primary source before relying on it; two anchors carry open items pending counsel
(the exact RTP irrevocability section and the Nacha reversal-window rule number) —
see `LIMITATIONS.md`. **This is reference IP, not legal advice** — sanctions
screening calibration, SAR disposition, and Reg E adjudication are the deploying
institution's compliance function's responsibility.

## License

MIT. See `LICENSE-MIT`.

> Patterns extracted from a private quantitative options program; the source
> program operates in paper-trading Phase 0 — no live capital has been deployed.
> Reference patterns and characterizations are summaries, not legal advice —
> consult qualified counsel and qualified compliance practitioners.
