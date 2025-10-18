import os
from typing import Any, Dict, Generator, List

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from app.routers import resolve, property as property_router, chat
from app import routes as api_routes
from app.db.connection import get_conn as get_conn_cm
from psycopg2 import errors

app = FastAPI(title="PropertyFish API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(resolve.router, prefix="/resolve", tags=["resolve"])
app.include_router(property_router.router)
app.include_router(property_router.legacy_router)
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(api_routes.router, prefix="/api", tags=["chat-query"])


def get_conn() -> Generator:
    with get_conn_cm() as conn:
        yield conn


@app.get("/search")
def search(
    q: str = Query(..., min_length=1, description="Free-text search query"),
    conn=Depends(get_conn),
):
    q = q.strip()
    if len(q) < 2:
        return []

    like_term = f"%{q}%"
    with conn.cursor() as cur:
        try:
            cur.execute(
                """
                SELECT
                    bbl,
                    address,
                    borough
                FROM pluto
                WHERE address ILIKE %s
                ORDER BY similarity(address, %s) DESC NULLS LAST, address ASC
                LIMIT 10
                """,
                (like_term, q),
            )
            rows = cur.fetchall()
        except errors.UndefinedFunction:
            conn.rollback()
            cur.execute(
                """
                SELECT
                    bbl,
                    address,
                    borough
                FROM pluto
                WHERE address ILIKE %s
                ORDER BY address ASC
                LIMIT 10
                """,
                (like_term,),
            )
            rows = cur.fetchall()

    results: List[Dict[str, Any]] = []
    for row in rows:
        record = {
            "bbl": row["bbl"],
            "address": row["address"],
            "borough": row["borough"],
        }
        results.append(record)

    return results


@app.get("/parcels/{bbl}")
def parcel_detail(bbl: str, conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                bbl,
                address,
                borough,
                zipcode,
                houseno,
                street,
                latitude,
                longitude,
                updated_at
            FROM pluto
            WHERE bbl = %s
            """,
            (bbl,),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Not found")

    data = {
        "bbl": row["bbl"],
        "address": row["address"],
        "borough": row["borough"],
        "zipcode": row["zipcode"],
        "houseno": row["houseno"],
        "street": row["street"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "updated_at": row["updated_at"],
        "latest_permits": [],
    }
    return data


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/version")
def version():
    return {"service": "propertyfish-chat", "env": os.getenv("ENV", "dev")}

@app.get("/")
def root():
    return {"ok": True, "service": "propertyfish"}
