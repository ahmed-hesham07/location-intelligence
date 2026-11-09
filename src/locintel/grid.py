"""0.25° analysis grid for the 7 project countries.

Cell centres sit on the ERA5 0.25° points, so one cell = one ERA5 grid point.
A cell is kept when the project countries cover at least `min_land_frac` of it;
its country is the one with the largest share.

    uv run python -m locintel.grid build            # build, save files, load raw.cells
    uv run python -m locintel.grid build --no-db    # files only
    uv run python -m locintel.grid lookup --lon 29.9187 --lat 31.2001
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
from shapely.geometry import box

from locintel.config import get_settings
from locintel.regions import COUNTRIES, ERA5_AREA, GRID_STEP_DEG

BOUNDARY_URL = (
    "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/"
    "releaseData/gbOpen/{iso}/ADM0/geoBoundaries-{iso}-ADM0.geojson"
)
EQUAL_AREA_CRS = "EPSG:6933"  # WGS 84 / NSIDC EASE-Grid 2.0 Global: equal-area, for area ratios
DEFAULT_MIN_LAND_FRAC = 0.25
CELLS_PER_ROW = int(round(360 / GRID_STEP_DEG))  # 1440 at 0.25°


# --- cell ids -------------------------------------------------------------------------------


def cell_id(lat: float, lon: float, step: float = GRID_STEP_DEG) -> int:
    """Stable integer id of the cell whose centre is nearest to (lat, lon).

    Row 0 is the cell centred on 90°N; column 0 the cell centred on 180°W.
    """
    row = int(round((90.0 - lat) / step))
    col = int(round((lon + 180.0) / step))
    return row * int(round(360 / step)) + col


def cell_centre(cid: int, step: float = GRID_STEP_DEG) -> tuple[float, float]:
    """Inverse of `cell_id`: (lat, lon) of the cell centre."""
    per_row = int(round(360 / step))
    row, col = divmod(cid, per_row)
    return 90.0 - row * step, col * step - 180.0


# --- inputs ---------------------------------------------------------------------------------


def load_countries(cache_dir: Path, countries: tuple[str, ...] = COUNTRIES) -> gpd.GeoDataFrame:
    """geoBoundaries gbOpen ADM0 shapes, downloaded once into `cache_dir`."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for iso in countries:
        path = cache_dir / f"geoBoundaries-{iso}-ADM0.geojson"
        if not path.exists():
            resp = requests.get(BOUNDARY_URL.format(iso=iso), timeout=120)
            resp.raise_for_status()
            if resp.content.startswith(b"version https://git-lfs"):
                raise RuntimeError(f"{iso}: got a Git LFS pointer, not GeoJSON")
            path.write_bytes(resp.content)
        gdf = gpd.read_file(path)[["geometry"]]
        gdf["country_iso3"] = iso
        frames.append(gdf)
    out = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")
    out["geometry"] = out.geometry.make_valid()
    return out.dissolve(by="country_iso3", as_index=False)


def candidate_cells(area: list[float] = ERA5_AREA, step: float = GRID_STEP_DEG) -> gpd.GeoDataFrame:
    """Every cell whose centre lies inside the [N, W, S, E] box."""
    north, west, south, east = area
    lats = np.arange(south, north + step / 2, step)
    lons = np.arange(west, east + step / 2, step)
    half = step / 2
    rows = [
        (
            cell_id(lat, lon, step),
            float(lat),
            float(lon),
            box(lon - half, lat - half, lon + half, lat + half),
        )
        for lat in lats
        for lon in lons
    ]
    return gpd.GeoDataFrame(rows, columns=["cell_id", "lat", "lon", "geometry"], crs="EPSG:4326")


# --- build ----------------------------------------------------------------------------------


def assign_cells(
    cells: gpd.GeoDataFrame,
    countries: gpd.GeoDataFrame,
    min_land_frac: float = DEFAULT_MIN_LAND_FRAC,
) -> gpd.GeoDataFrame:
    """Keep cells with project land share >= `min_land_frac`; tag the largest-share country."""
    cells_ea = cells.to_crs(EQUAL_AREA_CRS)
    countries_ea = countries.to_crs(EQUAL_AREA_CRS)
    cell_area = cells_ea.set_index("cell_id").geometry.area

    # Land share against the union, so overlapping (disputed) shapes are not counted twice.
    union = gpd.GeoDataFrame(geometry=[countries_ea.union_all()], crs=EQUAL_AREA_CRS)
    land = gpd.overlay(cells_ea[["cell_id", "geometry"]], union, how="intersection")
    land_frac = (land.set_index("cell_id").geometry.area / cell_area).reindex(cell_area.index)
    land_frac = land_frac.fillna(0.0).clip(upper=1.0)

    # Country with the largest overlap.
    parts = gpd.overlay(cells_ea[["cell_id", "geometry"]], countries_ea, how="intersection")
    parts["a"] = parts.geometry.area
    best = parts.sort_values("a", ascending=False).drop_duplicates("cell_id")
    country = best.set_index("cell_id")["country_iso3"]

    out = cells.set_index("cell_id")
    out["land_frac"] = land_frac.round(4)
    out["country_iso3"] = country
    out = out[(out["land_frac"] >= min_land_frac) & out["country_iso3"].notna()]
    out = out.reset_index()[["cell_id", "country_iso3", "lat", "lon", "land_frac", "geometry"]]
    return gpd.GeoDataFrame(out, geometry="geometry", crs="EPSG:4326").sort_values("cell_id")


