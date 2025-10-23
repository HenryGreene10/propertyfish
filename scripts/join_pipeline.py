#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, Sequence

from dotenv import load_dotenv

try:
    from psycopg2.errors import UndefinedTable
except ImportError:  # pragma: no cover
    UndefinedTable = Exception

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = REPO_ROOT / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from app.db.connection import get_conn  # noqa: E402


def _load_environment() -> None:
    load_dotenv(REPO_ROOT / ".env", override=False)
    load_dotenv(REPO_ROOT / "backend" / ".env", override=False)


def _validate_identifier(value: str, *, param: str) -> str:
    token = (value or "").strip()
    if not token:
        raise SystemExit(f"[join_pipeline] {param} cannot be empty.")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.")
    if any(ch not in allowed for ch in token):
        raise SystemExit(
            f"[join_pipeline] {param} '{value}' contains invalid characters. "
            "Use plain table identifiers (letters, numbers, underscore, dot)."
        )
    return token


def _detect_geom_column(conn, table: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND udt_name = 'geometry'
            ORDER BY ordinal_position
            """,
            (table,),
        )
        rows = cur.fetchall()

    geom_columns: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            geom_columns.append(row.get("column_name"))
        elif isinstance(row, (list, tuple)):
            geom_columns.append(row[0])
        else:
            geom_columns.append(row)
    geom_columns = [c for c in geom_columns if c]
    return geom_columns[0] if geom_columns else None


def _ensure_parcels_view(conn, source_table: str) -> None:
    raw_table = _validate_identifier(source_table, param="--parcels-table")
    table = raw_table.split(".")[-1]
    qualified = f"public.{table}"
    hint = (
        'psql "$DATABASE_URL" -c '
        f'"DROP VIEW IF EXISTS parcels; CREATE VIEW parcels AS SELECT * FROM {qualified};"'
    )

    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (qualified,))
        row = cur.fetchone()

    regclass = None
    if isinstance(row, dict):
        regclass = row.get("to_regclass")
    elif isinstance(row, (list, tuple)):
        regclass = row[0] if row else None
    else:
        regclass = row
    if not regclass:
        raise SystemExit(
            f"[join_pipeline] Source parcels table '{qualified}' not found. "
            "Confirm --parcels-table points to a real relation."
        )

    geom_column = _detect_geom_column(conn, table)
    if geom_column and geom_column != "geom":
        print(
            f"[join_pipeline] Hint: {hint}\n"
            f"[join_pipeline] Normalizing geometry column '{geom_column}' to geom in view.",
            file=sys.stderr,
        )
    elif not geom_column:
        print(
            f"[join_pipeline] Hint: {hint}\n"
            f"[join_pipeline] Warning: '{table}' has no geometry column; spatial joins may fail.",
            file=sys.stderr,
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.relkind
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = 'parcels' AND n.nspname = 'public'
            """
        )
        rel_row = cur.fetchone()

    relkind = None
    if isinstance(rel_row, dict):
        relkind = rel_row.get("relkind")
    elif isinstance(rel_row, (list, tuple)):
        relkind = rel_row[0] if rel_row else None

    statements: list[str] = []
    if relkind in {"r", "m"}:
        drop_stmt = (
            "DROP MATERIALIZED VIEW IF EXISTS public.parcels CASCADE;"
            if relkind == "m"
            else "DROP TABLE IF EXISTS public.parcels CASCADE;"
        )
        statements.append(drop_stmt)

    if geom_column and geom_column != "geom":
        statements.append(
            f"CREATE OR REPLACE VIEW public.parcels AS SELECT *, {geom_column}::geometry AS geom FROM {qualified};"
        )
    else:
        statements.append(f"CREATE OR REPLACE VIEW public.parcels AS SELECT * FROM {qualified};")

    with conn.cursor() as cur:
        for stmt in statements:
            cur.execute(stmt)
    conn.commit()


def _ensure_tables(conn, tables: Sequence[str]) -> None:
    missing: list[str] = []
    with conn.cursor() as cur:
        for table in tables:
            cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
            row = cur.fetchone()
            exists = None
            if isinstance(row, dict):
                exists = row.get("to_regclass")
            elif isinstance(row, (list, tuple)):
                exists = row[0] if row else None
            else:
                exists = row
            if not exists:
                missing.append(table)
    if missing:
        missing.sort()
        hint = (
            "[join_pipeline] Missing table '{table}'. Run ingest first or load schema, e.g. "
            "psql \"$DATABASE_URL\" -f backend/app/db/schema.sql"
        )
        for table in missing:
            print(hint.format(table=table), file=sys.stderr)
        sys.exit(2)


