# Location Intelligence Platform: phased build plan

A daily batch pipeline that turns weather and air-quality data into precomputed climate, solar and dust indicators for a 0.25° grid over Egypt and the Gulf, with an LLM that answers questions using only those numbers.

Each phase ends with a **manual test gate**. Do not start the next phase until every box in the gate is ticked.

## Branches

| Branch | Purpose | Who merges into it |
|---|---|---|
| `main` | Verified releases only: automated + manual tests passed | Owner only |
| `dev` | **v1** work: 0.25° grid, ERA5 + CAMS, Phases 0–13 in this file | Day-to-day |
| `dev-v2` | **v2** work: city-level layer — see `docs/PLAN_V2.md` on that branch | Day-to-day, rebased on `dev` |

v1 comes first. `dev-v2` holds the v2 plan now; v2 code starts only after v1 Phase 11 is done (Rule 5).

## Rules

1. Every step is a plain Python CLI first (`python -m locintel...`). Airflow wraps it only after it works by hand.
2. Users read **precomputed** marts only. No live data calls per question.
3. Every number the LLM says must exist in the cell's JSON. The validator rejects anything else.
4. No Earth Engine in v1.
5. Nothing new until Phase 11 is done. v2 ideas go into `docs/PLAN_V2.md` on `dev-v2`, not into v1.

## Stack

| Layer | Tool | Runs where |
|---|---|---|
| Language | Python 3.12, `uv` or `pip` + `pyproject.toml` | Local |
| Ingestion | `cdsapi`, `requests`, `xarray` + `cfgrib`/`netCDF4`, `pyarrow` | Local (Docker) |
| Data lake | **RustFS** (S3-compatible), buckets `raw/`, `staged/`, Parquet partitioned by date | Local (Docker) |
| Warehouse | **Postgres 16 + PostGIS** — schemas `raw`, `staging`, `marts` | Local (Docker) |
| Transform + tests | dbt-core + **dbt-postgres** | Local |
| Orchestration | Apache Airflow 3 (Docker Compose) | Local only (too RAM-heavy for Railway) |
| Solar + dust maths | pvlib, pandas | Python step in Airflow |
| Grid | geopandas + geoBoundaries country shapes → PostGIS `cells` table | Local |
| Serving DB | Postgres + PostGIS holding **marts only** | **Railway** |
| App | Streamlit + pydeck, LLM API (Claude or Groq) | **Railway** |
| IaC | Terraform, community Railway provider (`terraform-community-providers/railway`) | Railway project, services, variables |
| CI | GitHub Actions: ruff, pytest, `dbt build` against a Postgres service container, `terraform validate` | GitHub |

### Data flow

```text
CDS (ERA5) ─┐
ADS (CAMS) ─┼─► extract (Python) ─► RustFS raw/ ─► staged Parquet ─► Postgres raw ─► dbt ─► marts
Open-Meteo ─┘                                                                         │
                                                              pvlib (solar, soiling) ◄┘
                                                                         │
                                         sync marts ─► Railway Postgres ─► Streamlit + LLM
PVGIS / NASA POWER: validation only, never inputs.
```

### Cost notes

- Local Docker: free.
- Railway Hobby plan: about USD 5/month base, billed on RAM/CPU/volume. Set a **usage limit in the Railway dashboard** on day one (Terraform does not manage billing limits).
- Keep hourly data in the lake (RustFS) only; load **daily** aggregates into Postgres.

---

## Phase 0 — Repo skeleton

Build:
- [x] `pyproject.toml` (package `locintel`, ruff, pytest config)
- [x] Folder layout (see bottom of this file)
- [x] `.env.example` with every variable name, no values
- [x] One trivial test

Gate:
- [x] `ruff check .` passes
- [x] `pytest` passes
- [x] `.env` is in `.gitignore`

## Phase 1 — Local infrastructure (Docker Compose)

Build:
- [x] `docker-compose.yml`: `postgis/postgis:16-3.7`, `rustfs/rustfs:1.0.4`
- [x] `python -m locintel.load.lake init` creates buckets `raw`, `staged` (idempotent)
- [x] SQL init script: schemas `raw`, `staging`, `marts`; `CREATE EXTENSION postgis`
- [x] `locintel.config` reads `.env` (pydantic-settings, secrets hidden)
- [x] `python -m locintel.healthcheck` checks PostGIS, schemas and buckets

Gate:
- [x] `docker compose up -d --wait` exits 0; `postgres` and `rustfs` healthy
- [x] `uv run python -m locintel.load.lake init` → both buckets `created` (second run: `exists`)
- [x] `uv run python -m locintel.healthcheck` prints `OK`
- [ ] RustFS console (`http://localhost:9001/rustfs/console/`) shows buckets `raw` and `staged`
- [x] `docker compose down && docker compose up -d --wait` keeps data (volumes work)

