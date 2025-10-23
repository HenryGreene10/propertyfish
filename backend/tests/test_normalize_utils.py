import os

import psycopg2
import pytest

from app.utils.normalize import normalize_address, normalize_bbl


def test_normalize_bbl_padding_and_borough_alias():
    assert normalize_bbl("Manhattan", "12", "34") == "10001200034"
    assert normalize_bbl("bk", "1", "1") == "3000010001"
    assert normalize_bbl("4", "123", "45") == "40012300045"


def test_normalize_address_queens_hyphen():
    addr = normalize_address(" 41 -2 ", "Main st.")
    assert addr.house_number == "41-02"
    assert addr.street == "MAIN ST"
    assert addr.full == "41-02 MAIN ST"


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not configured for CRS test")
def test_crs_transform_contains():
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ST_Contains(
                    ST_Transform(
                        ST_MakeEnvelope(-73.99, 40.74, -73.98, 40.75, 4326),
                        2263
                    ),
                    ST_Transform(
                        ST_SetSRID(ST_MakePoint(-73.9857, 40.7484), 4326),
                        2263
                    )
                )
                """
            )
            (contains,) = cur.fetchone()
        assert contains is True
    finally:
        conn.close()
