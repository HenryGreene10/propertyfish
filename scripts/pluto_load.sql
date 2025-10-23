\echo 'TOMBSTONED: scripts/pluto_load.sql has been retired. See CODE_TOMBSTONES.md for details.'

DO $$
BEGIN
    RAISE EXCEPTION 'scripts/pluto_load.sql has been retired. Use backend/app/ingestion/pluto.py instead.';
END $$;
