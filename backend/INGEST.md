# Running DDL

To install the ingestion and DOB permit tables run:

```bash
psql "$DATABASE_URL" -f scripts/migrations/20251018_add_ingest_and_dob_permits.sql
```

## DOB Permits Ingestion

Run the Socrata-backed ingester with either a rolling window or an explicit start date:

```bash
python scripts/ingest_dob_permits.py --days 7
```

```bash
python scripts/ingest_dob_permits.py --since 2025-01-01
```

Use `--until` to cap the exclusive upper bound or `--dry-run` to validate the window without writing:

```bash
python scripts/ingest_dob_permits.py --days 1 --dry-run
```

Inspect available incremental date fields:

```bash
python scripts/ingest_dob_permits.py --diagnose-date-fields
```

### DOB Complaints Ingestion

- Diagnose schema and date fields  
  ```bash
  python scripts/ingest_dob_complaints.py --diagnose-date-fields
  ```
- Dry-run the upcoming window  
  ```bash
  python scripts/ingest_dob_complaints.py --days 7 --dry-run
  ```
- Backfill the past year  
  ```bash
  python scripts/ingest_dob_complaints.py --days 365
  ```
- Daily incremental run  
  ```bash
  python scripts/ingest_dob_complaints.py --days 1
  ```
