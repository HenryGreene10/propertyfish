-- Safe recreate
DROP MATERIALIZED VIEW IF EXISTS mv_permit_agg CASCADE;

-- Aggregate DOB permits by normalized BBL
-- Ensure the join key is BIGINT to match property_search_base.bbl
CREATE MATERIALIZED VIEW mv_permit_agg AS
SELECT
  bbl_normalize(bbl)::bigint              AS bbl_norm,          -- <- force BIGINT
  MAX(issuance_date)                      AS last_permit_date,
  COUNT(*) FILTER (
    WHERE issuance_date >= CURRENT_DATE - INTERVAL '365 days'
  )                                       AS permit_count_12m
FROM public.dob_permits
GROUP BY bbl_normalize(bbl)::bigint;

-- Helpful index for downstream joins
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_permit_agg_bbl ON mv_permit_agg(bbl_norm);
