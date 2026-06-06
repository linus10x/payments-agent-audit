# payments-agent-audit — Primary-Source Research Provenance (2026-06-05)

This file preserves the primary-source research underpinning the reg anchors
(`S3b_payment_regs_proposed.yaml`) and the golden corpus (`tests/golden`).
Every item carries a primary-source URL; PARTIAL/UNVERIFIED items are flagged.
Matters of record only. Confirm CFR verbatim against ecfr.gov before quoting
into published prose (the research pass used the Cornell LII mirror because
ecfr.gov gated automated fetches).

## Regulatory anchors (8)

1. **ofac_sdn** — OFAC SDN List; strict liability. 31 CFR Part 501; IEEPA
   (50 U.S.C. 1701-1706) + TWEA civil-penalty authority. SDN list service:
   https://ofac.treasury.gov/sanctions-list-service ·
   https://www.law.cornell.edu/cfr/text/31/part-501 ·
   https://ofac.treasury.gov/civil-penalties-and-enforcement-information
   (The 21st Century Peace through Strength Act, signed April 24, 2024, extended
   the IEEPA/TWEA civil and criminal statute of limitations from 5 to 10 years —
   50 U.S.C. 1705(d); 50 U.S.C. 4315(d).)
2. **fednow** — FedNow finality. Regulation J, 12 CFR Part 210 Subpart C;
   Operating Circular 8. "Payment through the FedNow Service is final and
   irrevocable when made." https://www.law.cornell.edu/cfr/text/12/part-210/subpart-C ·
   https://www.federalreserve.gov/newsevents/pressreleases/files/other20220519a1.pdf
3. **rtp** — The Clearing House RTP Operating Rules (eff. 2022-06-10). Final and
   irrevocable settlement; sender cannot revoke/recall once submitted.
   https://www.theclearinghouse.org/-/media/new/tch/documents/payment-systems/rtp_operating_rules_effective_06-10-2022.pdf
   (PARTIAL: exact section number of the irrevocability clause not pinned.)
4. **nacha_ach** — Nacha Operating Rules; ACH is NOT instant-final. Reversing
   entry must reach the RDFI within 5 Banking Days of the original Settlement
   Date. https://www.nacha.org/rules/reversals-and-enforcement ·
   https://www.nacha.org/sites/default/files/2021-05/End_User_Briefing_Reversals.pdf
   (PARTIAL: full Rules text paywalled; 5-day window confirmed from Nacha summaries.)
5. **travel_rule** — 31 CFR 1010.410(f). Transmittals ≥ $3,000 must record/pass
   originator+beneficiary info. https://www.law.cornell.edu/cfr/text/31/1010.410
   (The 2020 NPRM's proposed $250 cross-border threshold is PROPOSED ONLY — keep $3,000.)
6. **money_transmitter** — FinCEN MSB registration 31 CFR 1022; CSBS Model Money
   Transmission Modernization Act (state licensing). https://www.fincen.gov/fact-sheet-msb-registration-rule ·
   https://www.csbs.org/csbs-money-transmission-modernization-act-mtma
7. **baas_sponsor_bank** — Interagency Guidance on Third-Party Relationships:
   Risk Management (June 6, 2023): OCC Bulletin 2023-17 / FDIC FIL-29-2023 /
   Fed SR 23-4. https://www.federalregister.gov/documents/2023/06/09/2023-12340/ ·
   https://www.occ.gov/news-issuances/bulletins/2023/bulletin-2023-17.html ·
   https://www.federalreserve.gov/supervisionreg/srletters/sr2304.htm
8. **sar_timeliness** — 31 CFR 1020.320(b)(3). File within 30 calendar days of
   initial detection; +30 (max 60) if no suspect identified.
   https://www.law.cornell.edu/cfr/text/31/1020.320

## Golden corpus (matters of record, primary-sourced)

- **OFAC penalties:** Tango Card $116,048.60 (2022-09-30, IP-screening failure,
  stored-value) https://ofac.treasury.gov/recent-actions/20220930_33 ·
  MoneyGram $34,328.78 (2021-04-29) https://ofac.treasury.gov/recent-actions/20210429 ·
  CoinList $1,207,830 (2023-12-13) https://ofac.treasury.gov/media/932406/download ·
  OFAC "Sanctions Compliance Guidance for Instant Payment Systems" (guidance)
  https://ofac.treasury.gov/system/files/126/instant_payment_systems_compliance_guidance_brochure.pdf
- **FinCEN BSA/AML/SAR:** TD Bank $1.3B FinCEN Consent Order 2024-02 (2024-10-10)
  https://www.fincen.gov/news/news-releases/fincen-assesses-record-13-billion-penalty-against-td-bank ·
  Paxful $3.5M (2025-08-12, MSB-registration + SAR failures)
  https://www.fincen.gov/news/news-releases/fincen-assesses-35-million-penalty-against-paxful-facilitating-suspicious ·
  USAA FSB $80M (2023-04) https://www.fincen.gov/system/files?file=enforcement_action/2023-04-05/USAA_Consent_Order_Final_508_2.pdf
- **Reg E / EFTA (CFPB):** Block/Cash App $175M (2025)
  https://www.consumerfinance.gov/about-us/newsroom/cfpb-orders-operator-of-cash-app-to-pay-175-million-and-fix-its-failures-on-fraud/
  (PARTIAL: pull consent-order number from CFPB enforcement index before final cite.)
- **Instant-rail finality/fraud:** OFAC instant-payments guidance (above). NOTE:
  no U.S. *regulator enforcement* action found keyed specifically to FedNow/RTP
  irrevocable APP fraud; APP-loss dollar figures circulating are press/industry —
  UNVERIFIED at the regulator level. Use the irrevocability RULES as the anchor.
- **BaaS failures:** In re Synapse Financial Technologies, Ch. 11 filed 2024-04-22
  (Bankr. C.D. Cal.) — PARTIAL: pin docket on CourtListener/PACER before final cite ·
  Evolve Bank & Trust — Fed C&D consent (2024-06-14), third-party/AML/OFAC deficiencies
  https://www.federalreserve.gov/newsevents/pressreleases/enforcement20240614a.htm
- **Money-transmitter:** Coinbase NYDFS consent $50M penalty + $50M remediation
  (2023-01-04, TM/transaction-monitoring backlog) https://www.dfs.ny.gov/reports_and_publications/press_releases/pr202301041 ·
  Coinme CA DFPI consent (2025-06) https://dfpi.ca.gov/wp-content/uploads/2025/06/Consent-Order-Coinme-Inc.pdf
