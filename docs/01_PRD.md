# PropertyFish PRD (v0.1)

## Goal
Plain-English chat that returns a complete, cited, NYC **commercial** property dossier (Manhattan, Brooklyn, Queens) on one page.

## Target Users
NYC commercial brokers, investors, analysts, appraisers (solo/boutique).

## Must-have (MVP)
- Address/owner text → **BBL resolver**.
- Property summary (PLUTO/MapPLUTO).
- Zoning base + overlays (ZoLa/DCP).
- Recorded docs (deeds/mortgages, ACRIS).
- Permits/violations (DOB).
- Parcel map + overlays.
- Chat answers **with citations**. No predictions.

## Out of scope (MVP)
Residential listings, CoStar/LoopNet, phone/email, predictive scoring.

## Quality bars
- Accuracy: ≥95% on supported intents (golden set).
- p95 latency: ≤2.0s.
- Freshness: ACRIS/DOB daily, PLUTO quarterly; show last_updated.

## Success metrics (pilot)
- 5 WAUs, 2 paid conversions ($49–$99/mo).
- <2 blocking issues/week.

## Risks → Mitigations
- Data drift → staging tables + schema checks + alerts.
- LLM hallucination → **grounding via answer bundle** only.
- Perf → Redis, precomputed joins, PostGIS indexes.

