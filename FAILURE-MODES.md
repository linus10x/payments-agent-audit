# Failure Modes

What this library defends against, what it does not, and where the honest edges
are. Extending this file (and `LIMITATIONS.md`) is part of the discipline — the
claim layer must match implemented reality.

## Defended (with a test that proves it)

| Failure mode | Defense | Test |
|---|---|---|
| Promote an agent past unmet controls | Attestation-gated promotion; production requires independent attestation | AL-PROBE-01 |
| Agent clears its own veto | Self-clear hard-blocked, always | AL-PROBE-02 |
| Forged operator identity on a veto clear | Production requires an authenticated principal (no free strings) | AL-PROBE-02 |
| In-place tamper of a ledger entry | `event_hash` recompute on verify and on JSONL load | AL-PROBE-03 |
| End-to-end chain regeneration | Deployer-keyed genesis + external witness anchor (head divergence) | AL-PROBE-03 |
| Clean hardened chain falsely flagged | Branched genesis seed in verify | AL-PROBE-03 |
| Snap HALT→NORMAL in one call | Transition-direction guard | AL-PROBE-04 |
| Model owner self-challenges to a clean pass | Reject `challenger is primary`; independence attestation | AL-PROBE-05 |
| Autonomous irreversible-rail payout on post-hoc veto alone | Irreversibility promotion gate | AL-PROBE-06 |
| Auto-clear an OFAC hit by the agent | Self-disposition forbidden; human disposition required | `test_ofac_screening` |
| Name reordering / accents evading sanctions match | Token-sort + Jaccard + sequence-ratio fuzzy match | `test_ofac_screening` |
| Late SAR filing slipping through | 30/60-day deadline computation | golden corpus (TD Bank) |
| Reg E extension without provisional credit | Provisional-credit requirement | golden corpus (Cash App) |
| Sanctions-feed outage with money still moving | DEFCON forces HALT on feed outage | `test_defcon` |
| Ambiguous BaaS ledger ownership | Sponsor-bank oversight non-attestable | golden corpus (Synapse/Evolve) |

## Not defended (out of scope — by design)

- **Reasoning-layer prompt injection.** This library governs the *actions* an
  agent takes (the gates and the ledger), not the LLM's internal reasoning. A
  model that is socially engineered into proposing a bad action is still subject
  to the gates, but the library does not defend the reasoning layer itself.
- **A compromised host.** The internally-consistent chain detects tampering by an
  *honest* holder of the head. A storage-layer attacker who also controls the
  witness register can defeat it — which is why the witness register must be one
  the deployer does not control alone, and why production mode mandates it.
- **A malicious deployer.** The library assumes the deploying institution wants to
  be governed. It raises the cost of an undetected violation; it is not an
  adversary to its own operator.
- **List quality.** Screening is only as good as the wired sanctions list and the
  configured threshold. The library does not curate or validate the list.
- **Calibration.** DEFCON thresholds, the screening threshold, and the autonomy
  envelopes are illustrative; calibration is the deployer's compliance function's
  responsibility.
