# DOI Plan

This repository is built to be DOI-archived on Zenodo as a citable research
artifact, mirroring the `finserv-agent-audit` and `cre-agent-audit` anchors. A DOI
anchors the Payments vertical as a published, citable library alongside the
sibling repos.

**Status: STAGED — NOT YET MINTED. Owner gate.** No GitHub remote, no tag, no
Zenodo archive without explicit owner sign-off.

## Sequence (owner-executed, after sign-off)

1. **Create the remote** `linus10x/payments-agent-audit` (public, MIT).
2. **Enable the GitHub–Zenodo webhook** at
   `https://zenodo.org/account/settings/github/` (logged in as the account that
   holds the sibling DOIs) — flip the repository toggle on.
3. **Final pre-publish gate** — confirm `pytest --cov-fail-under=90` green, the six
   AL-PROBES green, `ruff` + `mypy --strict` clean, and the council 10/10 record on
   the public prose (README / CITATION / docs).
4. **Tag `v0.1.0`** and publish a GitHub Release. The webhook mints a
   version-specific DOI and a concept DOI.
5. **Backfill DOIs** — write the concept DOI into `CITATION.cff` (`doi:` field) and
   the README badge, then commit as `v0.1.1` (docs-only).
6. **Regulatory-anchor merge** — merge the staged payment reg anchors into the
   maintainer's canonical anchor list after counsel review, resolving the flagged
   open items.
7. **Claim reconciliation** — once the library is public + archived, update any
   maintainer-side surface that previously framed Payments as not-yet-backed (or
   OFAC screening as not-yet-implemented) to reflect this published library.

   *(These last two are maintainer-side reconciliation steps; they are not part of
   this repository.)*

## SemVer

`0.1.0` is the initial public minor.

- **MAJOR** — a default/observable-contract change (e.g. flipping a mode default).
- **MINOR** — new controls or primitives.
- **PATCH** — docs / DOI backfill.

Never re-tag a published DOI'd version; bump from the live tag.
