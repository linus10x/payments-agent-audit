#!/usr/bin/env python3
"""Surgical mutation pass over the load-bearing corrected-spec invariants.

mutmut 3.5 does not run cleanly in this no-install / Python 3.14 environment,
so this is a focused, deterministic mutation harness: it applies each mutant to
the source, runs the relevant fast tests, and records whether the suite KILLS
the mutant (tests fail) or it SURVIVES (tests pass — a weak assertion).

Scope cap (logged honestly): this targets the highest-value invariant lines of
the five corrected primitives + the payments controls — NOT every line of the
codebase. A surviving mutant means the suite would not have caught that
regression and the assertion must be strengthened. Run:

    PYTHONPATH=src python3 scripts/mutation_pass.py
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "payments_agent_audit" / "governance"

# Fast, deterministic test subset that exercises the invariants (skip the slow
# hypothesis property tier for per-mutant speed; the probes + unit tests pin the
# same invariants).
TEST_CMD = [
    sys.executable,
    "-m",
    "pytest",
    "-x",
    "-q",
    "-p",
    "no:cacheprovider",
    "tests/",
    "--ignore=tests/property",
]


@dataclass
class Mutant:
    file: str
    old: str
    new: str
    desc: str


MUTANTS: list[Mutant] = [
    # --- audit_chain (P3 genesis-seed branch + tamper + prod guard) ---
    Mutant("audit_chain.py", "if event.prev_hash != prev:", "if event.prev_hash == prev:",
           "verify(): flip prev_hash link check"),
    Mutant("audit_chain.py", "if event.event_hash != event._compute_hash():",
           "if event.event_hash == event._compute_hash():",
           "verify(): flip event_hash recompute check"),
    Mutant("audit_chain.py", 'if mode == "production" and witness_register is None:',
           'if mode == "production" and witness_register is not None:',
           "production-mode witness guard inverted"),
    Mutant("audit_chain.py", "and event.payload.get(\"genesis_version\") == GENESIS_VERSION",
           "and event.payload.get(\"genesis_version\") != GENESIS_VERSION",
           "_is_hardened_genesis: invert genesis-version check"),
    # --- sovereign_veto (P2 self-clear + prod guard + auth) ---
    Mutant("sovereign_veto.py", "if resolved_operator == self.agent_id:",
           "if resolved_operator != self.agent_id:", "self-clear rule inverted"),
    Mutant("sovereign_veto.py", 'if mode == "production" and authorizer is None:',
           'if mode == "production" and authorizer is not None:',
           "veto production-mode authorizer guard inverted"),
    Mutant("sovereign_veto.py", "if not principal:", "if principal:",
           "veto: accept failed authentication"),
    # --- autonomy_ladder (AL-PROBE-06 irreversibility + P1) ---
    Mutant("autonomy_ladder.py",
           "if is_irreversible(request.rail_id) and not self._has_effective_pre_auth(request):",
           "if is_irreversible(request.rail_id) or not self._has_effective_pre_auth(request):",
           "irreversibility gate: and -> or"),
    Mutant("autonomy_ladder.py", "return len(self.pre_auth_controls) == 0",
           "return len(self.pre_auth_controls) != 0", "only_post_hoc inverted"),
    Mutant("autonomy_ladder.py", "elif not att.is_independent:",
           "elif att.is_independent:", "P1 independence check inverted"),
    # D1 regression — the pre-auth-effective attestation requirement
    Mutant("autonomy_ladder.py",
           "return att is not None and att.satisfied and att.is_independent",
           "return att is not None and att.satisfied",
           "D1: drop pre-auth independence requirement"),
    Mutant("autonomy_ladder.py",
           "if request.only_post_hoc:\n            return False",
           "if request.only_post_hoc:\n            return True",
           "D1: only_post_hoc no longer blocks pre-auth unblock"),
    # --- effective_challenge (P5 self-challenge + downgrade) ---
    Mutant("effective_challenge_harness.py", "if challenger_model is primary_model:",
           "if challenger_model is not primary_model:", "self-challenge guard inverted"),
    Mutant("effective_challenge_harness.py",
           'if base_reco == "accept_primary" and not self.independence.is_independent:',
           'if base_reco == "accept_primary" and self.independence.is_independent:',
           "P5 independence downgrade inverted"),
    # --- defcon (P4 transition-direction guard + HALT stickiness) ---
    Mutant("defcon.py", "if de_escalating and target.value != from_level.value - 1:",
           "if de_escalating and target.value == from_level.value - 1:",
           "de-escalation adjacency guard inverted"),
    Mutant("defcon.py", "if self._current_level == DEFCON.HALT:\n            logger.warning",
           "if self._current_level != DEFCON.HALT:\n            logger.warning",
           "evaluate(): HALT auto-deescalation block inverted"),
    # --- ofac_screening (strict-liability) ---
    Mutant("ofac_screening.py", "if operator_id == self.agent_id:",
           "if operator_id != self.agent_id:", "OFAC self-disposition rule inverted"),
    Mutant("ofac_screening.py", "if best_score >= self.review_threshold:",
           "if best_score > self.review_threshold:", "OFAC threshold boundary weakened"),
    # --- sar_workflow (timeliness + travel rule) ---
    Mutant("sar_workflow.py", "meets = proposed_filing_date <= deadline",
           "meets = proposed_filing_date < deadline", "SAR deadline boundary weakened"),
    Mutant("sar_workflow.py", "in_scope = amount_usd >= TRAVEL_RULE_THRESHOLD_USD",
           "in_scope = amount_usd > TRAVEL_RULE_THRESHOLD_USD",
           "Travel Rule threshold boundary weakened"),
    # --- reg_e (provisional credit + D2 new-account window) ---
    Mutant("reg_e.py", "if not provisional_credit_given:",
           "if provisional_credit_given:", "Reg E provisional-credit check inverted"),
    Mutant("reg_e.py", "initial_days = NEW_ACCOUNT_INITIAL_BUSINESS_DAYS",
           "initial_days = INITIAL_INVESTIGATION_BUSINESS_DAYS",
           "D2: new-account initial window reverted to 10 days"),
    # --- rail_finality ---
    Mutant("rail_finality.py", "return self.finality is Finality.IRREVOCABLE",
           "return self.finality is not Finality.IRREVOCABLE",
           "rail irreversibility classification inverted"),
]


def _invalidate_bytecode() -> None:
    """Delete cached bytecode so a same-length mutant (e.g. ``==`` -> ``!=``)
    written within one mtime tick cannot leave a stale ``.pyc`` in play."""
    for pyc in ROOT.rglob("*.pyc"):
        pyc.unlink(missing_ok=True)
    for cache in ROOT.rglob("__pycache__"):
        for f in cache.glob("*"):
            f.unlink(missing_ok=True)


def run_tests() -> bool:
    """Return True if the suite PASSES (mutant survived)."""
    _invalidate_bytecode()
    result = subprocess.run(TEST_CMD, cwd=ROOT, capture_output=True, text=True)
    return result.returncode == 0


def main() -> int:
    killed, survived = 0, 0
    survivors: list[str] = []
    for m in MUTANTS:
        path = SRC / m.file
        original = path.read_text()
        if m.old not in original:
            print(f"SKIP (anchor not found): {m.file} :: {m.desc}")
            continue
        mutated = original.replace(m.old, m.new, 1)
        path.write_text(mutated)
        try:
            passed = run_tests()
        finally:
            path.write_text(original)  # always restore
        if passed:
            survived += 1
            survivors.append(f"{m.file} :: {m.desc}")
            print(f"SURVIVED  {m.file} :: {m.desc}")
        else:
            killed += 1
            print(f"killed    {m.file} :: {m.desc}")

    total = killed + survived
    score = (killed / total * 100) if total else 0.0
    print("\n" + "=" * 60)
    print(f"Mutation score: {killed}/{total} killed = {score:.1f}%")
    if survivors:
        print("SURVIVORS (strengthen assertions):")
        for s in survivors:
            print(f"  - {s}")
    return 0 if survived == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
