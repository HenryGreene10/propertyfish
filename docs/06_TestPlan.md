# Test Plan (v0.1)

## Golden BBL set
- 20 properties (Manhattan/Brooklyn/Queens; office/retail/industrial/mixed).

## Intent validations
- zoning_summary → has base district & overlays + citation.
- recent_deeds(limit=3) → sorted desc, each with doc_url + citation.
- summary → land_use, lot_area, bldg_sqft, stories, year_built.

## ETL checks
- Row deltas, null spikes, schema drift alerts.
- Freshness alarm if any source >72h stale.

## Performance
- p95 latency ≤ 2.0s; cache hit rate tracked.

## Pilot acceptance
- 10 real questions →≥95% pass on supported intents.
