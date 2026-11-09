from locintel import __version__
from locintel.regions import COUNTRIES, EAC4_AREA, ERA5_AREA, GRID_STEP_DEG


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_seven_countries() -> None:
    assert len(COUNTRIES) == 7
    assert len(set(COUNTRIES)) == 7


def test_area_order_is_north_west_south_east() -> None:
    for north, west, south, east in (ERA5_AREA, EAC4_AREA):
        assert north > south
        assert east > west


def test_eac4_box_contains_era5_box() -> None:
    n, w, s, e = ERA5_AREA
    n2, w2, s2, e2 = EAC4_AREA
    assert n2 >= n and w2 <= w and s2 <= s and e2 >= e


def test_era5_box_aligned_to_grid() -> None:
    for edge in ERA5_AREA:
        assert (edge / GRID_STEP_DEG).is_integer()
