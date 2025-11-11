-- sql/joins/mv_property_search.sql
-- Canonical search view joining PLUTO to mv_permit_agg by normalized BIGINT BBL

DROP VIEW IF EXISTS public.property_search;

CREATE VIEW public.property_search AS
SELECT
  -- Return digits-only BBL (left-padded to 10) for API
  lpad(regexp_replace(pl.bbl, '\D', '', 'g'), 10, '0') AS bbl,
  COALESCE(
    NULLIF(pl.address, ''),
    NULLIF(trim(coalesce(pl.houseno, '') || ' ' || coalesce(pl.street, '')), '')
  ) AS address,
  pl.borough AS borough,
  CASE pl.borough
    WHEN 'MN' THEN 'Manhattan'
    WHEN 'BX' THEN 'Bronx'
    WHEN 'BK' THEN 'Brooklyn'
    WHEN 'QN' THEN 'Queens'
    WHEN 'SI' THEN 'Staten Island'
    ELSE ''
  END AS borough_full,
  COALESCE(pa.permit_count_12m, 0) AS permit_count_12m,
  pa.last_permit_date AS last_permit_date
FROM public.pluto pl
LEFT JOIN public.mv_permit_agg pa
  ON lpad(regexp_replace(pl.bbl, '\D', '', 'g'), 10, '0') = lpad(pa.bbl_norm::text, 10, '0');

-- Verification (run manually if needed):
-- SELECT COUNT(*) FROM property_search WHERE permit_count_12m > 0 LIMIT 5;