def uncovered_share(cells: gpd.GeoDataFrame, countries: gpd.GeoDataFrame) -> float:
    """Share of project land lying outside all candidate cells (checks the download box)."""
    land = countries.to_crs(EQUAL_AREA_CRS).union_all()
    covered = cells.to_crs(EQUAL_AREA_CRS).union_all()
    return float(land.difference(covered).area / land.area)


# --- outputs --------------------------------------------------------------------------------


def save_files(grid: gpd.GeoDataFrame, countries: gpd.GeoDataFrame, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = [out_dir / "cells.parquet"]
    grid.to_parquet(written[0], index=False)
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed: skipping cells.png")
        return written
    fig, ax = plt.subplots(figsize=(14, 7))
    grid.plot(
        ax=ax,
        column="country_iso3",
        categorical=True,
        legend=True,
        edgecolor="white",
        linewidth=0.1,
        alpha=0.8,
    )
    countries.boundary.plot(ax=ax, color="black", linewidth=0.5)
    ax.set_title(f"locintel 0.25° grid: {len(grid)} cells")
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    png = out_dir / "cells.png"
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    written.append(png)
    return written


DDL = """
CREATE TABLE IF NOT EXISTS raw.cells (
    cell_id      integer PRIMARY KEY,
    country_iso3 char(3) NOT NULL,
    lat          double precision NOT NULL,
    lon          double precision NOT NULL,
    land_frac    real NOT NULL CHECK (land_frac BETWEEN 0 AND 1),
    geom         geometry(Polygon, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS cells_geom_gix ON raw.cells USING gist (geom);
CREATE INDEX IF NOT EXISTS cells_country_ix ON raw.cells (country_iso3);
"""


def load_to_postgres(grid: gpd.GeoDataFrame, dsn: str) -> int:
    """Replace raw.cells with `grid` in one transaction. Returns the row count."""
    import psycopg

    rows = [
        (
            int(r.cell_id),
            r.country_iso3,
            float(r.lat),
            float(r.lon),
            float(r.land_frac),
            r.geometry.wkb,
        )
        for r in grid.itertuples()
    ]
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(DDL)
        cur.execute("TRUNCATE raw.cells")
        cur.executemany(
            "INSERT INTO raw.cells (cell_id, country_iso3, lat, lon, land_frac, geom) "
            "VALUES (%s, %s, %s, %s, %s, ST_GeomFromWKB(%s, 4326))",
            rows,
        )
        cur.execute("SELECT count(*) FROM raw.cells")
        (count,) = cur.fetchone()
    return int(count)


# --- CLI ------------------------------------------------------------------------------------

CHECK_POINTS = {
    "Alexandria": (31.2001, 29.9187),
    "Riyadh": (24.7136, 46.6753),
    "Manama": (26.2235, 50.5876),
}


def build(no_db: bool, min_land_frac: float) -> int:
    settings = get_settings()
    ref_dir = Path(settings.data_dir) / "ref"
    countries = load_countries(ref_dir / "boundaries")
    cands = candidate_cells()
    missing = uncovered_share(cands, countries)
    grid = assign_cells(cands, countries, min_land_frac)

    print(f"candidate cells: {len(cands)}")
    print(f"kept cells (land >= {min_land_frac:.0%}): {len(grid)}")
    print(grid.groupby("country_iso3").size().rename("cells").to_string())
    print(f"project land outside the download box: {missing:.4%}")
    ids = set(grid["cell_id"])
    for name, (lat, lon) in CHECK_POINTS.items():
        cid = cell_id(lat, lon)
        print(f"{name}: cell {cid} centre {cell_centre(cid)} in grid: {cid in ids}")
    for p in save_files(grid, countries, ref_dir):
        print(f"wrote {p}")
    if not no_db:
        print(f"raw.cells rows: {load_to_postgres(grid, settings.postgres_dsn)}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m locintel.grid")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build the grid, save files, load raw.cells")
    b.add_argument("--no-db", action="store_true", help="skip loading into Postgres")
    b.add_argument("--min-land", type=float, default=DEFAULT_MIN_LAND_FRAC)
    lk = sub.add_parser("lookup", help="cell id for a point")
    lk.add_argument("--lon", type=float, required=True)
    lk.add_argument("--lat", type=float, required=True)
    args = parser.parse_args(argv)

    if args.cmd == "build":
        return build(args.no_db, args.min_land)
    cid = cell_id(args.lat, args.lon)
    print(f"cell {cid} centre {cell_centre(cid)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
