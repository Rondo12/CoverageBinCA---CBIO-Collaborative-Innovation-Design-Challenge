"""Build the campus boundary: the Fresno State area minus farm and agricultural land.

Simple version:
    Start with the university's outline from OpenStreetMap (it includes the farm),
    cut out every shape tagged as farmland, orchard, vineyard, etc., and keep what's left.

Technical version:
    Polygon difference (university - union(ag polygons)) done in meters (UTM zone 11N),
    then tiny leftover slivers are dropped. Result is saved as GeoJSON in lat/lon (WGS84).

Data (c) OpenStreetMap contributors, ODbL.
"""

from pathlib import Path

import geopandas as gpd

from binopt.config import ADD_BACK, STRIP_WIDTH_M

OSM_DIR = Path(__file__).resolve().parent.parent / "data" / "osm"

# Coordinate systems (CRS = coordinate reference system):
#   EPSG:4326  = latitude/longitude in degrees (what GPS and web maps use)
#   EPSG:32611 = UTM zone 11N, in meters (covers Fresno). Use it for areas and distances,
#                because one "degree" is not a fixed number of meters.
LATLON = "EPSG:4326"
METERS = "EPSG:32611"


def build_boundary(osm_dir=OSM_DIR, add_back=ADD_BACK):
    """Return (boundary, removed_ag) as GeoDataFrames in lat/lon.

    boundary   = the main campus, one row, a (Multi)Polygon
    removed_ag = the agricultural shapes that were cut out (for showing on the map)
    add_back   = OSM ids of farm-tagged areas to keep as campus (see ADD_BACK in config.py)
    """
    # Read the snapshots and switch them to meters.
    uni = gpd.read_file(osm_dir / "university.geojson").to_crs(METERS)
    ag = gpd.read_file(osm_dir / "ag_landuse.geojson").to_crs(METERS)
    # Keep only polygons (some OSM features can be points or lines).
    ag = ag[ag.geom_type.isin(["Polygon", "MultiPolygon"])]

    # Areas listed in ADD_BACK are taken out of the "farm" list, so they are not cut.
    # ag["osm_id"].isin(add_back) is True/False per row; "~" flips it to "NOT in the list".
    unknown = set(add_back) - set(ag["osm_id"])
    if unknown:
        raise ValueError(f"ADD_BACK ids not found in data/osm/ag_landuse.geojson: {sorted(unknown)}")
    kept_in = ag[ag["osm_id"].isin(add_back)]
    ag = ag[~ag["osm_id"].isin(add_back)]

    # union_all() merges all farm shapes into one shape; difference() cuts it out.
    campus = uni.geometry.iloc[0].difference(ag.union_all())

    # Shrink then grow: thin farm roads vanish, wide campus areas survive.
    opened = campus.buffer(-STRIP_WIDTH_M).buffer(STRIP_WIDTH_M)

    # "explode" splits a multi-part shape into separate rows, one per piece.
    # The main campus is by far the biggest piece; leftover pockets inside the farm are dropped.
    pieces = gpd.GeoDataFrame(geometry=[opened], crs=METERS).explode(index_parts=False)
    # max(..., key=...) picks the item with the largest value of the key: here, the largest area.
    main_piece = max(pieces.geometry, key=lambda shape: shape.area)

    # Growing back rounds off corners slightly. Intersecting with the un-rounded cut restores
    # the true edges (roads, lot corners) while keeping the thin strips removed.
    final = campus.intersection(main_piece.buffer(STRIP_WIDTH_M))

    # Make sure added-back areas are included in full, even if they were thin or detached.
    if len(kept_in):
        final = final.union(kept_in.union_all().intersection(uni.geometry.iloc[0]))

    boundary = gpd.GeoDataFrame(
        {"name": ["Fresno State main campus (excluding farm)"],
         "area_m2": [round(final.area)]},
        geometry=[final], crs=METERS,
    )
    removed = ag.clip(uni.geometry.iloc[0])  # only the ag land that was inside the university
    return boundary.to_crs(LATLON), removed.to_crs(LATLON)


def save_boundary(osm_dir=OSM_DIR):
    """Build the boundary and write data/osm/campus_boundary.geojson."""
    boundary, _ = build_boundary(osm_dir)
    path = osm_dir / "campus_boundary.geojson"
    boundary.to_file(path, driver="GeoJSON")
    return path


def load_boundary(osm_dir=OSM_DIR):
    """Read the saved campus boundary (lat/lon)."""
    return gpd.read_file(osm_dir / "campus_boundary.geojson")


# Lets you run this file directly:  .venv/bin/python -m binopt.boundary
# ("__main__" is the name Python gives the file you run; imported files get their own name.)
if __name__ == "__main__":
    path = save_boundary()
    print(f"Saved {path}  (ADD_BACK = {ADD_BACK})")
