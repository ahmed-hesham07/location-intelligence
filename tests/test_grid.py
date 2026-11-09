import geopandas as gpd
import pytest
from shapely.geometry import box

from locintel.grid import assign_cells, candidate_cells, cell_centre, cell_id
from locintel.regions import ERA5_AREA


def test_cell_id_roundtrip() -> None:
    for lat, lon in [(31.25, 29.75), (16.0, 24.0), (32.0, 60.0), (-89.75, -180.0)]:
        assert cell_centre(cell_id(lat, lon)) == (lat, lon)


def test_point_maps_to_nearest_centre() -> None:
    # Alexandria [29.9187, 31.2001] -> centre (31.25, 30.0)
    assert cell_centre(cell_id(31.2001, 29.9187)) == (31.25, 30.0)


def test_candidates_aligned_and_unique() -> None:
    cells = candidate_cells()
    north, west, south, east = ERA5_AREA
    assert len(cells) == 65 * 145
    assert cells["cell_id"].is_unique
    assert ((cells["lat"] * 4) % 1 == 0).all() and ((cells["lon"] * 4) % 1 == 0).all()
    assert cells["lat"].between(south, north).all() and cells["lon"].between(west, east).all()


@pytest.fixture
def small_cells() -> gpd.GeoDataFrame:
    return candidate_cells(area=[1.0, 0.0, 0.0, 1.0])  # 5 x 5 cells around the equator


def _countries(*shapes: tuple[str, tuple[float, float, float, float]]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"country_iso3": [iso for iso, _ in shapes]},
        geometry=[box(*b) for _, b in shapes],
        crs="EPSG:4326",
    )


def test_land_threshold(small_cells: gpd.GeoDataFrame) -> None:
    # Land covers x <= 0.5. Cell centred on x=0.5 spans 0.375..0.625 -> 50% land (kept);
    # cell centred on x=0.75 spans 0.625..0.875 -> 0% land (dropped).
    grid = assign_cells(small_cells, _countries(("EGY", (-1, -1, 0.5, 2))), min_land_frac=0.25)
    assert set(grid["lon"]) == {0.0, 0.25, 0.5}
    half = grid[grid["lon"] == 0.5]["land_frac"]
    assert half.between(0.49, 0.51).all()


def test_threshold_excludes_small_overlap(small_cells: gpd.GeoDataFrame) -> None:
    # Land to x=0.4: cell at 0.5 (0.375..0.625) has 10% land -> dropped at 25%.
    grid = assign_cells(small_cells, _countries(("EGY", (-1, -1, 0.4, 2))), min_land_frac=0.25)
    assert 0.5 not in set(grid["lon"])


def test_country_is_largest_share(small_cells: gpd.GeoDataFrame) -> None:
    # Border at x=0.55 inside the cell centred on 0.5: EGY has 70%, SAU 30%.
    grid = assign_cells(
        small_cells,
        _countries(("EGY", (-1, -1, 0.55, 2)), ("SAU", (0.55, -1, 2, 2))),
        min_land_frac=0.25,
    )
    border = grid[grid["lon"] == 0.5]
    assert (border["country_iso3"] == "EGY").all()
    assert border["land_frac"].between(0.99, 1.0).all()  # both countries count as land


def test_overlapping_claims_not_double_counted(small_cells: gpd.GeoDataFrame) -> None:
    grid = assign_cells(
        small_cells,
        _countries(("EGY", (-1, -1, 2, 2)), ("SAU", (-1, -1, 2, 2))),
        min_land_frac=0.25,
    )
    assert (grid["land_frac"] <= 1.0).all()
    assert grid["cell_id"].is_unique
