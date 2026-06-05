# Assurance Guide

How a second-line model-risk function or a third-line auditor reads this library
as evidence, and how the AL-PROBES map to the assurance questions an examiner
asks.

## The AL-PROBES

The probes are committed adversarial tests (`tests/adversarial/test_al_probes.py`)
that reconstruct the exact failing construction each corrected primitive defends
against, so a PASS is reproducible and reviewable.

| Probe | Assurance question | Pass condition |
|---|---|---|
| AL-PROBE-01 | Can a program be promoted past unmet lower-level controls? | Promotion **refused** when attestations are missing |
| AL-PROBE-02 | Can an agent clear its own veto, or can anyone assert operator identity? | Self-clear **blocked**; only an **authenticated principal** clears |
| AL-PROBE-03 | Does a clean hardened chain falsely flag, and is tampering caught? | Hardened chain verifies True; in-place tamper **and** regeneration detected; legacy chain still verifies |
| AL-PROBE-04 | Can the system snap from HALT back to NORMAL in one call? | Automatic de-escalation out of HALT **blocked**; one-shot HALT→NORMAL **rejected** |
| AL-PROBE-05 | Can a model owner self-challenge to a clean pass? | `challenger is primary` **rejected**; non-independent challenger cannot reach `accept_primary` |
| **AL-PROBE-06** | Can an irreversible-rail program run autonomously on a post-hoc veto alone? | Instant-rail + post-hoc-only promotion **refused** and recorded; pre-auth control unblocks; ACH modeled non-final |

## Test pyramid (what backs each claim)

- **Unit + contract** — every primitive, control, and obligation entry has direct
  tests; public APIs are pinned. (`tests/test_*.py`)
- **Property-based** (`tests/property/`) — ~2,300 generated cases per run across
  ledger append/verify/tamper invariants, the irreversibility algebra, DEFCON
  transition-direction algebra, veto un-self-clearability, and OFAC exact-match.
- **Golden corpus** (`tests/golden/`) — real, primary-sourced enforcement /
  litigation / incident matters turned into parametrized fixtures asserting how
  the controls would have flagged or governed each. Every fixture carries a
  primary-source URL or is marked unverified. Matters of record only.
- **Adversarial** (`tests/adversarial/`) — the six AL-PROBES.
- **Mutation** (`scripts/mutation_pass.py`) — a surgical mutation pass over the
  load-bearing invariants; a surviving mutant means an assertion is too weak.
- **Coverage gate** — `--cov-fail-under=90` is a floor, not a ceiling.

## Regulatory mapping (controls → authority)

| Control | Authority |
|---|---|
| OFAC screening | OFAC SDN/consolidated lists; 31 CFR Part 501; IEEPA |
| SAR timeliness | 31 CFR 1020.320(b)(3) (30/60-day filing) |
| Travel Rule | 31 CFR 1010.410(f) ($3,000 threshold) |
| Reg E error resolution | 12 CFR 1005.11 (10-day / 45-day / 90-day) |
| Rail finality | FedNow Reg J (12 CFR Part 210 Subpart C); RTP Operating Rules; Nacha Operating Rules |
| Sponsor-bank oversight | Interagency Guidance on Third-Party Relationships (June 2023) |
| Retention floor | 31 CFR 1010.430(d) (five years) |
| Effective challenge | SR 11-7 model risk management (effective challenge) |

Confirm each citation against the cited primary source before relying on it. The
obligation content is buyer-facing and is reference IP, not legal advice.
