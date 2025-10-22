CREATE OR REPLACE VIEW vw_join_stage1 AS
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
    'stage1'::text AS join_stage
FROM vw_socrata_norm s
JOIN parcels p
  ON p.bbl = s.bbl_text
WHERE s.bbl_text IS NOT NULL;
