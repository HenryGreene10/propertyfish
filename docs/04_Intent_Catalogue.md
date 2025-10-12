# Intent Catalogue (v0.1)

## Intents
- zoning_summary{bbl} → GET /property/:bbl/zoning
- recent_deeds{bbl, limit=3} → /deeds
- recent_mortgages{bbl, limit=3} → /mortgages
- permits_open{bbl} → /permits?since=last_365_days
- violations_recent{bbl} → /violations?since=last_365_days
- lot_building_facts{bbl} → /summary
- comps_nearby{bbl, radius_m=250, lookback=3y} (phase 2)
- who_owns_raw{bbl} → owner raw fields from PLUTO
- what_changed_since{bbl, since}
- explain_term{term, bbl?}

## Fallbacks
- Missing BBL → call /resolve.
- Empty result → neutral “Not available in sources” + deep link.

