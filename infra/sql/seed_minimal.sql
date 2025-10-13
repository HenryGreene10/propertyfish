-- Tables
CREATE TABLE IF NOT EXISTS properties (
  bbl TEXT PRIMARY KEY,
  address TEXT,
  normalized_address TEXT,
  owner_name TEXT,
  year_built INT,
  units_res INT
);

CREATE TABLE IF NOT EXISTS dob_permits (
  id SERIAL PRIMARY KEY,
  bbl TEXT,
  job_number TEXT,
  status TEXT,
  filed_date DATE,
  status_date DATE,
  source_url TEXT
);

CREATE TABLE IF NOT EXISTS dob_violations (
  id SERIAL PRIMARY KEY,
  bbl TEXT,
  violation_number TEXT,
  status TEXT,
  issue_date DATE,
  source_url TEXT
);

CREATE TABLE IF NOT EXISTS zoning (
  id SERIAL PRIMARY KEY,
  bbl TEXT,
  district TEXT
);

-- Demo rows (safe to re-run)
DELETE FROM dob_permits     WHERE bbl = '1000000001';
DELETE FROM dob_violations  WHERE bbl = '1000000001';
DELETE FROM zoning          WHERE bbl = '1000000001';
DELETE FROM properties      WHERE bbl = '1000000001';

INSERT INTO properties (bbl,address,normalized_address,owner_name,year_built,units_res)
VALUES ('1000000001','123 MAIN ST','123 MAIN ST','ACME HOLDINGS LLC',1930,12);

INSERT INTO dob_permits (bbl,job_number,status,filed_date,status_date,source_url) VALUES
('1000000001','B123456789','ISSUED','2024-01-15','2024-02-01','https://a810-bisweb.nyc.gov/permits'),
('1000000001','B987654321','SIGNED OFF','2023-09-10','2023-10-03','https://a810-bisweb.nyc.gov/permits');

INSERT INTO dob_violations (bbl,violation_number,status,issue_date,source_url) VALUES
('1000000001','V-001','OPEN','2023-11-20','https://a810-bisweb.nyc.gov/violations'),
('1000000001','V-002','CLOSED','2022-05-01','https://a810-bisweb.nyc.gov/violations');

INSERT INTO zoning (bbl,district) VALUES ('1000000001','R7-2');

-- make sure view can be recreated even if its columns changed
DROP VIEW IF EXISTS permits_violations CASCADE;

-- force canonical column names
CREATE VIEW permits_violations
  (id, bbl, kind, filed_at, status_at, status, ref, source_url) AS
SELECT
  p.id,
  p.bbl,
  'permit'::text     AS kind,
  p.filed_date       AS filed_at,
  p.status_date      AS status_at,
  p.status,
  p.job_number       AS ref,
  p.source_url
FROM dob_permits p
UNION ALL
SELECT
  v.id,
  v.bbl,
  'violation'::text  AS kind,
  v.issue_date       AS filed_at,
  NULL::date         AS status_at,
  v.status,
  v.violation_number AS ref,
  v.source_url
FROM dob_violations v;
