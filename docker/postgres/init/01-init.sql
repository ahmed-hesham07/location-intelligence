-- Runs once, when the Postgres data volume is empty.
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS raw;      -- loaded as-is from Parquet
CREATE SCHEMA IF NOT EXISTS staging;  -- dbt staging + intermediate models
CREATE SCHEMA IF NOT EXISTS marts;    -- dbt marts read by the app
