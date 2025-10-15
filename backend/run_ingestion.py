import os
import sys

from sqlalchemy import create_engine

from app.ingestion.dob_permits import run as run_dob_permits


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        raise SystemExit("Usage: python backend/run_ingestion.py <job>")

    job_name = args[0]
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required.")

    engine = create_engine(database_url, future=True)

    if job_name == "dob_permits":
        with engine.begin() as conn:
            run_dob_permits(conn, days_back=7)
    else:
        raise ValueError(f"Unknown ingestion job: {job_name}")


if __name__ == "__main__":
    main()
