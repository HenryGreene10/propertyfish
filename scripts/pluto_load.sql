\set ON_ERROR_STOP on

-- Pass the absolute CSV path when calling, e.g.:
--   psql "$DATABASE_URL" -v csv='/ABS/PATH/pluto_slim.csv' -f scripts/pluto_load.sql
-- or hardcode below:
-- \set csv '/home/henry/NYSee/propertyfish/data/pluto/25v2_1/pluto_slim.csv'

-- 0) raw text table
DROP TABLE IF EXISTS stg_pluto_raw;
CREATE TEMP TABLE stg_pluto_raw(
  bbl_txt   TEXT,
  address   TEXT,
  zipcode   TEXT,
  borough_t TEXT,
  block_t   TEXT,
  lot_t     TEXT
);

-- 1) load CSV
\echo Loading from :csv
\copy stg_pluto_raw FROM :'csv' CSV HEADER;

-- 2) cast/clean into typed staging
TRUNCATE stg_pluto_25v2_1;

INSERT INTO stg_pluto_25v2_1 (bbl, address, zipcode, borough, block, lot)
SELECT
  regexp_replace(bbl_txt, '\.0+$', '')::bigint AS bbl,
  address,
  zipcode,
  CASE
    WHEN borough_t ~ '^\d+$' THEN borough_t::smallint
    WHEN lower(borough_t) IN ('manhattan','mn')     THEN 1
    WHEN lower(borough_t) IN ('bronx','bx')         THEN 2
    WHEN lower(borough_t) IN ('brooklyn','bk')      THEN 3
    WHEN lower(borough_t) IN ('queens','qn')        THEN 4
    WHEN lower(borough_t) IN ('staten island','si') THEN 5
    ELSE NULL
  END AS borough,
  NULLIF(block_t,'')::int AS block,
  NULLIF(lot_t,'')::int   AS lot
FROM stg_pluto_raw
WHERE bbl_txt ~ '^[0-9]+(\.0+)?$';

ANALYZE stg_pluto_25v2_1;

-- 3) derived view (house_no/street)
DROP VIEW IF EXISTS stg_pluto_derived;
CREATE VIEW stg_pluto_derived AS
SELECT
  bbl, address, zipcode, borough, block, lot,
  CASE WHEN address ~ '^\s*\d+' THEN split_part(address,' ',1) END AS house_no,
  CASE WHEN position(' ' in address) > 0 THEN substr(address, position(' ' in address)+1) END AS street
FROM stg_pluto_25v2_1;

-- 4) helpers + upserts (idempotent)
CREATE OR REPLACE FUNCTION _addr_norm(hn TEXT, st TEXT, b SMALLINT, z TEXT)
RETURNS TEXT LANGUAGE sql IMMUTABLE AS $$
  SELECT lower(regexp_replace(
    coalesce(hn,'') || ' ' ||
    CASE b WHEN 1 THEN 'manhattan' WHEN 2 THEN 'bronx' WHEN 3 THEN 'brooklyn'
           WHEN 4 THEN 'queens' WHEN 5 THEN 'staten island' END || ' ' ||
    coalesce(st,'') || ' ' || coalesce(z,''),
    '\s+', ' ', 'g'));
$$;

CREATE OR REPLACE PROCEDURE upsert_addresses_from_pluto()
LANGUAGE sql AS $$
  INSERT INTO dim_address(house_no, street, borough, zipcode, full_norm, full_display)
  SELECT DISTINCT d.house_no, d.street, d.borough, d.zipcode,
         _addr_norm(d.house_no, d.street, d.borough, d.zipcode) AS full_norm,
         d.address AS full_display
  FROM stg_pluto_derived d
  WHERE d.house_no IS NOT NULL AND d.street IS NOT NULL
  ON CONFLICT (full_norm) DO NOTHING;
$$;

CREATE OR REPLACE PROCEDURE upsert_parcels_from_pluto()
LANGUAGE sql AS $$
  INSERT INTO dim_parcel(bbl, bin, borough, block, lot, addr_id)
  SELECT d.bbl, NULL::bigint, d.borough, d.block, d.lot, a.addr_id
  FROM stg_pluto_derived d
  JOIN dim_address a
    ON a.full_norm = _addr_norm(d.house_no, d.street, d.borough, d.zipcode)
  ON CONFLICT (bbl) DO UPDATE
    SET addr_id = EXCLUDED.addr_id,
        borough = EXCLUDED.borough,
        block   = EXCLUDED.block,
        lot     = EXCLUDED.lot,
        updated_at = now();
$$;

CALL upsert_addresses_from_pluto();
CALL upsert_parcels_from_pluto();
REFRESH MATERIALIZED VIEW mv_search_property;

-- 5) quick checks
SELECT COUNT(*) AS parcels FROM dim_parcel;
SELECT COUNT(*) AS addrs   FROM dim_address;
