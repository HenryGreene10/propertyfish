DROP VIEW IF EXISTS public.vw_property_rollup CASCADE;

CREATE VIEW public.vw_property_rollup AS
WITH p AS (
  SELECT
    bbl,
    address,
    zipcode,
    borough,
    houseno,
    street,
    latitude,
    longitude,
    -- derive a projected point if we have lat/long (optional; handy for maps/joins)
    CASE
      WHEN longitude IS NOT NULL AND latitude IS NOT NULL
      THEN ST_Transform(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326), 2263)
    END AS geom_2263
  FROM public.pluto
),
perm AS (
  SELECT
    parcel_bbl AS bbl,
    COUNT(*)         AS permits_count,
    MAX(filing_date) AS permits_last_filed
  FROM public.vw_permits_join_s1
  GROUP BY parcel_bbl
),
viol AS (
  SELECT
    parcel_bbl AS bbl,
    COUNT(*)          AS violations_count,
    MAX(issue_date)   AS violations_last_issued
  FROM public.vw_violations_join_s1
  GROUP BY parcel_bbl
)
SELECT
  p.*,
  COALESCE(perm.permits_count, 0)    AS permits_count,
  perm.permits_last_filed,
  COALESCE(viol.violations_count, 0) AS violations_count,
  viol.violations_last_issued
FROM p
LEFT JOIN perm ON public.bbl_normalize(perm.bbl) = public.bbl_normalize(p.bbl)
LEFT JOIN viol ON public.bbl_normalize(viol.bbl) = public.bbl_normalize(p.bbl);
