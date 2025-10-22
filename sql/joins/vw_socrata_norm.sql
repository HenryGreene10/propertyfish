CREATE OR REPLACE VIEW public.vw_socrata_norm AS
WITH base AS (
    SELECT
        upper(trim(COALESCE(dp.job__::text, dp.job_number::text, dp.job::text))) AS job_number,
        upper(trim(COALESCE(dp.borough::text, dp.boro::text, dp.boroname::text, dp.boro_name::text))) AS borough_raw,
        COALESCE(dp.block::text, dp.blk::text) AS block_raw,
        dp.lot::text AS lot_raw,
        dp.house__::text AS house_primary,
        dp.house_no::text AS house_alt,
        dp.houseno::text AS house_alt2,
        dp.street_name::text AS street_primary,
        dp.street::text AS street_alt,
        COALESCE(dp.gis_latitude::double precision, dp.latitude::double precision) AS latitude_val,
        COALESCE(dp.gis_longitude::double precision, dp.longitude::double precision) AS longitude_val,
        dp.filing_date,
        dp.issuance_date
    FROM public.dob_permits dp
),
address AS (
    SELECT
        base.*,
        upper(trim(COALESCE(base.house_primary, base.house_alt, base.house_alt2))) AS house_norm,
        upper(trim(COALESCE(base.street_primary, base.street_alt))) AS street_norm,
        CASE WHEN COALESCE(base.block_raw, '') ~ '^\d+$' THEN base.block_raw::bigint END AS block_num,
        CASE WHEN COALESCE(base.lot_raw, '') ~ '^\d+$' THEN base.lot_raw::bigint END AS lot_num
    FROM base
),
borough AS (
    SELECT
        address.*,
        CASE
            WHEN address.borough_raw IS NULL THEN NULL
            WHEN address.borough_raw ~ '^[1-5]$' THEN address.borough_raw
            WHEN address.borough_raw IN ('MANHATTAN','MN','NEW YORK') THEN '1'
            WHEN address.borough_raw IN ('BRONX','BX','THE BRONX') THEN '2'
            WHEN address.borough_raw IN ('BROOKLYN','BK','KINGS') THEN '3'
            WHEN address.borough_raw IN ('QUEENS','QN','QNS') THEN '4'
            WHEN address.borough_raw IN ('STATEN ISLAND','SI','RICHMOND') THEN '5'
            ELSE NULL
        END AS borough_digit
    FROM address
)
SELECT
    borough.job_number,
    borough.borough_raw,
    borough.borough_digit::smallint AS boro_num,
    CASE borough.borough_digit
        WHEN '1' THEN 'MANHATTAN'
        WHEN '2' THEN 'BRONX'
        WHEN '3' THEN 'BROOKLYN'
        WHEN '4' THEN 'QUEENS'
        WHEN '5' THEN 'STATEN ISLAND'
    END AS borough_name,
    borough.block_num AS block,
    borough.lot_num AS lot,
    CASE
        WHEN borough.borough_digit IS NOT NULL AND borough.block_num IS NOT NULL AND borough.lot_num IS NOT NULL
        THEN borough.borough_digit || lpad(borough.block_num::text, 5, '0') || lpad(borough.lot_num::text, 4, '0')
        ELSE NULL
    END AS bbl_text,
    NULLIF(borough.house_norm, '') AS house_no,
    NULLIF(borough.street_norm, '') AS street_name,
    CASE
        WHEN borough.house_norm IS NOT NULL AND borough.house_norm <> ''
             AND borough.street_norm IS NOT NULL AND borough.street_norm <> ''
        THEN borough.house_norm || ' ' || borough.street_norm
        ELSE NULL
    END AS address_key,
    borough.latitude_val AS latitude,
    borough.longitude_val AS longitude,
    CASE
        WHEN borough.longitude_val IS NOT NULL AND borough.latitude_val IS NOT NULL
        THEN ST_SetSRID(ST_MakePoint(borough.longitude_val, borough.latitude_val), 4326)
        ELSE NULL
    END AS geom_4326,
    CASE
        WHEN borough.longitude_val IS NOT NULL AND borough.latitude_val IS NOT NULL
        THEN ST_Transform(ST_SetSRID(ST_MakePoint(borough.longitude_val, borough.latitude_val), 4326), 2263)
        ELSE NULL
    END AS geom_2263,
    borough.filing_date,
    borough.issuance_date
FROM borough;
