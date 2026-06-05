# DOI Plan

This repository is built to be DOI-archived on Zenodo as a citable research
artifact, mirroring the `finserv-agent-audit` and `cre-agent-audit` anchors. Own
DOI = the Payments vertical becomes a Day-1 funnel-claimable "backed" vertical.

**Status: STAGED — NOT YET MINTED. Owner gate.** No GitHub remote, no tag, no
Zenodo archive without explicit owner sign-off.

## Sequence (owner-executed, after sign-off)

1. **Create the remote** `linus10x/payments-agent-audit` (public, MIT).
2. **Enable the GitHub–Zenodo webhook** for the repository (Zenodo > GitHub > flip
   the toggle on).
3. **Final pre-publish gate** — confirm `pytest --cov-fail-under=90` green, the six
   AL-PROBES green, ruff + mypy --strict clean, and the council 10/10 record on the
   public prose (README/CITATION/docs).
4. **Tag `v0.1.0`** and publish a GitHub Release. The webhook mints a
   version-specific DOI and a concept DOI.
5. **Backfill DOIs** — write the concept DOI into `CITATION.cff` (`doi:` field) and
   the README badge, then commit as `v0.1.1` (docs-only).
6. **Reg-anchor merge** — the owner merges `S3b_payment_regs_proposed.yaml` into the
   canonical SSOT after counsel review, resolving the flagged open items.
7. **Claim flip** — per `S3b_payments_SHIPPED_note.md`, the owner / S2 flips the
   funnel's Payments label from `cross-applied` to `backed` and updates the §1 Claim
   Sheet OFAC entry to reflect the now-implemented control. This stream does not edit
   the funnel or the Claim Sheet.

## SemVer

`0.1.0` is the initial public minor. A default/observable-contract change (e.g.
flipping a mode default) would be a MAJOR bump; new controls are MINOR; doc/DOI
backfill is PATCH. Never re-tag a published DOI'd version.