def _order_join_paths(paths: list[Path]) -> list[Path]:
    head = [p for p in paths if p.name.lower() == "vw_socrata_norm.sql"]
    tail = sorted(
        [p for p in paths if p.name.lower() != "vw_socrata_norm.sql"],
        key=lambda p: p.name.lower(),
    )
    return head + tail


def _read_sql_files(paths: Iterable[Path]) -> list[tuple[Path, str]]:
    statements: list[tuple[Path, str]] = []
    for path in paths:
        sql = path.read_text(encoding="utf-8").strip()
        if sql:
            statements.append((path, sql))
    return statements


def _apply_sql(conn, statements: list[tuple[Path, str]]) -> None:
    with conn.cursor() as cur:
        for path, sql in statements:
            try:
                cur.execute(sql)
                print(f"[join_pipeline] ensured view from {path.relative_to(REPO_ROOT)}")
            except UndefinedTable as exc:  # type: ignore[misc]
                message = str(exc)
                if "vw_socrata_norm" in message:
                    print(
                        "[join_pipeline] vw_socrata_norm is missing; ensure it is created before dependent views.",
                        file=sys.stderr,
                    )
                    print(
                        'Hint: psql "$DATABASE_URL" -f sql/joins/vw_socrata_norm.sql',
                        file=sys.stderr,
                    )
                raise
    conn.commit()


def _fetch_metrics(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM vw_join_coverage_summary")
        row = cur.fetchone()
        if not row:
            return {}
    return dict(row)


def _print_metrics(metrics: dict[str, object]) -> None:
    total = metrics.get("total_rows") or 0
    matched = metrics.get("matched_count") or 0
    unmatched = metrics.get("unmatched_count") or 0
    stage1 = metrics.get("stage1_count") or 0
    stage2 = metrics.get("stage2_count") or 0
    stage3 = metrics.get("stage3_count") or 0

    def _pct(value) -> str:
        if not total or value is None:
            return "n/a"
        return f"{(value or 0) / total:.1%}"

    print("\n[join_pipeline] Coverage metrics")
    print(f"  total rows      : {total}")
    print(f"  matched rows    : {matched} ({_pct(matched)})")
    print(f"  unmatched rows  : {unmatched} ({_pct(unmatched)})")
    print(f"  stage1 matches  : {stage1} ({_pct(metrics.get('stage1_count'))})")
    print(f"  stage2 matches  : {stage2} ({_pct(metrics.get('stage2_count'))})")
    print(f"  stage3 matches  : {stage3} ({_pct(metrics.get('stage3_count'))})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ensure Socrata→PLUTO join views and report coverage.")
    parser.add_argument(
        "--sql-root",
        default=str(REPO_ROOT / "sql"),
        help="Root directory containing sql/joins and sql/reports (default: %(default)s)",
    )
    parser.add_argument(
        "--parcels-table",
        default="pluto",
        help="Source table/view to expose as parcels (default: %(default)s).",
    )
    parser.add_argument(
        "--enforce-stage1",
        type=float,
        default=None,
        help="Fail if stage1 coverage falls below this decimal threshold (e.g., 0.8).",
    )
    args = parser.parse_args()

    _load_environment()
    sql_root = Path(args.sql_root)
    joins_dir = sql_root / "joins"
    reports_dir = sql_root / "reports"
    if not joins_dir.is_dir():
        raise RuntimeError(f"Expected directory missing: {joins_dir}")
    if not reports_dir.is_dir():
        raise RuntimeError(f"Expected directory missing: {reports_dir}")

    join_paths = _order_join_paths(list(joins_dir.glob("*.sql")))
    report_paths = sorted(reports_dir.glob("*.sql"), key=lambda p: p.name.lower())

    join_statements = _read_sql_files(join_paths)
    report_statements = _read_sql_files(report_paths)

    with get_conn() as conn:
        conn.autocommit = False
        _ensure_parcels_view(conn, args.parcels_table)
        _ensure_tables(conn, ("dob_permits", "parcels"))
        _apply_sql(conn, join_statements + report_statements)
        metrics = _fetch_metrics(conn)

    if not metrics:
        print("[join_pipeline] No coverage metrics returned (views may be empty).")
        return

    _print_metrics(metrics)

    if args.enforce_stage1 is not None:
        stage1_pct = metrics.get("stage1_pct")
        if stage1_pct is None:
            raise SystemExit("Stage1 coverage is undefined; cannot enforce threshold.")
        if stage1_pct < args.enforce_stage1:
            raise SystemExit(
                f"Stage1 coverage {stage1_pct:.3f} is below required threshold {args.enforce_stage1:.3f}"
            )


if __name__ == "__main__":
    main()
