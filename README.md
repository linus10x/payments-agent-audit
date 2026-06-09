# payments-agent-audit

**A runnable governance library for autonomous AI agents in regulated payments — where rail finality, OFAC strict liability, and Reg E meet AI deployment authority.**

[![CI](https://github.com/linus10x/payments-agent-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/linus10x/payments-agent-audit/actions/workflows/ci.yml)
[![coverage](https://img.shields.io/badge/coverage-98.97%25-brightgreen)](#install)
[![tests](https://img.shields.io/badge/tests-183%20passing-brightgreen)](#install)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE-MIT)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue)](pyproject.toml)
[![DOI](https://zenodo.org/badge/1260897052.svg)](https://doi.org/10.5281/zenodo.20592773)
[![Autonomy Ladder family](https://img.shields.io/badge/Autonomy%20Ladder-family%20(6%20libraries)-1b2a4a)](https://github.com/linus10x/autonomy-ladder-libraries)

> **What this is:** a reference library that encodes the [Autonomy Ladder](https://autonomy-ladder.io) (A0→A4) for autonomous payments agents — finality as a first-class input, a non-overridable sovereign veto, a hash-chain audit ledger, and a real OFAC screening control — as runnable, tested Python. If an agent can move money on an instant rail, a control that fires *after* authorization governs nothing; the money is already gone.
> **What this is not:** a deployed production control, a sanctions-list feed, or legal advice. It ships no SDN data and runs in no institution's payment flow.
> **Who this is for:** a payments / fintech compliance or risk lead deciding how far to trust an AI agent on FedNow / RTP / ACH / card rails — or a lab or cloud-provider FSI applied lead who needs a concrete, falsifiable model of deployment-authority governance under strict-liability regimes.

## 30-second tour

- **Verticals:** payments (part of the six-library [Autonomy Ladder family](https://github.com/linus10x/autonomy-ladder-libraries)).
- **Decision classes:** the **rail-finality / irreversibility gate** (AL-PROBE-06) and **OFAC screen → human disposition** — both real, tested controls.
- **Regulators / rules encoded:** OFAC sanctions (strict liability), Regulation E error resolution (12 CFR 1005.11), BSA/AML SAR timeliness + Travel Rule, and rail finality (FedNow Reg J 12 CFR 210 Subpart C · RTP irrevocability · Nacha return windows).
- **Assurance:** **183 tests · 98.97% coverage** · 11 AL-PROBE functions · a 23-mutant author audit (run manually) · zero runtime dependencies, typed, MIT.
- **Golden corpus — 10 real, primary-sourced matters of record:** Tango Card (OFAC 2022) · MoneyGram (OFAC 2021) · CoinList (OFAC 2023) · TD Bank (FinCEN 2024) · USAA FSB (FinCEN 2022) · Paxful (FinCEN 2025) · Block/Cash App (CFPB 2025) · OFAC Instant-Payment guidance (2022) · Synapse/Evolve (Bankr. + Fed 2024) · Coinbase (NYDFS 2023).

## Read me first

1. **The test that carries the thesis** — `tests/adversarial/` (AL-PROBE-06, the irreversibility gate) and the OFAC screen test. Each rule is a runnable, falsifiable check.
2. **[`WORKED_EXAMPLE.md`](WORKED_EXAMPLE.md)** — the full irreversible-rail decision class walked end to end: an agent attempts an autonomous instant-rail payment, the gate refuses promotion, the OFAC screen holds a near-match, and both land on the tamper-evident ledger.
3. **[autonomy-ladder.io](https://autonomy-ladder.io)** — the framework and whitepaper behind all six libraries.

## Install

```bash
pip install -e ".[dev,test-property]"
PYTHONPATH=src python3 examples/instant_rail_promotion_refusal.py
```

---

## Why this exists for frontier autonomy stacks

The controls in this library are **domain-agnostic**. The DEFCON state machine, the non-overridable **sovereign veto** (a separate-process control the agent cannot switch off), the **hash-chain audit ledger** (it detects tampering within its trust boundary), the **hard envelopes with mechanical escalation**, the **sampled-review tripwires**, and **monitor-led promotion** were forged in real multi-agent production systems under consequence — and they apply directly to any high-stakes coordinated autonomy (vehicles, robots, agent swarms) where *invisible promotion* or *cascade failure* is unacceptable. The decision class is a parameter: this repo encodes it for **payments — OFAC screening, Reg E, rail-finality / irreversibility**, but the same A0→A4 deployment-authority structure lifts into any decision class without inheriting financial-services assumptions.

- **Framework + whitepaper:** [autonomy-ladder.io](https://autonomy-ladder.io)
- **Non-financial demo (under 60s):** [`finserv-agent-audit/examples/agent_coordination`](https://github.com/linus10x/finserv-agent-audit/tree/main/examples/agent_coordination) — the same veto / envelope / audit-chain / demotion primitives on a generic agent swarm.

> **For reviewers & safety teams:** every control here is falsifiable — the test suite (183 tests · 98.97% coverage · a real OFAC screening control) turns each rule into a runnable check, and the veto and ledger are infrastructure with operational properties (separate process boundary, distinct credentials, a gate the agent cannot reach; write-once retention). These are reference implementations for adoption, not deployed production controls.


## The worked example, in 10 lines of output

```
=== Post-hoc-veto-only on FedNow ===
granted                = False
irreversibility_refusal = True
  - IRREVERSIBILITY REFUSAL: program 'fednow-payout-bot' moves money on FedNow
    Service (instant credit) (final-by-rule), and its only controls act after
    authorization (['post_hoc_veto']). ...
```

A FedNow instant-payout bot is **refused** A3 promotion — not because autonomy
is forbidden, but because its only control acts *after* an irreversible credit
settles. Add a pre-authorization control and the same program is promotable.
The full walkthrough is in [`WORKED_EXAMPLE.md`](WORKED_EXAMPLE.md); two runnable
scripts ship under [`examples/`](examples/):
[`instant_rail_promotion_refusal.py`](examples/instant_rail_promotion_refusal.py)
(AL-PROBE-06) and [`ofac_screen_and_disposition.py`](examples/ofac_screen_and_disposition.py)
(OFAC screen → human disposition).

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
|:---|:---|:---|
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
pytest tests/adversarial/ -v               # the six AL-PROBES (11 test functions)
PYTHONPATH=src python3 scripts/mutation_pass.py   # surgical mutation pass (manual)

# Runnable examples:
PYTHONPATH=src python3 examples/instant_rail_promotion_refusal.py
PYTHONPATH=src python3 examples/ofac_screen_and_disposition.py
```

As of this build: **183 tests pass at 98.97% coverage.** CI (`ci.yml`) runs the
test + coverage gate, the AL-PROBES, ruff, and `mypy --strict` on Python 3.12 and
3.13. Four assurance tiers back the claims, each a discrete count:

- **Property tier** — a Hypothesis suite generating up to 2,300 cases per run
  (a ceiling, not a floor) across the ledger, finality, gate, veto, and OFAC invariants.
- **Golden-corpus tier** — 10 real, primary-sourced enforcement / litigation /
  incident matters as parametrized fixtures (each carries a primary-source URL).
- **Adversarial tier** — the six AL-PROBES, 11 committed test functions under
  `tests/adversarial/`.
- **Mutation tier** — a surgical pass that kills all 23 targeted mutants of the
  load-bearing invariants. It is an **author audit run manually**
  (`scripts/mutation_pass.py`), not wired into CI.

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

> Patterns extracted from a private quantitative program; the source
> program operates in paper-trading Phase 0 — no live capital has been deployed.
> Reference patterns and characterizations are summaries, not legal advice —
> consult qualified counsel and qualified compliance practitioners.

---

## Part of the Autonomy Ladder™ family

[![Autonomy Ladder family](https://img.shields.io/badge/Autonomy%20Ladder-family%20(6%20libraries)-1b2a4a)](https://github.com/linus10x/autonomy-ladder-libraries)

Six co-equal regulated-vertical reference libraries implementing one framework —
the **Autonomy Ladder** (A0→A4, every rung demotable). They share the same five
governance primitives, the same MIT license, and the same evidence discipline
(zero runtime deps · `mypy --strict` · SHA-pinned CI · golden corpora of real,
primary-sourced enforcement actions). The decision class changes by vertical;
the rungs and controls do not. **Start at the family landing page:
[`autonomy-ladder-libraries`](https://github.com/linus10x/autonomy-ladder-libraries).**
This library's primitives are mapped to A0→A4 in [`AUTONOMY_LADDER.md`](AUTONOMY_LADDER.md).

| Vertical | Library | DOI |
|---|---|---|
| Cross-vertical financial services | [`finserv-agent-audit`](https://github.com/linus10x/finserv-agent-audit) | [10.5281/zenodo.20434570](https://doi.org/10.5281/zenodo.20434570) |
| Banking (model risk · ECOA/Reg B · BSA/AML/OFAC) | [`banking-agent-audit`](https://github.com/linus10x/banking-agent-audit) | [10.5281/zenodo.20564584](https://doi.org/10.5281/zenodo.20564584) |
| Payments (OFAC · Reg E · rail finality) | **[`payments-agent-audit`](https://github.com/linus10x/payments-agent-audit)** | [10.5281/zenodo.20592773](https://doi.org/10.5281/zenodo.20592773) |
| Health-insurance payer (UM · prior auth · appeals) | [`payer-agent-audit`](https://github.com/linus10x/payer-agent-audit) | [10.5281/zenodo.20564377](https://doi.org/10.5281/zenodo.20564377) |
| SEC-registered investment advisers (Advisers Act §206) | [`private-capital-agent-audit`](https://github.com/linus10x/private-capital-agent-audit) | [10.5281/zenodo.20564496](https://doi.org/10.5281/zenodo.20564496) |
| Commercial real estate | [`cre-agent-audit`](https://github.com/linus10x/cre-agent-audit) | [10.5281/zenodo.20437081](https://doi.org/10.5281/zenodo.20437081) |

**Framework + whitepaper:** [autonomy-ladder.io](https://autonomy-ladder.io).
