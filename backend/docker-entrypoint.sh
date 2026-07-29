#!/usr/bin/env sh
# Applies database migrations, then hands off to the process in CMD.
set -eu

echo "waiting for the database…"
python - <<'PY'
import asyncio
import sys

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from app.core.config import get_settings


async def wait() -> None:
    url = get_settings().database_url
    for attempt in range(60):
        engine = create_async_engine(url)
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            await engine.dispose()
            print("database is ready")
            return
        except Exception as exc:  # noqa: BLE001 - retry loop, the error is transient
            await engine.dispose()
            if attempt % 10 == 0:
                print(f"database not ready yet ({exc.__class__.__name__})")
            await asyncio.sleep(1)
    print("database did not become ready in time", file=sys.stderr)
    sys.exit(1)


asyncio.run(wait())
PY

echo "applying migrations…"
alembic upgrade head

exec "$@"
