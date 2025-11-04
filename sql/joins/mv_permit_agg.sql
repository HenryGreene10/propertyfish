CREATE MATERIALIZED VIEW IF NOT EXISTS public.mv_permit_agg AS
SELECT
  bbl_norm,
  COUNT(*) FILTER (WHERE event_date >= current_date - INTERVAL '12 months') AS permit_count_12m,
  MAX(event_date) AS last_permit_date
FROM public.vw_permits_norm
WHERE bbl_norm IS NOT NULL
GROUP BY bbl_norm;

CREATE UNIQUE INDEX IF NOT EXISTS ux_permit_agg_bbl ON public.mv_permit_agg (bbl_norm);
