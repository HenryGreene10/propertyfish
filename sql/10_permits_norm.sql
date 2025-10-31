CREATE OR REPLACE VIEW public.vw_permits_norm AS
SELECT
  p.job_number,
  p.status,
  p.issuance_date::date AS issuance_date,
  p.filing_date::date   AS filing_date,
  p.filed_date::date    AS filed_date,
  p.status_date::date   AS status_date,
  -- replace latest_action_date with COALESCE of real fields
  COALESCE(
    p.issuance_date::date,
    p.filing_date::date,
    p.filed_date::date,
    p.status_date::date
  ) AS event_date,
  CASE
    WHEN p.bbl IS NOT NULL THEN replace(split_part(p.bbl, '.', 1), ' ', '')::bigint
  END AS bbl_norm
FROM public.dob_permits p;
