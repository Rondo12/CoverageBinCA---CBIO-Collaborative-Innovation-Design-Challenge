"""Download OpenStreetMap data for Fresno State and save it as snapshot files.

Simple version:
    Run this ONCE (or when you want fresher data). It asks OpenStreetMap for campus
    shapes and saves them into data/osm/. Everything else in the project reads those
    saved files, so the notebooks keep working even if OpenStreetMap's servers are down.

Technical version:
    Uses osmnx, which sends queries to the Overpass API and returns GeoDataFrames
    (tables with a geometry column). We keep only the columns we use and write GeoJSON.

Run from the repo root:
    .venv/bin/python scripts/fetch_osm.py

Data (c) OpenStreetMap contributors, available under the Open Database License (ODbL).
"""

from datetime import date
from pathlib import Path

import osmnx as ox

OUT = Path("data/osm")

# The university outline in OpenStreetMap: way 44175866,
# "California State University, Fresno". "W" means it is a way (a closed line = polygon).
UNIVERSITY_OSM_ID = "W44175866"

# Land-use tags that mean "farm or agricultural land". These get cut out of the campus.
AG_LANDUSE = [
    "farmland", "orchard", "vineyard", "meadow", "farmyard",
    "greenhouse_horticulture", "plant_nursery", "animal_keeping", "grass_farm",
]

# Only these columns are kept. OSM features can have hundreds of tags; we need a few.
KEEP_COLUMNS = [
    "name", "building", "building:levels", "amenity", "landuse", "highway",
    "entrance", "cuisine", "vending", "parking", "access", "wheelchair",
    "footway", "shop", "leisure",
]


def save(gdf, filename):
    """Keep only useful columns, add the OSM id, and write a GeoJSON file."""
    gdf = gdf.reset_index()  # osmnx puts (element type, id) in the index; make them columns
    cols = [c for c in KEEP_COLUMNS if c in gdf.columns]
    out = gdf[["element", "id"] + cols + ["geometry"]].copy()
    out["osm_id"] = out["element"].astype(str) + "/" + out["id"].astype(str)
    out = out.drop(columns=["element", "id"])
    path = OUT / filename
    out.to_file(path, driver="GeoJSON")
    print(f"  saved {len(out):5d} features -> {path}")
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ox.settings.use_cache = False  # always ask the server; the snapshot IS our cache

    print("University outline...")
    uni = ox.geocode_to_gdf(UNIVERSITY_OSM_ID, by_osmid=True)
    uni = uni[["name", "geometry"]].assign(osm_id="way/44175866")
    uni.to_file(OUT / "university.geojson", driver="GeoJSON")
    area = uni.geometry.iloc[0]
    # Search a little beyond the outline (about 100 m) so edge features are included.
    search = area.buffer(0.001)

    print("Layers inside the university area...")
    save(ox.features_from_polygon(search, {"landuse": AG_LANDUSE}), "ag_landuse.geojson")
    save(ox.features_from_polygon(search, {"building": True}), "buildings.geojson")
    save(ox.features_from_polygon(
        search, {"highway": ["footway", "path", "pedestrian", "steps", "cycleway", "living_street"]}),
        "walkways.geojson")
    save(ox.features_from_polygon(search, {"amenity": "parking"}), "parking.geojson")
    save(ox.features_from_polygon(
        search, {"amenity": ["cafe", "restaurant", "fast_food", "food_court", "vending_machine", "bar", "pub"]}),
        "food_drink.geojson")
    save(ox.features_from_polygon(search, {"entrance": True}), "entrances.geojson")

    (OUT / "FETCHED.txt").write_text(
        f"OpenStreetMap snapshot fetched {date.today().isoformat()} via Overpass API (osmnx).\n"
        "Data (c) OpenStreetMap contributors, ODbL: https://www.openstreetmap.org/copyright\n"
    )
    print("Done.")


if __name__ == "__main__":
    main()
