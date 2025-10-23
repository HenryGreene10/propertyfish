DROP VIEW IF EXISTS public.vw_property_search CASCADE;
CREATE VIEW public.vw_property_search AS
SELECT
  r.*,
  UPPER(REGEXP_REPLACE(COALESCE(houseno::text,'') || ' ' || COALESCE(street,''), '\s+',' ','g')) || ' | ' ||
  (SELECT boro_name
     FROM public.borough_map bm
    WHERE bm.boro_code = public.borough_to_code(r.borough)
  ) AS address_key
FROM public.vw_property_rollup r;
