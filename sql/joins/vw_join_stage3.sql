CREATE OR REPLACE VIEW vw_join_stage3 AS
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
    ST_Distance(p.geom, s.geom_2263) AS distance_feet,
    'stage3'::text AS join_stage
FROM vw_socrata_norm s
JOIN parcels p
  ON s.geom_2263 IS NOT NULL
 AND p.geom IS NOT NULL
 AND ST_Contains(p.geom, s.geom_2263)
WHERE s.geom_2263 IS NOT NULL
  AND NOT EXISTS (
        SELECT 1
        FROM vw_join_stage1 j1
        WHERE j1.job_number = s.job_number
    )
  AND NOT EXISTS (
        SELECT 1
        FROM vw_join_stage2 j2
        WHERE j2.job_number = s.job_number
    );
