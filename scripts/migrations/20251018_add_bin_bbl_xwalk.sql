-- BIN -> BBL crosswalk used by DOB ingestion
CREATE TABLE IF NOT EXISTS pad_bin_bbl (
  bin  bigint PRIMARY KEY,
  bbl  bigint NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pad_bin_bbl_bbl ON pad_bin_bbl (bbl);
