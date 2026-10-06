"""Build demand points: where on campus single-use packaging waste is generated (estimated).

Simple version:
    Every building, parking lot and food/drink spot inside the campus boundary becomes a
    "demand point" with a weight: a relative score for how much waste-generating foot traffic
    it gets. Bigger, taller, busier places get bigger weights. All the factors are guesses
    (PLACEHOLDER) kept in binopt/config.py.

Technical version:
    OSM snapshots -> GeoDataFrame in meters (UTM 11N). Buildings: weight = area * levels * use
    factor. Parking: area * PARKING_FACTOR. Food/drink: fixed weight per amenity. Each row keeps
    its footprint geometry (used for edge distances in candidates.py) and a point inside it
    (lat/lon written to data/demand.csv).

Data (c) OpenStreetMap contributors, ODbL.
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd

from binopt import config
from binopt.boundary import LATLON, METERS, OSM_DIR, load_boundary

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Columns required by docs/data-contract.md, then extra columns that explain each weight.
CONTRACT_COLUMNS = ["demand_id", "lat", "lon", "weight", "source", "use_type", "name"]
EXTRA_COLUMNS = ["osm_id", "area_m2", "levels", "factor"]


def read_layer(name, osm_dir=OSM_DIR):
    """Read one snapshot (e.g. "buildings") in meters, making sure the columns we use exist."""
    gdf = gpd.read_file(osm_dir / f"{name}.geojson").to_crs(METERS)
    # Not every snapshot has every column (parking has no "name"). Add missing ones as empty.
    for col in ["name", "building", "amenity", "building:levels"]:
        if col not in gdf.columns:
            gdf[col] = None
    return gdf


def inside(gdf, boundary):
    """Keep features whose inside point lies within the boundary.

    representative_point() is a point guaranteed to be INSIDE the shape (a centroid can fall
    outside an L-shaped building). For a point feature it's the point itself.
    """
    return gdf[gdf.representative_point().within(boundary)].copy()


def classify_use(row):
    """Decide a building's use_type: OSM tags first, then name keywords, then a default."""
    for tag in (row["amenity"], row["building"]):
        if isinstance(tag, str) and tag in config.OSM_TAG_USE:
            return config.OSM_TAG_USE[tag]
    name = row["name"] if isinstance(row["name"], str) else ""
    lowered = " " + name.lower()  # leading space so " lab" also matches a name starting "Lab"
    for keyword, use_type in config.NAME_KEYWORDS:
        if keyword in lowered:
            return use_type
    return "academic" if name else "unknown"


def parse_levels(value):
    """building:levels is text in OSM ("2", "3;4", ...). Return a number, or the default."""
    try:
        levels = float(str(value).split(";")[0])
        return levels if levels > 0 else config.DEFAULT_LEVELS
    except ValueError:
        return config.DEFAULT_LEVELS


def building_demand(boundary, osm_dir=OSM_DIR):
    """Buildings inside the boundary, with weight = area x levels x use factor."""
    b = inside(read_layer("buildings", osm_dir), boundary)
    b = b[~b["building"].isin(config.SKIP_BUILDING_TYPES)]

    # Buildings mapped only as a dot: drop the dot if it sits inside a mapped outline
    # (same building twice), otherwise give it the default footprint.
    is_point = b.geom_type == "Point"
    outlines = b[~is_point].union_all()
    b = b[~(is_point & b.within(outlines))]
    is_point = b.geom_type == "Point"

    b["area_m2"] = b.area.where(~is_point, config.DEFAULT_POINT_AREA_M2).round(1)
    b["levels"] = b["building:levels"].map(parse_levels)
    b["use_type"] = b.apply(classify_use, axis=1)
    b["factor"] = b["use_type"].map(config.USE_FACTORS)
    b["weight"] = b["area_m2"] * b["levels"] * b["factor"]
    b["source"] = "building"
    return b


def parking_demand(boundary, osm_dir=OSM_DIR):
    """Parking lots inside the boundary, with weight = area x PARKING_FACTOR."""
    p = inside(read_layer("parking", osm_dir), boundary)
    p = p[p.geom_type.isin(["Polygon", "MultiPolygon"])]
    p["area_m2"] = p.area.round(1)
    p["levels"] = 1
    p["use_type"] = "parking"
    p["factor"] = config.PARKING_FACTOR
    p["weight"] = p["area_m2"] * p["factor"]
    p["source"] = "parking"
    return p


def food_drink_demand(boundary, osm_dir=OSM_DIR):
    """Food and drink spots inside the boundary, as extra points with a fixed weight."""
    f = inside(read_layer("food_drink", osm_dir), boundary)
    # Some are mapped as building outlines; the spot itself is the point inside.
    f["geometry"] = f.representative_point()
    f["use_type"] = f["amenity"]
    f["area_m2"] = None
    f["levels"] = None
    f["factor"] = None
    f["weight"] = f["amenity"].map(config.FOOD_DRINK_WEIGHTS)
    f["source"] = "food_drink"
    return f


def build_demand(boundary=None, osm_dir=OSM_DIR):
    """Return all demand points as a GeoDataFrame in meters.

    geometry = the footprint (building/lot outline, or the point for food/drink).
    lat/lon  = a point inside the footprint, for the CSV and the map.
    """
    if boundary is None:
        boundary = load_boundary(osm_dir).to_crs(METERS).geometry.iloc[0]

    parts = [building_demand(boundary, osm_dir), parking_demand(boundary, osm_dir),
             food_drink_demand(boundary, osm_dir)]
    # pd.concat stacks tables on top of each other (same columns, more rows).
    demand = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=METERS)

    # A weight of 0 or missing (an unlisted use type) would be a silent mistake: stop loudly.
    bad = demand[~(demand["weight"] > 0)]
    if len(bad):
        raise ValueError(f"Demand points without a positive weight (check config.py):\n"
                         f"{bad[['osm_id', 'source', 'use_type']]}")

    # Point inside each footprint, converted to lat/lon.
    points = demand.representative_point().to_crs(LATLON)
    demand["lat"] = points.y.round(6)
    demand["lon"] = points.x.round(6)
    demand["weight"] = demand["weight"].round(1)
    demand["name"] = demand["name"].fillna("")

    # Stable order (by source, then OSM id) so IDs don't shuffle between runs.
    demand = demand.sort_values(["source", "osm_id"]).reset_index(drop=True)
    demand["demand_id"] = [f"D{i:04d}" for i in range(1, len(demand) + 1)]
    return demand[CONTRACT_COLUMNS + EXTRA_COLUMNS + ["geometry"]]


def save_demand(demand, data_dir=DATA_DIR):
    """Write data/demand.csv (no geometry column; lat/lon are the location)."""
    path = Path(data_dir) / "demand.csv"
    demand.drop(columns="geometry").to_csv(path, index=False)
    return path
