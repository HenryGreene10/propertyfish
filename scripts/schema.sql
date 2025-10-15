-- helpers
CREATE TABLE IF NOT EXISTS ingestion_watermarks (
  source TEXT PRIMARY KEY,
  last_cursor TEXT,
  last_seen_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS ingestion_alerts (
  id BIGSERIAL PRIMARY KEY,
  source TEXT NOT NULL,
  level TEXT NOT NULL DEFAULT 'warn',  -- 'info'|'warn'|'error'
  summary TEXT NOT NULL,
  details JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at TIMESTAMPTZ
);

-- STAGING (append-only raw)
CREATE TABLE IF NOT EXISTS staging_dob_permits (
  id BIGSERIAL PRIMARY KEY,
  source_pk TEXT NOT NULL,
  payload JSONB NOT NULL,
  pulled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  row_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_stg_dob_permits_hash ON staging_dob_permits (row_hash);

CREATE TABLE IF NOT EXISTS staging_dob_violations (
  id BIGSERIAL PRIMARY KEY,
  source_pk TEXT NOT NULL,
  payload JSONB NOT NULL,
  pulled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  row_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_stg_dob_violations_hash ON staging_dob_violations (row_hash);

CREATE TABLE IF NOT EXISTS staging_acris_master (
  id BIGSERIAL PRIMARY KEY,
  source_pk TEXT NOT NULL,
  payload JSONB NOT NULL,
  pulled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  row_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_stg_acris_master_hash ON staging_acris_master (row_hash);

-- CANONICAL (serves the app)
CREATE TABLE IF NOT EXISTS dob_permits (
  job_number TEXT PRIMARY KEY,
  bbl TEXT,
  house_no TEXT,
  street_name TEXT,
  borough TEXT,
  job_type TEXT,
  work_type TEXT,
  status TEXT,
  filing_date DATE,
  latest_status_date DATE,
  estimated_cost NUMERIC,
  raw JSONB,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_dob_permits_bbl ON dob_permits (bbl);
CREATE INDEX IF NOT EXISTS idx_dob_permits_filing ON dob_permits (filing_date);

CREATE TABLE IF NOT EXISTS dob_violations (
  violation_number TEXT PRIMARY KEY,
  bbl TEXT,
  house_no TEXT,
  street_name TEXT,
  borough TEXT,
  device_type TEXT,
  category TEXT,
  description TEXT,
  status TEXT,
  issue_date DATE,
  disposition_date DATE,
  raw JSONB,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_dob_violations_bbl ON dob_violations (bbl);
CREATE INDEX IF NOT EXISTS idx_dob_violations_issue ON dob_violations (issue_date);

CREATE TABLE IF NOT EXISTS acris_master (
  document_id TEXT PRIMARY KEY,
  doc_type TEXT,
  doc_date DATE,
  bbl TEXT,
  party_primary TEXT,
  amount NUMERIC,
  raw JSONB,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_acris_bbl ON acris_master (bbl);
CREATE INDEX IF NOT EXISTS idx_acris_doc_date ON acris_master (doc_date);

CREATE TABLE IF NOT EXISTS zoning_lots (
  bbl TEXT PRIMARY KEY,
  zoning TEXT,
  land_use TEXT,
  lot_area NUMERIC,
  bldg_area NUMERIC,
  far NUMERIC,
  res_fa NUMERIC,
  comm_fa NUMERIC,
  facil_fa NUMERIC,
  units_res INTEGER,
  year_built INTEGER,
  raw JSONB,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dof_tax (
  bbl TEXT NOT NULL,
  tax_year INTEGER NOT NULL,
  tax_class TEXT,
  assessed_land NUMERIC,
  assessed_total NUMERIC,
  market_value NUMERIC,
  condo_flag BOOLEAN,
  owner_name TEXT,
  raw JSONB,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (bbl, tax_year)
);
CREATE INDEX IF NOT EXISTS idx_dof_tax_bbl ON dof_tax (bbl);
CREATE INDEX IF NOT EXISTS idx_dof_tax_year ON dof_tax (tax_year);

-- Fast summary MV (optional)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_property_activity AS
SELECT
  coalesce(p.bbl, v.bbl) AS bbl,
  COUNT(p.job_number) FILTER (WHERE p.filing_date >= CURRENT_DATE - INTERVAL '365 days') AS permits_last_12m,
  COUNT(v.violation_number) FILTER (WHERE v.status ILIKE 'OPEN%') AS open_violations
FROM dob_permits p
FULL OUTER JOIN dob_violations v ON p.bbl = v.bbl
GROUP BY 1;
