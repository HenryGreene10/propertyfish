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
