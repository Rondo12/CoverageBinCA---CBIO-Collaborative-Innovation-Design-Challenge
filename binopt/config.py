"""Every tunable setting for the campus data, in one place.

Simple version:
    If you want to change an assumption (a weight, a distance, which areas count as campus),
    change it HERE, not inside the other files. Then rerun the steps listed next to it.

Technical version:
    Module-level constants imported by boundary.py, demand.py, candidates.py and maps.py.
    Anything marked PLACEHOLDER is an assumption we chose, not a measured value.
"""

# ---------------------------------------------------------------------------
# Campus boundary (used by binopt/boundary.py)
# ---------------------------------------------------------------------------

# Farm roads and fence-line strips narrower than 2 x this width are removed from the boundary.
# PLACEHOLDER: 20 m, chosen by checking the map; farm roads here are under 40 m wide.
STRIP_WIDTH_M = 20

# ADD_BACK: OpenStreetMap areas that are tagged as farm land but should COUNT AS CAMPUS.
#
# Simple version:
#   The boundary is "university minus farm land". If a farm-tagged area should stay in
#   (for example, you walk past it and it is really a quad or a parking lot), put its
#   OpenStreetMap ID in this list and it won't be cut out.
#
# How to find an ID:
#   - Open the boundary map, turn on the "Removed: farm / ag land" layer, hover the orange area.
#   - Or go to openstreetmap.org, right-click the spot > "Query features", click the area.
#   IDs look like "way/1216348399" (type/number). Copy them exactly, in quotes.
#
# Example (NOT active; it is commented out with #):
#   ADD_BACK = ["way/1216348399"]   # farmyard south of Barstow, west of Chestnut
#
# After editing, rerun from the repo root:
#   1. .venv/bin/python -m binopt.boundary      (rewrites data/osm/campus_boundary.geojson)
#   2. rerun notebooks/01_campus_data.ipynb     (rebuilds demand, candidates, distances, map)
#   Then note the change and the reason in docs/decisions.md.
ADD_BACK = []