> MinIO was dropped: its free Docker images were withdrawn in late 2025. RustFS is S3-compatible, so the Python code (boto3) is the same.

## Phase 2 — Grid

Build:
- [ ] `locintel/grid.py`: 0.25° cells aligned to ERA5 (cell centres on .00/.25/.50/.75), clipped to EGY, SAU, ARE, QAT, KWT, BHR, OMN (geoBoundaries ADM0)
- [ ] Columns: `cell_id`, `country_iso3`, `lat`, `lon`, `geom` (polygon, EPSG:4326)
- [ ] CLI: `python -m locintel.grid build` → loads `raw.cells`
- [ ] pytest: alignment, no duplicate `cell_id`, every cell has a country

Gate:
- [ ] Cell count in the expected range (~6,000) — record the exact number
- [ ] Plot (QGIS or a geopandas PNG): no sea cells, no holes, Bahrain present
- [ ] Alexandria `[29.9187, 31.2001]` falls in exactly one cell

## Phase 3 — ERA5 extract (one day, local file)

Prereq: CDS account, key in `~/.cdsapirc`, ERA5 single-levels licence accepted.

Build:
- [ ] `locintel/extract/era5.py`: request one day, region bbox, variables: `2m_temperature`, `2m_dewpoint_temperature`, `total_precipitation`, `10m_u/v_component_of_wind`, `total_cloud_cover`, `surface_solar_radiation_downwards`, `surface_pressure`
- [ ] Hourly → daily aggregates per cell (mean/min/max/sum), unit conversion (K→°C, m→mm, J/m²→kWh/m²), RH from Magnus formula
- [ ] Write Parquet to `data/` (local) first
- [ ] pytest: unit conversions, 24 hours present, accumulated-variable handling, UTC

Gate:
- [ ] `python -m locintel.extract.era5 --date 2025-07-15` produces one Parquet file
- [ ] Row count = cells × 1
- [ ] Alexandria on 2025-07-15: Tmax 28–35 °C, GHI 7–8.5 kWh/m², rain ≈ 0
- [ ] Riyadh on the same day: Tmax > 40 °C

## Phase 4 — Load: lake (RustFS) → Postgres

Build:
- [ ] `locintel/load/lake.py`: upload raw file + Parquet to RustFS (`raw/era5/date=YYYY-MM-DD/`)
- [ ] `locintel/load/warehouse.py`: Parquet → `raw.era5_daily` (idempotent: delete-then-insert per date)
- [ ] Table partitioned by month (declarative partitioning) or indexed on `(date, cell_id)`

Gate:
- [ ] Files visible in RustFS console under the right prefix
- [ ] `SELECT COUNT(*) FROM raw.era5_daily WHERE date = '2025-07-15'` = cell count
- [ ] Running the load twice gives the same count (no duplicates)

## Phase 5 — Airflow

Build:
- [ ] Add Airflow 3 to `docker-compose.yml`
- [ ] `dags/ingest_era5.py`: TaskFlow `extract → upload → load`, retries 3, `catchup` for backfill, ERA5 lag of ~5 days handled (run for `today - 6d`)

Gate:
- [ ] DAG appears in UI with no import errors
- [ ] Manual trigger succeeds
- [ ] Backfill 7 days → 7 × cell count rows
- [ ] Break the CDS key on purpose → task retries, then fails visibly
- [ ] Backfill 1 year, check row count

## Phase 6 — dbt + climate mart

Build:
- [ ] dbt project, `dbt-postgres` profile reading `.env`
- [ ] `staging/stg_era5_daily` → `intermediate/int_climate_daily` → `marts/mart_climate_monthly`
- [ ] Indicators: mean/max temp, days > 40 °C, rain mm, RH, wind speed + dominant direction, cloud cover %
- [ ] Tests: unique `(cell_id, date)`, not null, accepted ranges (temp −20…60 °C, rain ≥ 0), source freshness < 7 days

Gate:
- [ ] `dbt build` passes
- [ ] Alexandria July: mean Tmax ≈ 30 °C, days > 40 °C ≈ 0
- [ ] Riyadh July: days > 40 °C ≥ 20
- [ ] `dbt docs generate && dbt docs serve` opens the lineage graph
- [ ] Backfill to 5 years

## Phase 7 — Dust and air quality

Prereq: ADS account, EAC4 licence accepted.

