# Search Contract Audit

Context gathered from the local snapshots (`docs/db/property_search_desc.txt`, `sql/40_property_rollup.sql`, `sql/41_property_search.sql`, `sql/42_property_search_geom_and_indexes.sql`, fixtures) shows that `property_search` is a permit-centric materialized view built on PLUTO addresses plus DOB permit aggregates. `docs/db/property_search_columns.csv` is empty in this repo snapshot, so the column list below is derived from the view definitions themselves.

## Schema summary (property_search)
- `address` (text) — uppercase mailing-style address built from PLUTO `houseno`+`street`.
- `bbl` (bigint) — numeric borough-block-lot key; API should stringify.
- `borough` (text) — 2-letter code {`MN`,`BX`,`BK`,`QN`,`SI`}.
- `borough_full` (text) — spelled-out borough name.
- `permit_count_12m` (bigint) — `COALESCE(a.permit_count_12m,0)` from `mv_permit_agg`.
- `last_permit_date` (date) — latest DOB permit activity for the BBL in the 12‑month aggregate.
- Upstream source (`vw_property_search` in `sql/42_property_search_geom_and_indexes.sql`) also exposes `zipcode`, `latitude`, `longitude`, `geom_4326`, `violations_count`, `address_key`. These are already referenced in the backend router and survive through the materialized view even though they are not listed in `property_search_desc`.
- `year_built` now comes from `public.properties` (LEFT JOIN on BBL). Floors/units totals are not part of this snapshot and remain `NULL` in API responses until a richer data source is wired in.

## Filter contract
- `q` (text, optional). Matches `ps.address ILIKE '%q%'`, falls back to trigram similarity on `ps.address_key` when available, and accepts raw BBL strings (`CAST(ps.bbl AS TEXT) ILIKE '%q%'`). Empty/whitespace-only strings are ignored.
- `borough` (string, optional). Accept two-letter codes or spelled-out names; normalize to `{MN,BX,BK,QN,SI}` using the mappings already defined for BBL parsing. Only equality filters; no partial LIKEs.
- `year_min` (int ≥ 0, optional). Applies `ps.<year_col> >= :year_min` (`year_built` or `yearbuilt`). Nulls excluded.
- `permits_min_12m` (int ≥ 0, optional). Uses `ps.permit_count_12m` as the canonical 12‑month counter (`ps.permit_count_12m >= :permits_min_12m`). When the aggregate is missing, the value is `0`, so the filter naturally drops zero-permit rows.
- Null policy: filters only run when the client provides a value. Numeric comparisons are straightforward `>=` checks which skip rows where the source column is NULL.

## Sorting rules
- Allowed `sort` values: `last_permit_date`, `year_built`, `permit_count_12m`, `relevance`.
- `order` ∈ `{asc,desc}`; default depends on the field. Descending is the default for numeric/date sorts; `relevance` is always `DESC`.
- Null handling: `NULLS LAST` for descending, `NULLS FIRST` for ascending to keep incomplete data off the top when sorting high→low.
- Tie-breakers: always append `last_permit_date DESC NULLS LAST` and `bbl ASC` to make ordering deterministic.
- Default behavior:
  - With `q`: primary sort is `relevance DESC` (trigram similarity) followed by `last_permit_date DESC NULLS LAST`.
  - Without `q`: default to `last_permit_date DESC NULLS LAST`.
  - If the caller requests `relevance` without `q`, drop back to the default above.

## Pagination
- `limit`: clamp to `[1,50]`, default `20`.
- `offset`: integer ≥ 0, default `0`.
- The API should include `total` alongside `rows` to enable client-side paging controls.

## Example search URLs
1. `GET /api/search?limit=20&offset=0` → default browse by latest permit activity.
2. `GET /api/search?q=MAIN%20ST&borough=BK&limit=10` → relevance-first Brooklyn subset for “Main St”.
3. `GET /api/search?borough=Queens&year_min=1930&sort=year_built&order=asc` → Queens pre-war stock oldest first (name normalization should map “Queens” → `QN`).
4. `GET /api/search?permits_min_12m=3&sort=last_permit_date&order=desc&limit=5` → actively permitted buildings only.
5. `GET /api/search?q=1003560001&sort=relevance` → BBL lookup using the trigram key; falls back to latest permit date as a tie-breaker.
6. `GET /api/search?year_min=1950&permits_min_12m=1&sort=year_built&order=desc` → focus on post-war buildings that recently pulled permits.
7. `GET /api/search?borough=SI&permits_min_12m=0&sort=permit_count_12m&order=asc` → Staten Island buildings with few permits (ascending pushes NULLs first by definition).

## Performance notes (no changes applied yet)
- Keep/refresh `GIN (address_key gin_trgm_ops)` for relevance sorts; consider Postgres `pg_trgm` + trigram indexes on `address`.
- Create partial btree indexes for `last_permit_date` and `year_built` (`WHERE last_permit_date IS NOT NULL`, etc.) to accelerate descending sorts.
- If floors/units become available later, denormalize them into the materialized view (or a companion view) so filters remain cheap.
- For text search, a trigram index on `upper(unaccent(address))` (or materialized `address_key`) keeps `relevance` computations cheap.
- When data volume grows, consider partitioned refreshes (`REFRESH MATERIALIZED VIEW CONCURRENTLY property_search`) and aggregated tables keyed by borough to keep pagination counts fast.

## Refresh command
- `REFRESH MATERIALIZED VIEW CONCURRENTLY public.property_search;`
