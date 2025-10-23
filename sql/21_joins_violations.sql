DROP VIEW IF EXISTS public.vw_violations_join_s1 CASCADE;
CREATE VIEW public.vw_violations_join_s1 AS
SELECT
  v.*,
  pr.bbl       AS parcel_bbl,
  pr.address   AS parcel_address,
  pr.zipcode   AS parcel_zipcode,
  pr.borough   AS parcel_borough,
  pr.houseno   AS parcel_houseno,
  pr.street    AS parcel_street,
  pr.latitude  AS parcel_latitude,
  pr.longitude AS parcel_longitude,
  pr.geom      AS parcel_geom
FROM public.vw_violations_norm v
JOIN public.parcels pr ON public.bbl_normalize(pr.bbl) = public.bbl_normalize(v.bbl_text);

DROP VIEW IF EXISTS public.vw_violations_join_s2 CASCADE;
CREATE VIEW public.vw_violations_join_s2 AS
SELECT
  v.*,
  pr.bbl       AS parcel_bbl,
  pr.address   AS parcel_address,
  pr.zipcode   AS parcel_zipcode,
  pr.borough   AS parcel_borough,
  pr.houseno   AS parcel_houseno,
  pr.street    AS parcel_street,
  pr.latitude  AS parcel_latitude,
  pr.longitude AS parcel_longitude,
  pr.geom      AS parcel_geom
FROM public.vw_violations_norm v
JOIN public.parcels pr
  ON UPPER(REGEXP_REPLACE(COALESCE(pr.houseno::text,'') || ' ' || COALESCE(pr.street,''), '\s+',' ','g')) || ' | ' ||
     (SELECT boro_name FROM public.borough_map bm WHERE bm.boro_code = public.borough_to_code(pr.borough)) = v.address_key
WHERE v.bbl_text IS NULL;

DROP VIEW IF EXISTS public.vw_violations_join_s3 CASCADE;
CREATE VIEW public.vw_violations_join_s3 AS
SELECT
  v.*,
  pr.bbl       AS parcel_bbl,
  pr.address   AS parcel_address,
  pr.zipcode   AS parcel_zipcode,
  pr.borough   AS parcel_borough,
  pr.houseno   AS parcel_houseno,
  pr.street    AS parcel_street,
  pr.latitude  AS parcel_latitude,
  pr.longitude AS parcel_longitude,
  pr.geom      AS parcel_geom
FROM public.vw_violations_norm v
JOIN public.parcels pr
  ON pr.geom IS NOT NULL
 AND v.latitude IS NOT NULL AND v.longitude IS NOT NULL
 AND ST_DWithin(
       pr.geom,
       ST_Transform(ST_SetSRID(ST_Point(v.longitude, v.latitude),4326),2263),
       10
     )
WHERE v.bbl_text IS NULL;

DROP VIEW IF EXISTS public.vw_violations_join_coverage CASCADE;
CREATE VIEW public.vw_violations_join_coverage AS
WITH tot AS (SELECT COUNT(*) total FROM public.vw_violations_norm),
s1 AS (SELECT COUNT(*) matched FROM public.vw_violations_join_s1),
s2 AS (SELECT COUNT(*) matched FROM public.vw_violations_join_s2),
s3 AS (SELECT COUNT(*) matched FROM public.vw_violations_join_s3)
SELECT total, s1.matched AS s1, s2.matched AS s2, s3.matched AS s3,
       ROUND(CASE WHEN total>0 THEN (s1.matched+s2.matched+s3.matched)::numeric/total*100 ELSE 0 END, 2) AS pct_total
FROM tot, s1, s2, s3;
