CREATE OR REPLACE VIEW vw_join_coverage_summary AS
WITH totals AS (
    SELECT COUNT(*)::bigint AS total_rows FROM vw_socrata_norm
),
stage1 AS (
    SELECT COUNT(*)::bigint AS stage1_count FROM vw_join_stage1
),
stage2 AS (
    SELECT COUNT(*)::bigint AS stage2_count FROM vw_join_stage2
),
stage3 AS (
    SELECT COUNT(*)::bigint AS stage3_count FROM vw_join_stage3
),
matched AS (
    SELECT COUNT(*)::bigint AS matched_count
    FROM (
        SELECT job_number FROM vw_join_stage1
        UNION
        SELECT job_number FROM vw_join_stage2
        UNION
        SELECT job_number FROM vw_join_stage3
    ) AS unioned
)
SELECT
    totals.total_rows,
    matched.matched_count,
    (totals.total_rows - matched.matched_count) AS unmatched_count,
    COALESCE(stage1.stage1_count, 0) AS stage1_count,
    COALESCE(stage2.stage2_count, 0) AS stage2_count,
    COALESCE(stage3.stage3_count, 0) AS stage3_count,
    CASE
        WHEN totals.total_rows > 0 THEN stage1.stage1_count::numeric / totals.total_rows
        ELSE NULL
    END AS stage1_pct,
    CASE
        WHEN totals.total_rows > 0 THEN stage2.stage2_count::numeric / totals.total_rows
        ELSE NULL
    END AS stage2_pct,
    CASE
        WHEN totals.total_rows > 0 THEN stage3.stage3_count::numeric / totals.total_rows
        ELSE NULL
    END AS stage3_pct,
    CASE
        WHEN totals.total_rows > 0 THEN matched.matched_count::numeric / totals.total_rows
        ELSE NULL
    END AS matched_pct,
    CASE
        WHEN totals.total_rows > 0 THEN (totals.total_rows - matched.matched_count)::numeric / totals.total_rows
        ELSE NULL
    END AS unmatched_pct
FROM totals
CROSS JOIN matched
CROSS JOIN stage1
CROSS JOIN stage2
CROSS JOIN stage3;
