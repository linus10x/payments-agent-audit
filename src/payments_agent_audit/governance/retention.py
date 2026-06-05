"""Record-retention floors for payments governance artifacts.

The BSA requires covered records be retained for **five years** (31 CFR
1010.430(d)) — a payments governance ledger must reflect that floor, NOT a
generic 90-day log-rotation default. SAR records and supporting documentation
carry the same five-year floor (31 CFR 1020.320(d)). Reg E requires evidence
of compliance for two years (12 CFR 1005.13(b)); the BSA floor dominates for
the audit chain. PCI DSS 4.0.1 sets a one-year log-retention minimum with
three months immediately available — again dominated by the BSA floor.

These are floors. Calibrate up to the longest applicable obligation; confirm
the exact rule text against the staged primary-source anchors before relying
on a number. Authored from the staged anchors, not from memory.
"""

from __future__ import annotations

from datetime import timedelta

# 31 CFR 1010.430(d) — BSA general record retention.
BSA_RECORD_RETENTION = timedelta(days=5 * 365)
# 31 CFR 1020.320(d) — SAR + supporting documentation retention.
SAR_RECORD_RETENTION = timedelta(days=5 * 365)
# 12 CFR 1005.13(b) — Reg E compliance evidence.
REG_E_RETENTION = timedelta(days=2 * 365)

# The governing floor for the payments audit chain.
AUDIT_CHAIN_RETENTION_FLOOR = BSA_RECORD_RETENTION


def meets_retention_floor(
    configured: timedelta, floor: timedelta = AUDIT_CHAIN_RETENTION_FLOOR
) -> bool:
    """True when a configured retention period meets the governing floor."""
    return configured >= floor


__all__ = [
    "AUDIT_CHAIN_RETENTION_FLOOR",
    "BSA_RECORD_RETENTION",
    "REG_E_RETENTION",
    "SAR_RECORD_RETENTION",
    "meets_retention_floor",
]
