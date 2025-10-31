-- Postgres + PostGIS schema (minimal MVP)
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS parcels (
  bbl TEXT PRIMARY KEY,
  address_std TEXT,
  borough TEXT, block INT, lot INT, bin INT,
  land_use TEXT, tax_class TEXT,
  lot_area_sqft INT, bldg_sqft INT,
  stories INT, year_built INT,
  geom geometry(MultiPolygon, 2263),
  last_updated TIMESTAMP
);

CREATE TABLE IF NOT EXISTS zoning_layers (
  bbl TEXT PRIMARY KEY,
  base_codes TEXT[],
  overlays TEXT[],
  sp_districts TEXT[],
  far_notes TEXT,
  last_updated TIMESTAMP
);

CREATE TABLE IF NOT EXISTS acris_events (
  id BIGSERIAL PRIMARY KEY,
  bbl TEXT,
  doc_type TEXT,
  recorded_at DATE,
  consideration NUMERIC,
  parties JSONB,
  doc_id TEXT,
  doc_url TEXT,
  last_updated TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_acris_bbl ON acris_events(bbl);
CREATE INDEX IF NOT EXISTS idx_acris_rec ON acris_events(recorded_at DESC);

CREATE TABLE IF NOT EXISTS permits_violations (
  id BIGSERIAL PRIMARY KEY,
  bbl TEXT,
  kind TEXT,         -- permit | violation
  status TEXT,
  filed_at DATE,
  closed_at DATE,
  details JSONB,
  last_updated TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pv_bbl ON permits_violations(bbl);

-- Sprint A: extensions and indexes for fuzzy address search
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS idx_parcels_address_trgm ON parcels USING gin (address_std gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_parcels_bbl ON parcels(bbl);

-- Ingestion metadata
CREATE TABLE IF NOT EXISTS ingestion_watermarks (
  source TEXT PRIMARY KEY,
  last_cursor BIGINT,
  last_seen_at TIMESTAMPTZ,
  last_run TIMESTAMPTZ NOT NULL DEFAULT now(),
  notes TEXT
);

-- Ingestion staging tables
CREATE TABLE IF NOT EXISTS staging_dob_permits (
  id BIGSERIAL PRIMARY KEY,
  source_pk TEXT NOT NULL,
  payload JSONB NOT NULL,
  pulled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  row_hash TEXT NOT NULL,
  UNIQUE (row_hash)
);
CREATE INDEX IF NOT EXISTS idx_stg_dob_permits_hash ON staging_dob_permits(row_hash);

CREATE TABLE IF NOT EXISTS staging_dob_violations (
  id BIGSERIAL PRIMARY KEY,
  source_pk TEXT NOT NULL,
  payload JSONB NOT NULL,
  pulled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  row_hash TEXT NOT NULL,
  UNIQUE (row_hash)
);
CREATE INDEX IF NOT EXISTS idx_stg_dob_violations_hash ON staging_dob_violations(row_hash);

CREATE TABLE IF NOT EXISTS staging_hpd_violations (
  id BIGSERIAL PRIMARY KEY,
  source_pk TEXT NOT NULL,
  payload JSONB NOT NULL,
  pulled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  row_hash TEXT NOT NULL,
  UNIQUE (row_hash)
);
CREATE INDEX IF NOT EXISTS idx_stg_hpd_violations_hash ON staging_hpd_violations(row_hash);

CREATE TABLE IF NOT EXISTS staging_hpd_registrations (
  id BIGSERIAL PRIMARY KEY,
  source_pk TEXT NOT NULL,
  payload JSONB NOT NULL,
  pulled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  row_hash TEXT NOT NULL,
  UNIQUE (row_hash)
);
CREATE INDEX IF NOT EXISTS idx_stg_hpd_reg_hash ON staging_hpd_registrations(row_hash);

CREATE TABLE IF NOT EXISTS staging_acris_legal (
  id BIGSERIAL PRIMARY KEY,
  source_pk TEXT NOT NULL,
  payload JSONB NOT NULL,
  pulled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  row_hash TEXT NOT NULL,
  UNIQUE (row_hash)
);
CREATE INDEX IF NOT EXISTS idx_stg_acris_legal_hash ON staging_acris_legal(row_hash);

CREATE TABLE IF NOT EXISTS staging_acris_mortgage (
  id BIGSERIAL PRIMARY KEY,
  source_pk TEXT NOT NULL,
  payload JSONB NOT NULL,
  pulled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  row_hash TEXT NOT NULL,
  UNIQUE (row_hash)
);
CREATE INDEX IF NOT EXISTS idx_stg_acris_mtg_hash ON staging_acris_mortgage(row_hash);

CREATE TABLE IF NOT EXISTS staging_pluto (
  id BIGSERIAL PRIMARY KEY,
  source_pk TEXT NOT NULL,
  payload JSONB NOT NULL,
  pulled_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  row_hash TEXT NOT NULL,
  UNIQUE (row_hash)
);
CREATE INDEX IF NOT EXISTS idx_stg_pluto_hash ON staging_pluto(row_hash);

-- Ingestion canonical tables
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
  issuance_date DATE,
  latest_status_date DATE,
  estimated_cost NUMERIC,
  raw JSONB,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_dob_permits_bbl ON dob_permits(bbl);
CREATE INDEX IF NOT EXISTS idx_dob_permits_filing ON dob_permits(filing_date);

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
CREATE INDEX IF NOT EXISTS idx_dob_violations_bbl ON dob_violations(bbl);
CREATE INDEX IF NOT EXISTS idx_dob_violations_issue ON dob_violations(issue_date);

CREATE TABLE IF NOT EXISTS hpd_violations (
  violation_id TEXT PRIMARY KEY,
  bbl TEXT,
  house_no TEXT,
  street_name TEXT,
  borough TEXT,
  status TEXT,
  inspection_date DATE,
  disposition_date DATE,
  raw JSONB,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hpd_violations_bbl ON hpd_violations(bbl);

CREATE TABLE IF NOT EXISTS hpd_registrations (
  registration_id TEXT PRIMARY KEY,
  bbl TEXT,
  house_no TEXT,
  street_name TEXT,
  borough TEXT,
  registration_date DATE,
  raw JSONB,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_hpd_registrations_bbl ON hpd_registrations(bbl);

CREATE TABLE IF NOT EXISTS acris_legal (
  doc_id TEXT PRIMARY KEY,
  bbl TEXT,
  doc_type TEXT,
  recorded_date DATE,
  raw JSONB,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_acris_legal_bbl ON acris_legal(bbl);

CREATE TABLE IF NOT EXISTS acris_mortgage (
  doc_id TEXT PRIMARY KEY,
  bbl TEXT,
  doc_type TEXT,
  recorded_date DATE,
  amount NUMERIC,
  raw JSONB,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_acris_mortgage_bbl ON acris_mortgage(bbl);

-- Ensure watermarks metadata table exists
CREATE TABLE IF NOT EXISTS ingestion_watermarks (
  source TEXT PRIMARY KEY,
  last_cursor BIGINT,
  last_seen_at TIMESTAMPTZ,
  last_run TIMESTAMPTZ,
  notes TEXT
);

-- PLUTO ingestion staging table
CREATE TABLE IF NOT EXISTS pluto_staging (
  rowhash TEXT PRIMARY KEY,
  bbl TEXT,
  borough TEXT,
  houseno TEXT,
  street TEXT,
  zipcode TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  raw JSONB NOT NULL
);

-- Canonical PLUTO table
CREATE TABLE IF NOT EXISTS pluto (
  rowhash TEXT PRIMARY KEY,
  bbl TEXT,
  address TEXT,
  zipcode TEXT,
  borough TEXT,
  houseno TEXT,
  street TEXT,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  raw JSONB,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_pluto_bbl ON pluto (bbl);
CREATE INDEX IF NOT EXISTS idx_pluto_address ON pluto (street, houseno);
