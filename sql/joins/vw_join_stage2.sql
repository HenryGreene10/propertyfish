CREATE OR REPLACE VIEW vw_join_stage2 AS
WITH parcel_addresses AS (
    SELECT
        p.*,
        upper(regexp_replace(coalesce(p.address_std, ''), '\s+', ' ', 'g')) AS address_norm,
        upper(coalesce(p.borough, '')) AS borough_norm
    FROM parcels p
)
SELECT
    s.job_number,
    s.bbl_text,
    s.boro_num,
    s.boro_name,
    s.block5,
    s.lot4,
    s.house_number_norm,
    s.street_norm,
    s.address_key,
    p.bbl AS parcel_bbl,
    p.address_std AS parcel_address,
    p.borough AS parcel_borough,
    'stage2'::text AS join_stage
FROM vw_socrata_norm s
JOIN parcel_addresses p
  ON s.address_key IS NOT NULL
 AND p.address_norm = s.address_key
 AND (
        s.boro_name IS NULL
        OR p.borough_norm = s.boro_name
        OR p.borough_norm = coalesce(s.boro_num::text, '')
    )
WHERE s.address_key IS NOT NULL
  AND NOT EXISTS (
        SELECT 1
        FROM vw_join_stage1 j1
        WHERE j1.job_number = s.job_number
    );
