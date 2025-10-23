BEGIN;

CREATE TABLE IF NOT EXISTS dob_complaints (
  complaint_id     text PRIMARY KEY,
  status           text,
  date_entered     timestamp NULL,
  house_number     text,
  house_street     text,
  zip_code         text,
  bin              text,
  community_board  text,
  complaint_category text,
  inspection_date  timestamp NULL,
  disposition_date timestamp NULL,
  dobrundate       timestamp NULL,
  updated_at       timestamp with time zone DEFAULT now()
);

-- Upper(address) and zip indexes to support address+zip join to PLUTO
CREATE INDEX IF NOT EXISTS idx_dob_c_addr_upper
  ON dob_complaints (upper(house_number || ' ' || house_street));

CREATE INDEX IF NOT EXISTS idx_dob_c_zip
  ON dob_complaints (zip_code);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_property_events__dob_complaints AS
SELECT
  p.bbl,
  c.complaint_id,
  c.date_entered,
  c.status,
  c.complaint_category,
  c.inspection_date,
  c.disposition_date,
  c.bin,
  c.house_number,
  c.house_street,
  c.zip_code
FROM dob_complaints c
JOIN pluto p
  ON upper(p.address) = upper(c.house_number || ' ' || c.house_street)
 AND (p.zipcode IS NULL OR c.zip_code IS NULL OR p.zipcode = c.zip_code);

CREATE INDEX IF NOT EXISTS idx_mv_prop_dob_bbl ON mv_property_events__dob_complaints (bbl);

COMMIT;
