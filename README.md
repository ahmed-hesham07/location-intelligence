# location-intelligence

Daily batch pipeline turning ERA5 and CAMS weather and air-quality data into climate, solar-yield and dust-soiling indicators for Egypt and the Gulf.

**Stack:** Airflow · dbt · Postgres + PostGIS · RustFS (S3) · pvlib · Streamlit · Terraform (Railway).

See [`docs/PLAN.md`](docs/PLAN.md) for the phased build plan and test gates.

## Quick start

Requires [uv](https://docs.astral.sh/uv/) (installs Python 3.12 itself).

```bash
uv sync
cp .env.example .env   # then fill in keys
uv run ruff check .
uv run pytest
```

## Local stack (Phase 1)

Postgres 16 + PostGIS (warehouse) and RustFS (S3-compatible lake) in Docker.

```bash
cp .env.example .env            # set POSTGRES_PASSWORD, S3_ACCESS_KEY, S3_SECRET_KEY
docker compose up -d --wait
uv run python -m locintel.healthcheck   # prints OK
```

| Service | Address |
|---|---|
| Postgres | `localhost:5432` |
| S3 API | `http://localhost:9000` |
| RustFS console | `http://localhost:9001/rustfs/console/` (log in with the S3 keys) |

`docker compose down` keeps data; `docker compose down -v` deletes it.
