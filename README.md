# location-intelligence

Daily batch pipeline turning ERA5 and CAMS weather and air-quality data into climate, solar-yield and dust-soiling indicators for Egypt and the Gulf.

**Stack:** Airflow · dbt · Postgres + PostGIS · MinIO · pvlib · Streamlit · Terraform (Railway).

See [`docs/PLAN.md`](docs/PLAN.md) for the phased build plan and test gates.

## Quick start

Requires [uv](https://docs.astral.sh/uv/) (installs Python 3.12 itself).

```bash
uv sync
cp .env.example .env   # then fill in keys
uv run ruff check .
uv run pytest
```
