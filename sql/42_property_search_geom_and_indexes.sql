-- Ensure required extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- 1) Ensure vw_property_search exposes geom_4326 (point)
-- If your existing view already selects latitude/longitude, redefine the view here
-- with the added expression for geom_4326.
DROP VIEW IF EXISTS vw_property_search CASCADE;
CREATE VIEW vw_property_search AS
SELECT
  r.bbl,
  r.address,
  r.zipcode,
  r.borough,
  r.houseno,
  r.street,
  r.latitude,
  r.longitude,
  CASE
    WHEN r.latitude IS NOT NULL AND r.longitude IS NOT NULL
    THEN ST_SetSRID(ST_MakePoint(r.longitude, r.latitude), 4326)
    ELSE NULL
  END AS geom_4326,
  r.permits_count,
  r.permits_last_filed,
  r.violations_count,
  r.violations_last_issued,
  -- Make sure address_key is normalized for trigram/unaccent searches
  UPPER(unaccent(
    regexp_replace(COALESCE(r.address, ''), '[^A-Za-z0-9 ]', ' ', 'g')
  )) AS address_key
FROM vw_property_rollup r;

-- 2) Helpful indexes.
-- Note: you cannot index a VIEW directly, so add them on a MATERIALIZED VIEW or the base tables.
-- If you want indexes, switch vw_property_search to a materialized view for production:
--   DROP MATERIALIZED VIEW IF EXISTS mv_property_search;
--   CREATE MATERIALIZED VIEW mv_property_search AS (SELECT ... same as above ...);
--   CREATE INDEX ... ON mv_property_search(...);
-- For now we’ll add functional indexes on the base tables that the view depends on, plus a quick
-- materialized version you can refresh for pilot.

-- Materialized view for speed in pilot:
DROP MATERIALIZED VIEW IF EXISTS mv_property_search;
CREATE MATERIALIZED VIEW mv_property_search AS
SELECT * FROM vw_property_search;

-- Indexes on the materialized view
CREATE INDEX IF NOT EXISTS idx_mv_search_geom_gist
  ON mv_property_search USING GIST (geom_4326);

CREATE INDEX IF NOT EXISTS idx_mv_search_bbl
  ON mv_property_search (bbl);

CREATE INDEX IF NOT EXISTS idx_mv_search_borough
  ON mv_property_search (borough);

CREATE INDEX IF NOT EXISTS idx_mv_search_zipcode
  ON mv_property_search (zipcode);

CREATE INDEX IF NOT EXISTS idx_mv_search_addresskey_trgm
  ON mv_property_search USING GIN (address_key gin_trgm_ops);
