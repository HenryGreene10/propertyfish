DROP MATERIALIZED VIEW IF EXISTS property_search CASCADE;

CREATE MATERIALIZED VIEW property_search AS
WITH psb AS (
  SELECT
    address,
    -- strip any ".000000000" or other decimal tails, then cast
    NULLIF(regexp_replace(bbl::text, '\..*', ''), '')::bigint AS bbl
  FROM public.property_search_base
),
pa AS (
  SELECT
    bbl_norm::bigint AS bbl_norm,
    permit_count_12m,
    last_permit_date
  FROM public.mv_permit_agg
),
p_enriched AS (
  SELECT
    psb.address,
    psb.bbl,
    SUBSTRING(LPAD(psb.bbl::text, 10, '0') FROM 1 FOR 1) AS boro_digit
  FROM psb
)
SELECT
  COALESCE(
    NULLIF(UPPER(TRIM(COALESCE(p.houseno,'') || ' ' || p.street)),''),
    e.address
  ) AS address,
  e.bbl,
  CASE e.boro_digit
    WHEN '1' THEN 'MN'
    WHEN '2' THEN 'BX'
    WHEN '3' THEN 'BK'
    WHEN '4' THEN 'QN'
    WHEN '5' THEN 'SI'
    ELSE NULL
  END AS borough,
  COALESCE(a.permit_count_12m, 0) AS permit_count,
  a.last_permit_date,
  CASE e.boro_digit
    WHEN '1' THEN 'Manhattan'
    WHEN '2' THEN 'Bronx'
    WHEN '3' THEN 'Brooklyn'
    WHEN '4' THEN 'Queens'
    WHEN '5' THEN 'Staten Island'
    ELSE NULL
  END AS borough_full
FROM p_enriched e
LEFT JOIN public.pluto p
  ON NULLIF(regexp_replace(p.bbl::text, '\..*', ''), '')::bigint = e.bbl
LEFT JOIN pa a
  ON e.bbl = a.bbl_norm;

-- Required for CONCURRENT refresh and fast lookups
CREATE UNIQUE INDEX IF NOT EXISTS ux_property_search_bbl
  ON public.property_search (bbl);
CREATE INDEX IF NOT EXISTS ix_property_search_addr_trgm ON property_search USING gin (address gin_trgm_ops);
