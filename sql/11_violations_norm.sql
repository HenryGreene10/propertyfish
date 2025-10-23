DROP VIEW IF EXISTS public.vw_violations_norm CASCADE;

CREATE VIEW public.vw_violations_norm AS
WITH src AS (
  SELECT
    UPPER(NULLIF(TRIM(violation_number),'')) AS violation_number,
    UPPER(NULLIF(TRIM(bbl),''))              AS bbl_text,
    NULLIF(issue_date::text,'')::date        AS issue_date,
    NULLIF(disposition_date::text,'')::date  AS disposition_date,
    NULLIF(TRIM(status),'')                  AS status,
    NULL::int                                AS boro_code,
    NULL::int                                AS block,
    NULL::int                                AS lot,
    NULL::text                               AS house_no,
    NULL::text                               AS street_name,
    NULL::double precision                   AS latitude,
    NULL::double precision                   AS longitude
  FROM public.dob_violations
),
parts AS (
  SELECT s.*,
         (public.parse_bbl(s.bbl_text)).boro  AS boro_code_d,
         (public.parse_bbl(s.bbl_text)).block AS block_d,
         (public.parse_bbl(s.bbl_text)).lot   AS lot_d
  FROM src s
)
SELECT
  p.violation_number,
  COALESCE(p.bbl_text, public.make_bbl(p.boro_code, p.block, p.lot)) AS bbl_text,
  COALESCE(p.boro_code, p.boro_code_d) AS boro_code,
  COALESCE(p.block,     p.block_d)     AS block,
  COALESCE(p.lot,       p.lot_d)       AS lot,
  p.house_no,
  p.street_name,
  p.issue_date, p.disposition_date, p.status,
  p.latitude, p.longitude,
  bm.boro_name,
  CASE WHEN p.house_no IS NULL AND p.street_name IS NULL THEN NULL
       ELSE UPPER(REGEXP_REPLACE(COALESCE(p.house_no,'') || ' ' || COALESCE(p.street_name,''), '\s+', ' ', 'g')) || ' | ' || COALESCE(bm.boro_name,'')
  END AS address_key
FROM parts p
LEFT JOIN public.borough_map bm ON bm.boro_code = COALESCE(p.boro_code, p.boro_code_d);
