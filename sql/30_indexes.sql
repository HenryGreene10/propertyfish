-- PLUTO (adjust names if yours differ)
CREATE INDEX IF NOT EXISTS idx_pluto_bbl ON public.pluto(bbl);
-- drop/skip any broken cast indexes, then:
CREATE INDEX IF NOT EXISTS idx_pluto_bbl_norm ON public.pluto (public.bbl_normalize(bbl));
CREATE INDEX IF NOT EXISTS idx_pluto_boro_code ON public.pluto (public.borough_to_code(borough));
CREATE INDEX IF NOT EXISTS idx_pluto_addr_key ON public.pluto (
  UPPER(REGEXP_REPLACE(COALESCE(houseno::text,'') || ' ' || COALESCE(street,''), '\s+',' ','g'))
);
-- spatial helper (cheap-ish)
CREATE INDEX IF NOT EXISTS idx_pluto_geom_wgs84 ON public.pluto USING GIST (ST_Transform(ST_SetSRID(ST_MakePoint(longitude,latitude),4326),2263));

-- Permits (what you actually have)
CREATE INDEX IF NOT EXISTS idx_dp_job_number   ON public.dob_permits (job_number);
CREATE INDEX IF NOT EXISTS idx_dp_bbl          ON public.dob_permits (bbl);
CREATE INDEX IF NOT EXISTS idx_dp_bbl_norm     ON public.dob_permits (public.bbl_normalize(bbl));
CREATE INDEX IF NOT EXISTS idx_dp_filed_date   ON public.dob_permits (filed_date);
CREATE INDEX IF NOT EXISTS idx_dp_status_date  ON public.dob_permits (status_date);

-- Violations
CREATE INDEX IF NOT EXISTS idx_dv_violation_number ON public.dob_violations (violation_number);
CREATE INDEX IF NOT EXISTS idx_dv_bbl              ON public.dob_violations (bbl);
CREATE INDEX IF NOT EXISTS idx_dv_bbl_norm         ON public.dob_violations (public.bbl_normalize(bbl));
CREATE INDEX IF NOT EXISTS idx_dv_issue_date       ON public.dob_violations (issue_date);
CREATE INDEX IF NOT EXISTS idx_dv_disp_date        ON public.dob_violations (disposition_date);
