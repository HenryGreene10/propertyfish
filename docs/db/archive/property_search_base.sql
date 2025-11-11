-- PLUTO-only base: no risky casts here
DROP MATERIALIZED VIEW IF EXISTS public.property_search_base CASCADE;

CREATE MATERIALIZED VIEW public.property_search_base AS
SELECT
  p.bbl::bigint                                      AS bbl,
  -- normalized address text for consistent search
  COALESCE(upper(trim(both ' ' FROM COALESCE(p.houseno, '') || ' ' || p.street)), '') AS address,
  p.borough                                          AS borough,
  -- keep both code and full name; full name via CASE on PLUTO 'borough' if already 2-letter:
  CASE p.borough
    WHEN 'MN' THEN 'MANHATTAN'
    WHEN 'BX' THEN 'BRONX'
    WHEN 'BK' THEN 'BROOKLYN'
    WHEN 'QN' THEN 'QUEENS'
    WHEN 'SI' THEN 'STATEN ISLAND'
    ELSE NULL
  END                                                AS borough_full
FROM public.pluto p
WHERE p.bbl IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_property_search_base_bbl ON public.property_search_base (bbl);
