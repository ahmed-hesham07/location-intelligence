"""Check the local stack: `uv run python -m locintel.healthcheck`.

Exits 0 when Postgres has PostGIS and the three schemas, and every lake bucket exists.
"""

import sys

import psycopg

from locintel.config import Settings, get_settings
from locintel.load.lake import s3_client

REQUIRED_SCHEMAS = {"raw", "staging", "marts"}


def check_postgres(settings: Settings) -> list[str]:
    errors: list[str] = []
    with psycopg.connect(settings.postgres_dsn, connect_timeout=5) as conn:
        version = conn.execute("SELECT postgis_lib_version()").fetchone()
        print(f"postgres: PostGIS {version[0] if version else '?'}")
        rows = conn.execute(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name = ANY(%s)",
            (list(REQUIRED_SCHEMAS),),
        ).fetchall()
        found = {r[0] for r in rows}
        print(f"postgres: schemas {sorted(found)}")
        missing = REQUIRED_SCHEMAS - found
        if missing:
            errors.append(f"missing schemas: {sorted(missing)}")
    return errors


def check_lake(settings: Settings) -> list[str]:
    s3 = s3_client(settings)
    found = {b["Name"] for b in s3.list_buckets().get("Buckets", [])}
    print(f"lake: buckets {sorted(found)}")
    missing = set(settings.bucket_names) - found
    if missing:
        return [f"missing buckets: {sorted(missing)} (run: python -m locintel.load.lake init)"]
    return []


def main() -> int:
    settings = get_settings()
    errors: list[str] = []
    for name, check in (("postgres", check_postgres), ("lake", check_lake)):
        try:
            errors += check(settings)
        except Exception as exc:  # noqa: BLE001 - report any connection failure plainly
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    for e in errors:
        print(f"FAIL {e}")
    print("OK" if not errors else "FAILED")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
