-- sql/joins/mv_permit_agg.sql
-- Build permit aggregation with correct 10-digit BBL (borough + block + lot)

DROP MATERIALIZED VIEW IF EXISTS public.mv_permit_agg CASCADE;

CREATE MATERIALIZED VIEW public.mv_permit_agg AS
WITH src AS (
  SELECT
    CASE UPPER(TRIM(dp.borough))
      WHEN 'MN'            THEN 1
      WHEN 'MANHATTAN'     THEN 1
      WHEN 'BX'            THEN 2
      WHEN 'BRONX'         THEN 2
      WHEN 'BK'            THEN 3
      WHEN 'BROOKLYN'      THEN 3
      WHEN 'QN'            THEN 4
      WHEN 'QUEENS'        THEN 4
      WHEN 'SI'            THEN 5
      WHEN 'STATEN ISLAND' THEN 5
      ELSE NULL
    END                                  AS boro_code,
    NULLIF((dp.raw ->> 'block')::int, 0) AS block_int,
    NULLIF((dp.raw ->> 'lot')::int,   0) AS lot_int,
    dp.issuance_date                     AS permit_date
  FROM public.dob_permits dp
  WHERE dp.issuance_date IS NOT NULL
),
norm AS (
  SELECT
    -- CORRECT 10-digit BBL: boro*1e9 + block*1e4 + lot
    ( boro_code::bigint * 1000000000
    + block_int::bigint * 10000
    + lot_int::bigint )                  AS bbl_norm,
    permit_date
  FROM src
  WHERE boro_code BETWEEN 1 AND 5
    AND block_int IS NOT NULL
    AND lot_int   IS NOT NULL
),
win AS (
  SELECT
    bbl_norm,
    permit_date,
    COUNT(*) OVER (
      PARTITION BY bbl_norm
      ORDER BY permit_date
      RANGE BETWEEN '365 days'::interval PRECEDING AND CURRENT ROW
    ) AS permit_count_12m
  FROM norm
)
SELECT
  bbl_norm,
  MAX(permit_date)      AS last_permit_date,
  MAX(permit_count_12m) AS permit_count_12m
FROM win
GROUP BY bbl_norm;

CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_permit_agg_bbl
  ON public.mv_permit_agg (bbl_norm);

-- Verification (run manually if needed):
-- SELECT COUNT(*) FROM mv_permit_agg;
-- SELECT SUBSTRING(bbl_norm::text,1,1) AS first_digit, COUNT(*) FROM mv_permit_agg GROUP BY 1 ORDER BY 1;
