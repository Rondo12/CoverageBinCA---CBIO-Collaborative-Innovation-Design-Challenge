"""Write the tiny example dataset in data/example/ (made-up points, for testing the model).

Simple version:
    8 pretend "places people make waste" and 5 pretend bin spots, laid out on a small grid
    near the middle of campus. The right answer is small enough to check by hand, so Ronnie
    can test his model before running it on the real campus data.

Technical version:
    Points are defined in meters (UTM zone 11N) relative to an origin, converted to lat/lon,
    and distances are computed the same way the real pipeline does (straight line in meters).
    The expected answers were worked out by hand; tests/test_example_data.py double-checks them.

Run from the repo root:  .venv/bin/python scripts/make_example_data.py
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

OUT = Path("data/example")
METERS, LATLON = "EPSG:32611", "EPSG:4326"
ORIGIN_X, ORIGIN_Y = 255_000, 4_077_600  # a spot near the middle of campus, in UTM meters

# (id, x meters east of origin, y meters north of origin, weight, source, use_type, name)
DEMAND = [
    ("D1", 10, 10, 50, "building", "dining", "Example dining hall"),
    ("D2", -20, 30, 20, "food_drink", "cafe", "Example cafe"),
    ("D3", 110, 20, 30, "building", "classroom", "Example classroom building"),
    ("D4", 190, 30, 40, "building", "library", "Example library"),
    ("D5", 100, 128, 10, "building", "office", "Example office"),
    ("D6", 280, 70, 35, "food_drink", "fast_food", "Example snack bar"),
    ("D7", 230, 20, 15, "food_drink", "vending_machine", "Example vending machine"),
    ("D8", 150, 50, 25, "parking", "parking", "Example parking lot"),
]
# (id, x, y, kind, near)
SITES = [
    ("S1", 0, 0, "entrance", "Example dining hall"),
    ("S2", 100, 0, "walkway", "Example classroom building"),
    ("S3", 200, 0, "walkway", "Example library"),
    ("S4", 100, 100, "walkway", "Example office"),
    ("S5", 300, 50, "entrance", "Example snack bar"),
]

# Worked out by hand for p = 2 sites (see docs/data-contract.md, "Check your model").
# (radius_m, site_id, covered_weight)
EXPECTED = [
    (30, "S1", 50), (30, "S5", 35),   # total 85
    (50, "S1", 70), (50, "S3", 55),   # total 125
    (75, "S1", 70), (75, "S3", 80),   # total 150
]


def to_latlon(rows):
    """Turn (x, y) offsets in meters into a GeoDataFrame with lat and lon columns."""
    pts = [Point(ORIGIN_X + r[1], ORIGIN_Y + r[2]) for r in rows]
    g = gpd.GeoDataFrame(geometry=pts, crs=METERS)
    ll = g.to_crs(LATLON)
    return g, ll.geometry.y.round(6), ll.geometry.x.round(6)


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    dg, dlat, dlon = to_latlon(DEMAND)
    demand = pd.DataFrame({
        "demand_id": [r[0] for r in DEMAND], "lat": dlat, "lon": dlon,
        "weight": [r[3] for r in DEMAND], "source": [r[4] for r in DEMAND],
        "use_type": [r[5] for r in DEMAND], "name": [r[6] for r in DEMAND],
    })
    sg, slat, slon = to_latlon(SITES)
    candidates = pd.DataFrame({
        "site_id": [r[0] for r in SITES], "lat": slat, "lon": slon,
        "kind": [r[3] for r in SITES], "near": [r[4] for r in SITES],
        "accessible": "unknown",
    })

    # Every demand-site pair, straight-line distance in meters. Pairs farther than 200 m
    # (MAX_DISTANCE_M in config.py) are left out, just like in the real data.
    rows = []
    for i, d in enumerate(DEMAND):
        for j, s in enumerate(SITES):
            dist = dg.geometry.iloc[i].distance(sg.geometry.iloc[j])
            if dist <= 200:
                rows.append((d[0], s[0], round(dist, 1)))
    distances = pd.DataFrame(rows, columns=["demand_id", "site_id", "distance_m"])

    total = demand["weight"].sum()
    site_ll = candidates.set_index("site_id")
    expected = pd.DataFrame(EXPECTED, columns=["radius_m", "site_id", "covered_weight"])
    expected["lat"] = expected["site_id"].map(site_ll["lat"])
    expected["lon"] = expected["site_id"].map(site_ll["lon"])
    expected["covered_share"] = (expected["covered_weight"] / total).round(4)
    expected["n_sites"] = 2
    expected = expected[["site_id", "lat", "lon", "covered_weight", "covered_share", "radius_m", "n_sites"]]

    demand.to_csv(OUT / "demand.csv", index=False)
    candidates.to_csv(OUT / "candidates.csv", index=False)
    distances.to_csv(OUT / "distances.csv", index=False)
    expected.to_csv(OUT / "expected_chosen_sites.csv", index=False)
    print(f"Wrote {len(demand)} demand points, {len(candidates)} sites, {len(distances)} distance rows to {OUT}/")


if __name__ == "__main__":
    main()
