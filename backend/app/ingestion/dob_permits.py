from app.ingestion.framework import run_job


def run(conn, days_back: int = 7, page_size: int = 50000) -> None:
    """
    Backward-compatible entrypoint for DOB permits ingestion.
    """
    run_job(conn, "dob_permits", days_back=days_back, page_size=page_size)
