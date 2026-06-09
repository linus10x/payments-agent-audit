# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/) and the project adheres to
[Semantic Versioning](https://semver.org/).

## [0.1.1] — 2026-06-09

### Added

- **Zenodo archival.** The release is archived on Zenodo — concept DOI
  [`10.5281/zenodo.20592773`](https://doi.org/10.5281/zenodo.20592773), which always
  resolves to the latest version.
- **`examples/`** — two runnable walkthroughs (an AL-PROBE-06 instant-rail
  promotion refusal, and an OFAC screen → human disposition flow), referenced
  from the README quickstart. The `examples/*` ruff config now governs real code.

### Changed

- **README pass** — added a buyer-first hook, a 30-second quickstart, a full
  badge row (CI · coverage · tests · license · Python · DOI), a one-line proof
  strip, and the six-library Autonomy Ladder™ family block.
- **`pyproject.toml`** version `0.1.0` → `0.1.1` (all other surfaces already
  read 0.1.1).

## [0.1.0] — 2026-06-06

Initial public release. Reference governance patterns for autonomous AI agents in
regulated payments. Public remote + `v0.1.0` tag + GitHub Release are live; the
Zenodo DOI is pending the GitHub–Zenodo integration toggle.

### Added — five corrected primitives

- **Level-gate (A0→A4)** with an irreversibility promotion gate and (in production
  mode) independent attestation of promotion criteria, not caller-asserted booleans.
- **Sovereign veto** with a fail-closed production mode (refuses to start without a
  wired `Authorizer`) and operator identity bound to an authenticated principal.
- **Hash-chain audit ledger** with a branched genesis seed so hardened and legacy
  chains both verify; in-place tamper and end-to-end regeneration both detected.
- **DEFCON risk-state machine** with a transition-direction guard (no one-call
  HALT→NORMAL).
- **Effective-challenge harness** that rejects a self-challenge and records an
  independence attestation; a non-independent challenger cannot reach `accept_primary`.

### Added — payments controls

- **OFAC sanctions screening** — implemented fuzzy match (token-sort + Jaccard +
  sequence ratio) and a strict-liability hit-disposition workflow against a
  pluggable list; **no list bundled**.
- **BSA/AML SAR** — 30/60-day timeliness, the Travel Rule ($3,000 threshold), and a
  vague-rationale gate on alert disposition.
- **Regulation E** error resolution (10 / 45 / 90-day windows; provisional credit).
- **Rail-finality / irreversibility** classification (FedNow/RTP/Fedwire irrevocable;
  ACH return-window; card chargeback) feeding the AL-PROBE-06 gate.
- **Sponsor-bank / BaaS oversight** (regulated-entity-of-record; ledger-ownership
  ambiguity = the Synapse failure mode).
- **Retention** — a five-year BSA floor (31 CFR 1010.430(d)), not a 90-day default.

### Added — assurance

- The six AL-PROBES (AL-PROBE-01..05 + the new AL-PROBE-06) as committed adversarial
  tests — 11 test functions in total (AL-PROBE-03 carries three sub-tests and
  AL-PROBE-06 carries four; the rest are one each).
- ~2,300 property-based cases per run; a primary-sourced golden corpus of real
  enforcement matters; a surgical mutation pass over the load-bearing invariants
  (100% kill on the targeted set).
- 183 tests, 98.97% coverage (`--cov-fail-under=90`), ruff + mypy --strict clean.

[0.1.1]: https://github.com/linus10x/payments-agent-audit/releases/tag/v0.1.1
[0.1.0]: https://github.com/linus10x/payments-agent-audit/releases/tag/v0.1.0
