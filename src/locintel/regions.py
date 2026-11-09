"""Project region constants shared by every phase."""

# ISO3 codes of the seven project countries.
COUNTRIES: tuple[str, ...] = ("EGY", "SAU", "ARE", "QAT", "KWT", "BHR", "OMN")

# Download boxes as [North, West, South, East], the order cdsapi expects.
ERA5_AREA: list[float] = [32, 24, 16, 60]
# EAC4 is ~0.75°, so add a 1° margin for interpolation onto edge cells.
EAC4_AREA: list[float] = [33, 23, 15, 61]

GRID_STEP_DEG: float = 0.25
