# The Autonomy Ladder, mapped to this library

`payments-agent-audit` is one of six co-equal libraries in the
[**Autonomy Ladder™ family**](https://github.com/linus10x/autonomy-ladder-libraries).
Every library encodes the same five rungs of *deployment authority* and the same
governance primitives — the **decision class** changes by vertical, the rungs and
the climbing rule do not. The framework and whitepaper live at
[autonomy-ladder.io](https://autonomy-ladder.io).

This document maps the framework to the concrete primitives in *this* repository.

## The five rungs (A0 → A4)

```
A4  Production Autonomous   ── writes across coordinating agents; monitor-led promotion + validated escalation
A3  Supervised Autonomous   ── writes one decision class autonomously; non-overridable sovereign veto + live ledger
A2  Delegated               ── writes inside a hard, mechanically-enforced envelope; sampled review
A1  Assisted                ── drafts; a human approves every write
A0  Informational           ── reads & recommends; no write authority
        ▲ climb one rung at a time, only on evidence ·  ▼ demote the moment assurance degrades (routine, not crisis)
```

Source of truth in code: `AutonomyTier` in
`src/payments_agent_audit/governance/autonomy_ladder.py`
(`A0_INFORMATIONAL` → `A4_PRODUCTION_AUTONOMOUS`).

## How this library's primitives realize each rung

| Primitive (this repo) | Module | Realizes |
|---|---|---|
| **Level-gate (A0→A4) + irreversibility refusal** | `autonomy_ladder.py` | The climbing rule itself. Refuses promotion when a lower-rung control is unmet, and in production mode requires **independent attestation** (2nd-line MRM / 3rd-line audit) per criterion rather than caller-asserted booleans. |
| **Rail-finality gate — AL-PROBE-06** | `rail_finality.py` + the gate | The payments-specific climbing constraint: an irreversible-write program (FedNow / RTP, final-by-rule) cannot reach **A3/A4** on a post-hoc control alone; promotion requires an *attested pre-authorization* control. ACH is modeled non-final and exempt. |
| **Sovereign veto** | `sovereign_veto.py` | The non-overridable stop that makes **A3** legible: a separate-process control the agent cannot switch off; in production mode a wired `Authorizer` is mandatory and the clearing operator is an **authenticated principal**, never a free string. An agent cannot clear its own veto. |
| **Hash-chain audit ledger** | `audit_chain.py` | The live, tamper-evident record that **A3/A4** require: branched genesis seed, in-place-tamper and end-to-end-regeneration detection (the latter via a mandatory external witness anchor in production mode). Every promotion, refusal, screen, and disposition is recorded. |
| **DEFCON risk-state machine** | `defcon.py` | Mechanical **demotion**: a transition-direction guard so the automatic path cannot de-escalate out of HALT, and a manual override out of HALT steps only to the adjacent level — a recovering program climbs back through review states, it does not snap fully open. |
| **Real OFAC screening control** | `ofac_screening.py` | A decision-class write gate under strict liability: a potential match is **HELD** (the payment must not proceed) and only an authenticated human may disposition it. This is the control that keeps an autonomous payments agent honest at A2+ — it cannot self-clear a hit. |
| **Effective-challenge harness** | `effective_challenge_harness.py` | The independence discipline behind promotion evidence: rejects a self-challenge and records who chose the challenger and whether it shares owner / vendor family / prompt template — so an attestation reflects a genuine second opinion. |

## The climbing rule, concretely

- **Up one rung, only on evidence.** Promotion to A3/A4 in production mode demands
  independent attestation of every lower-rung criterion *and* — for an irreversible
  rail — an attested pre-authorization control (AL-PROBE-06).
- **Down the moment assurance degrades.** Demotion is routine, mechanical, and
  direction-guarded (DEFCON); it does not wait for a crisis or a human's nerve.

For the runnable proof of the climbing rule on an instant rail, see
[`WORKED_EXAMPLE.md`](WORKED_EXAMPLE.md) and
[`examples/instant_rail_promotion_refusal.py`](examples/instant_rail_promotion_refusal.py).