Build:
- [ ] `extract/cams_eac4.py`: PM2.5, PM10, dust AOD 550 nm history (3-hourly → daily)
- [ ] `extract/openmeteo_aq.py`: recent daily PM2.5, PM10, dust (respect 10,000 calls/day — batch by cell centres)
- [ ] Regrid CAMS (~0.75° EAC4 / 0.4° Open-Meteo) to the 0.25° cells (nearest or bilinear — document which)
- [ ] Units: store µg/m³; convert to g/m³ only inside the soiling step (× 1e-6 from µg/m³)
- [ ] dbt: `stg_cams_daily`, `mart_air_quality_monthly` + range tests
- [ ] DAG `ingest_cams.py`

Gate:
- [ ] Unit tests pass (kg/m³ → µg/m³ = × 1e9)
- [ ] Gulf PM10 monthly means mostly 50–300 µg/m³; spikes on known dust-storm dates
- [ ] EAC4 and Open-Meteo agree within reason on an overlap month

## Phase 8 — Solar yield

Build:
- [ ] `models/solar.py` (pvlib): GHI → DNI/DHI (Erbs or DISC), POA transposition, cell temperature, PVWatts losses; tilts 0–40° step 1°, azimuth 180°
- [ ] Output `marts.mart_solar_monthly`: kWh/kWp per month and year, best tilt
- [ ] `scripts/pvgis_compare.py`: PVcalc for 20 sample cells

Gate:
- [ ] Best tilt ≈ latitude ± 5° for most cells
- [ ] Annual yield in 1,600–2,100 kWh/kWp range for the region
- [ ] PVGIS gap per cell written to README (target: mean |gap| < 10%)

## Phase 9 — Soiling and cleaning

Build:
- [ ] `models/soiling.py`: `pvlib.soiling.hsu` with PM2.5/PM10 (g/m³), rain threshold, cleaning when loss ≥ 5%
- [ ] `marts.mart_soiling_monthly`: mean daily loss %, suggested cleaning interval (days, as a range)

Gate:
- [ ] A day with rain above threshold resets soiling to ~0
- [ ] Soiling ratio never below ~0.66 (known HSU floor) — documented
- [ ] Gulf cells clean more often than Mediterranean-coast Egypt cells

## Phase 10 — Railway + app + LLM

Build:
- [ ] `infra/` Terraform (Railway provider): project, `postgres` service (PostGIS image + volume), `app` service, variables, domain. Verify which resources the provider supports before writing; fall back to dashboard for anything it lacks
- [ ] `scripts/sync_marts.py`: copy `marts` schema local → Railway (`pg_dump -n marts | psql`) — also an Airflow task
- [ ] `app/`: Streamlit + pydeck map, click cell → indicator panels
- [ ] Question box: cell JSON + question → LLM → number validator → re-prompt up to 3× → refuse
- [ ] Secrets only in Railway variables

Gate:
- [ ] `terraform plan` clean, `terraform apply` creates services
- [ ] Railway Postgres has `marts` tables with the same row counts as local
- [ ] Public URL loads; clicking Alexandria shows its numbers
- [ ] A test where the LLM is forced to output a fake number → rejected
- [ ] Railway usage limit set in dashboard

## Phase 11 — Production polish

Build:
- [ ] GitHub Actions: ruff, pytest, `dbt build` on a Postgres service container with seed data, `terraform validate`
- [ ] Airflow failure email alerts; dbt test failure stops the DAG
- [ ] README: problem, architecture, how to run, PVGIS comparison, limits (dust is modelled; HSU floor)

Gate:
- [ ] CI green on a PR
- [ ] A broken dbt test blocks the run and sends an email
- [ ] A fresh clone + README steps → running stack
- [ ] Demo video recorded

## Phase 12–13 — Forecasting (after v1)

- [ ] Daily: Open-Meteo 16-day forecast + CAMS dust forecast, append-only by issue date
- [ ] Monthly: Copernicus seasonal forecasts + 1993–2016 hindcasts
- [ ] Correction model vs ERA5, mapped to 0.25° grid
- [ ] Score vs 10-year average; hide forecasts that don't beat it
- [ ] App shows ranges; LLM states uncertainty

Gate: forecast skill score recorded in README.

---

## Repo layout

```text
location-intelligence/
├── README.md
├── docker-compose.yml        # Postgres+PostGIS, RustFS, Airflow
├── .env.example
├── pyproject.toml
├── .github/workflows/ci.yml
├── infra/                    # Terraform: Railway
├── docker/                   # Postgres init SQL, Dockerfiles
├── dags/
├── src/locintel/
│   ├── config.py
│   ├── grid.py
│   ├── extract/              # era5, cams_eac4, openmeteo_aq
│   ├── load/                 # lake (RustFS/S3), warehouse (Postgres)
│   └── models/               # solar, soiling
├── dbt/models/{staging,intermediate,marts}/
├── app/                      # Streamlit + LLM
├── scripts/                  # pvgis_compare, sync_marts
├── docs/PLAN.md
└── tests/
```
