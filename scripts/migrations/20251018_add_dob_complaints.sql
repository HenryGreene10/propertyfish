-- DOB complaints core table
CREATE TABLE IF NOT EXISTS dob_complaints (
  complaint_id          TEXT PRIMARY KEY,
  bbl                   TEXT,
  bin                   TEXT,
  borough               TEXT,
  house_number          TEXT,
  street                TEXT,
  zip                   TEXT,
  apartment             TEXT,
  community_board       TEXT,
  complaint_category    TEXT,
  complaint_type        TEXT,
  status                TEXT,
  priority              TEXT,
  disposition           TEXT,
  inspector             TEXT,
  date_received         TIMESTAMPTZ,
  last_inspection_date  TIMESTAMPTZ,
  last_status_date      TIMESTAMPTZ,
  latitude              DOUBLE PRECISION,
  longitude             DOUBLE PRECISION,
  source_version        TEXT DEFAULT 'dob_complaints_v1',
  raw                   JSONB NOT NULL,
  created_at            TIMESTAMPTZ DEFAULT now(),
  updated_at            TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dob_complaints_bbl ON dob_complaints (bbl);
CREATE INDEX IF NOT EXISTS idx_dob_complaints_date_received ON dob_complaints (date_received);
CREATE INDEX IF NOT EXISTS idx_dob_complaints_last_status_date ON dob_complaints (last_status_date);

-- Staging table for batch upserts
CREATE TABLE IF NOT EXISTS dob_complaints__staging (
  complaint_id          TEXT PRIMARY KEY,
  bbl                   TEXT,
  bin                   TEXT,
  borough               TEXT,
  house_number          TEXT,
  street                TEXT,
  zip                   TEXT,
  apartment             TEXT,
  community_board       TEXT,
  complaint_category    TEXT,
  complaint_type        TEXT,
  status                TEXT,
  priority              TEXT,
  disposition           TEXT,
  inspector             TEXT,
  date_received         TIMESTAMPTZ,
  last_inspection_date  TIMESTAMPTZ,
  last_status_date      TIMESTAMPTZ,
  latitude              DOUBLE PRECISION,
  longitude             DOUBLE PRECISION,
  source_version        TEXT,
  raw                   JSONB NOT NULL,
  loaded_at             TIMESTAMPTZ DEFAULT now()
);

-- Materialized view summarising DOB complaints by property
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_property_events__dob_complaints AS
SELECT
  bbl,
  COUNT(*) AS complaints_total,
  COUNT(*) FILTER (WHERE date_received >= now() - INTERVAL '365 days') AS complaints_1y,
  MAX(date_received) AS complaints_most_recent
FROM dob_complaints
WHERE bbl IS NOT NULL
GROUP BY bbl;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_prop_events_dob_complaints_bbl
  ON mv_property_events__dob_complaints (bbl);
