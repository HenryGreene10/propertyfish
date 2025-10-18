import os
import sys

from sqlalchemy import create_engine

from app.ingestion.dob_permits import run as legacy_dob_permits_run
from app.ingestion.framework import get_catalog, run_job
from app.ingestion.pluto import run as run_pluto


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        raise SystemExit("Usage: python -m app.ingestion.orchestrator <job> [days_back]")

    job_name = args[0]
    extras = args[1:]
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required.")

    engine = create_engine(database_url, future=True)

    if job_name == "pluto":
        dry_run = False
        if "--dry-run" in extras:
            dry_run = True
            extras = [arg for arg in extras if arg != "--dry-run"]
        if extras:
            raise ValueError(f"Unexpected arguments for pluto job: {extras}")
        raw_conn = engine.raw_connection()
        try:
            run_pluto(raw_conn, dry_run=dry_run)
        finally:
            raw_conn.close()
        return

    days_back = _resolve_days_back(job_name, extras)

    catalog = get_catalog()

    if job_name in catalog:
        with engine.begin() as conn:
            run_job(conn, job_name, days_back=days_back)
        return

    if job_name == "dob_permits":
        with engine.begin() as conn:
            legacy_dob_permits_run(conn, days_back=days_back)
        return

    raise ValueError(f"Unknown ingestion job: {job_name}")


def _resolve_days_back(job_name: str, extra_args: list[str]) -> int:
    if extra_args:
        try:
            return int(extra_args[0])
        except ValueError as exc:
            raise ValueError(f"Invalid days_back value '{extra_args[0]}'") from exc

    env_value = os.getenv("DAYS_BACK_DEFAULT")
    if env_value:
        try:
            return int(env_value)
        except ValueError:
            pass

    # Legacy default for DOB permits was 7 days.
    if job_name == "dob_permits":
        return 7

    return 3


if __name__ == "__main__":
    main()
