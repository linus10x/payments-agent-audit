# Limitations

Known boundaries. Read alongside `FAILURE-MODES.md`. The claim layer matches
implemented reality; nothing here is overclaimed.

- **Reference IP, not a production control.** The primitives are tested reference
  patterns, not a deployed control operating inside a production payments stack
  wrapped in an organizational assurance apparatus. Use them as a starting point
  for adoption, never as "a control already operating in production."
- **Not legal advice.** Statutory and CFR characterizations are summaries.
  Sanctions screening calibration, SAR disposition, Reg E adjudication, and
  money-transmitter / BaaS structuring are the deploying institution's compliance
  and legal functions' responsibility. Confirm every citation against the cited
  primary source.
- **No sanctions list is bundled.** `OFACScreener` runs against a pluggable
  `SanctionsListProvider`. The OFAC SDN/consolidated list changes constantly;
  shipping a copy would be worse than shipping none. The deployer wires a live
  feed and owns its freshness.
- **Fuzzy matching is a recall tool, not an adjudicator.** It surfaces candidates
  for human disposition; it does not decide identity. Thresholds err toward
  over-flagging (strict liability) and must be tuned to the deployer's tolerance.
- **Within-trust-boundary ledger.** The hash-chain detects tampering by an honest
  holder of the head. Adversarial tamper-evidence requires the external
  `WitnessRegister`, which is a deployer integration (mandatory in production mode).
- **Illustrative thresholds.** DEFCON fraud/loss bands, the screening threshold,
  and the retention floor are examples or floors. Calibrate to your rails, volumes,
  risk appetite, and the longest applicable obligation.
- **Business-day approximations.** The Reg E gate approximates the 10 *business*-day
  window as calendar days and does not own a banking-holiday calendar; it flags the
  requirement, the deployer applies their calendar.
- **Reg-anchor verification.** Some staged anchors carry open items (e.g. the exact
  RTP irrevocability section number; the Nacha rule number behind the 5-banking-day
  reversal window). These are flagged for counsel and are not authored from memory.
- **Single-host concurrency.** The chain serializes appends within a process and,
  for the JSONL store, across processes on one host via `flock`. Distributed
  multi-writer deployments need a store that provides the equivalent guarantee.
