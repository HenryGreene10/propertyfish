import os, asyncio, asyncpg

SQL = "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_property_search;"

async def main():
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise SystemExit("DATABASE_URL not set")
    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2, command_timeout=600)
    async with pool.acquire() as conn:
        await conn.execute(SQL)
    await pool.close()
    print("MV refresh complete")

if __name__ == "__main__":
    asyncio.run(main())
