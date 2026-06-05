# Architecture

`payments-agent-audit` is a zero-dependency, stdlib-only Python library. It has
two planes and a set of pluggable Protocol seams.

## Two planes

- **Control plane** — the governance gates an autonomous payment agent calls
  before it acts: the autonomy-ladder promotion gate, the sovereign veto, the
  DEFCON state machine, the effective-challenge harness, and the payments
  controls (OFAC screening, SAR/Travel Rule, Reg E, sponsor-bank oversight,
  rail-finality classification).
- **Audit plane** — the hash-chain ledger every gate writes to. Each governance
  decision (a screen, a disposition, a promotion refusal, a DEFCON transition)
  is appended as a hash-chained `AuditEvent`, so the record of what the agent did
  is itself tamper-detectable.

The canonical event schema (`schemas/audit_event.py`) is the boundary between the
two planes: a frozen, hashed `AuditEvent` with a payments-specific event-type
vocabulary.

## Protocol seams (deployer integration points)

The chain does not own its dependencies; it consumes interfaces so a deployer can
swap implementations without forking:

- **`LedgerStore`** (`ledger_store.py`) — pluggable storage. `InMemoryLedgerStore`
  and `JsonlLedgerStore` ship; a WORM/SEC-17a-4 store is a deployer integration.
- **`TimestampSource`** (`timestamp_source.py`) — `LocalClock` ships; an RFC 3161
  TSA source is the deployer's to wire when a trusted time anchor is required.
- **`WitnessRegister`** (`witness_anchor.py`) — the external anchor
  (OpenTimestamps, Sigstore Rekor, a regulator log) that converts the
  internally-consistent chain into an adversarially tamper-evident record.
- **`SanctionsListProvider`** (`ofac_screening.py`) — the OFAC SDN/consolidated
  list source. **No list is bundled**; the deployer wires a live feed.
- **`Authorizer`** (`sovereign_veto.py`) — authenticates a credential to a
  principal (IdP/KMS) and authorizes privileged operations.

## Modes: advisory vs. production

Every gate that depends on an external trust root distinguishes two modes:

- **advisory** (the default) — backward-compatible, labeled advisory in code and
  docs. Operator identity is a caller assertion; the witness register is optional.
- **production** — fail-closed. The sovereign veto and the DEFCON machine refuse
  to start without a wired `Authorizer`; the audit chain refuses to start without
  a `WitnessRegister`; the autonomy-ladder gate refuses to start without a wired
  chain to record refusals. Adding the strict mode is opt-in and does not change
  the advisory default (no breaking change).

## The genesis-seed branch (audit chain)

A chain may be *hardened* (a deployer-keyed genesis event #0 whose `prev_hash` is
`SHA-256(domain/deployer_id/creation_iso)`) or *legacy* (no genesis event; the
first real event seeds from the all-zeroes `"0"*64` value). `verify()` /
`verify_strict()` **branch the genesis seed** on which kind of chain they are
walking — recomputing the deployer-keyed seed from the genesis event's own payload
when present, and falling back to the all-zeroes value otherwise. Both kinds
verify True. The deployer-keyed
seed plus an external witness anchor is what makes end-to-end regeneration
detectable: an attacker can rebuild a self-consistent chain, but its head will not
match the witnessed head, and it cannot reproduce the legitimate deployer's
genesis identity.

## Data flow (a FedNow payout decision)

```
agent wants to send a FedNow credit
   │
   ├─▶ OFACScreener.screen(beneficiary)   ── potential match? HOLD (sovereign veto)
   │                                          │ human disposition (authenticated)
   ├─▶ AutonomyLadderGate.evaluate(...)    ── irreversible rail + post-hoc only? REFUSE
   │                                          │ recorded: IRREVERSIBLE_PROMOTION_REFUSED
   ├─▶ DEFCONMachine.evaluate(metrics)     ── sanctions feed down / fraud spike? HALT
   │
   └─▶ every step appends to AuditChain ──▶ periodically anchored to WitnessRegister
```
