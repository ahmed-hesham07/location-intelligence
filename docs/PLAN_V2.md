# Location Intelligence Platform: v2 plan (city-level layer)

Branch: `dev-v2`. Start code only after v1 Phase 11 is done on `dev`; until then this file is the only v2 work. Rebase `dev-v2` on `dev` before starting.

## Why v2

v1 cells are 0.25° (~28 km). One cell can hold a port, a factory zone and housing. v1 inputs (ERA5 0.25°, CAMS ~0.75°) cannot tell them apart, so v1 does not pretend to. v2 adds data that **can** resolve them, only where it matters: cities.

## Design

- **Two levels.** Keep the v1 0.25° cells as parents. Add fine cells only inside urban/industrial areas.
- **Fine grid:** H3 resolution 8 (~0.74 km², ~0.9 km across) — standard, hierarchical, cheap joins. Each fine cell stores its parent `cell_id`.
- **Inherit, don't invent.** Climate and solar irradiance come from the parent cell. Fine cells add only what fine data actually measures.
- **Precompute monthly, not daily**, at fine level (row count: see Size).

## Fine-level inputs

| Need | Dataset | Resolution | Access |
|---|---|---|---|
| Industrial / residential / commercial | OpenStreetMap `landuse=*`, `building=*` | Vector | Geofabrik extracts (free, ODbL) |
| Built-up / bare / water share | ESA WorldCover v200, Dynamic World V1 | 10 m | Earth Engine or direct download |
| Local aerosol (dust, smog near industry) | MODIS MAIAC AOD `MODIS/061/MCD19A2_GRANULES` | 1 km daily | Earth Engine |
| Surface heat (urban heat island) | MODIS LST `MODIS/061/MOD11A1`, Landsat 9 L2 `ST_B10` | 1 km / 30 m | Earth Engine |
| Rooftop area | Google Open Buildings V3 | Polygons | Earth Engine — **check Gulf coverage first** (likely Egypt only) |

Reference snippets for each dataset: `earth_engine_datasets.md` (shared separately).

## Fine-level indicators

| Indicator | From |
|---|---|
| Land-use mix (% industrial / residential / commercial / bare) | OSM + WorldCover |
| Local soiling adjustment: parent HSU soiling × (fine AOD / parent-mean AOD) | MAIAC + v1 soiling |
| Surface heat vs parent mean (°C hotter/cooler) | MODIS / Landsat LST |
| Rooftop PV potential (m² roof × parent yield) | Open Buildings + v1 solar |

Never mix surface temperature (LST) with air temperature (ERA5 `t2m`) in one indicator.

## Size

- Urban + industrial area in the 7 countries: roughly 30–60k km² → ~40–80k H3 res-8 cells (estimate; measure in Phase V1).
- Monthly × 10 years → ~5–10 M rows. Fits Postgres.
- A full 1 km grid over all 3.6 M km² with daily rows (~6.5 B rows) is **out of scope**.

## Licence warning

Earth Engine is free for non-commercial use only. Before charging anyone: a commercial Earth Engine plan, or download the same data from the source (NASA LP DAAC, USGS, ESA) and process it yourself.

## Phases (draft)

| Phase | Build | Manual gate |
|---|---|---|
| V1 | Urban mask: OSM + WorldCover → H3 res-8 cells with parent `cell_id` | Cell count recorded; Alexandria industrial zone vs Smouha residential land in different cells |
| V2 | Earth Engine export (MAIAC, LST) → lake → Postgres, monthly per fine cell | Alexandria summer LST hotspots match known industrial areas |
| V3 | dbt: fine-level marts joined to parent marts | Every fine cell has a parent; parent values unchanged |
| V4 | App: zoom into a city shows fine cells; LLM gets both levels in JSON | Validator still rejects any number not in the JSON |
