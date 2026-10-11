"""Every tunable setting for the campus data, in one place.

Simple version:
    If you want to change an assumption (a weight, a distance, which areas count as campus),
    change it HERE, not inside the other files. Then rerun the steps listed next to it.

Technical version:
    Module-level constants imported by boundary.py, demand.py, candidates.py, current_bins.py
    and maps.py.
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
#   .venv/bin/python -m binopt.build      (rebuilds the boundary, demand, candidates, distances)
#   Then note the change and the reason in docs/decisions.md.
ADD_BACK = []

# Areas inside the university outline that Facilities' bins don't serve, cut out of the campus.
# Each is a box: everything east of min_lon AND south of max_lat (degrees) is removed.
# Campus Pointe: the private hotel, apartment and restaurant development east of Chestnut Ave and
# south of the Gibson Farm Market. The 2021 receptacle map shows no Facilities bins there.
# Decision 2026-10-10 (docs/decisions.md). Delete the entry to put it back.
OUT_OF_SCOPE = [
    {"name": "Campus Pointe", "min_lon": -119.7366, "max_lat": 36.8133},
]

# ---------------------------------------------------------------------------
# Demand: how much waste-generating foot traffic each place gets (binopt/demand.py)
# ---------------------------------------------------------------------------
#
# Simple version:
#   Bigger buildings, more floors, and busier uses (eating, studying) get a bigger number.
#   A building's weight = footprint area (m2) x floors x use factor.
#   The number is a RELATIVE score ("relative demand units"), not people or pounds.
#
# Technical version:
#   weight_i = area_m2_i * levels_i * USE_FACTORS[use_type_i]       (buildings)
#   weight_i = area_m2_i * PARKING_FACTOR                          (parking lots)
#   weight_i = FOOD_DRINK_WEIGHTS[amenity_i]                       (food/drink points, extra)
#   Only ratios matter to the model: doubling every weight gives the same chosen sites.

# Floors to assume when OpenStreetMap doesn't record building:levels (97 of 107 buildings).
# PLACEHOLDER: 1 undercounts multi-story buildings; add real floor counts when we have them.
DEFAULT_LEVELS = 1

# Footprint to assume for buildings mapped only as a dot (no outline) in OpenStreetMap.
# PLACEHOLDER: 500 m2, about a small one-story building.
DEFAULT_POINT_AREA_M2 = 500

# Use factor per m2 of floor area. PLACEHOLDER: all of these are our guesses, ranked by how much
# single-use packaging we expect per m2 (eating > shopping > studying > offices > farm).
USE_FACTORS = {
    "dining": 3.0,         # dining halls, food courts
    "student_union": 2.5,  # student unions: food, lounges, events
    "retail": 1.5,         # bookstore, shops, markets
    "library": 1.2,
    "academic": 1.0,       # classrooms and departments (any named building not matched below)
    "recreation": 0.8,     # gyms, rec center
    "dormitory": 0.8,
    "lab": 0.5,            # research labs
    "hotel": 0.5,
    "office": 0.4,         # administration, health center, police
    "event": 0.2,          # stadiums and arenas: very busy, but only on event days
    "operations": 0.2,     # warehouses, plant operations
    "farm": 0.1,           # farm-unit buildings
    "unknown": 0.5,        # no name and no useful tag in OpenStreetMap
}

# How a building's use_type is decided, first rule that matches wins:
#   1. OSM tags (amenity=..., building=...) in OSM_TAG_USE
#   2. a keyword in the building's name, NAME_KEYWORDS (checked top to bottom, case-insensitive)
#   3. any other named building -> "academic"; no name -> "unknown"
OSM_TAG_USE = {
    "library": "library",
    "conference_centre": "event",   # Save Mart Center (arena)
    "dormitory": "dormitory",
    "stadium": "event",
    "retail": "retail",
    "commercial": "retail",
    "farm_auxiliary": "farm",
}
NAME_KEYWORDS = [            # order matters: "marketplace" must be checked before "market"
    ("dining", "dining"),
    ("marketplace", "dining"),   # Kennel Marketplace
    ("student union", "student_union"),
    ("university center", "student_union"),
    ("bookstore", "retail"),
    ("market", "retail"),
    ("library", "library"),
    ("recreation", "recreation"),
    ("gym", "recreation"),
    ("hotel", "hotel"),
    ("hyatt", "hotel"),
    ("administration", "office"),
    ("alumni", "office"),
    ("health center", "office"),
    ("police", "office"),
    ("warehouse", "operations"),
    ("operations", "operations"),
    ("mechanics", "operations"),
    ("laboratory", "lab"),
    ("research", "lab"),
    ("lab school", "academic"),  # a school, not a lab; must come before " lab"
    (" lab", "lab"),             # leading space: "DOJ Lab", but not "Label"
    (" unit", "farm"),           # Beef Unit, Horse Unit; leading space so "community" doesn't match
    ("pavilion", "farm"),        # Judging Pavilion
]

# Building types that are not places people spend time: left out of demand.
# roof = open shade canopies (mostly parking shade), bridge = covered walkways.
SKIP_BUILDING_TYPES = ["roof", "bridge"]

# Parking lots: people walking to and from cars. Per m2 of lot. PLACEHOLDER.
PARKING_FACTOR = 0.05

# Food and drink spots get an EXTRA point with a fixed weight, on top of their building.
# PLACEHOLDER: a restaurant (2000) counts about like a 700 m2 dining hall floor.
FOOD_DRINK_WEIGHTS = {
    "food_court": 3000,
    "restaurant": 2000,
    "fast_food": 2000,
    "cafe": 1500,
    "bar": 1000,
    "pub": 1000,
    "vending_machine": 300,
}

# ---------------------------------------------------------------------------
# Candidate sites: where a bin station could go (binopt/candidates.py)
# ---------------------------------------------------------------------------

# One candidate every this many meters along each walkway. PLACEHOLDER.
CANDIDATE_SPACING_M = 25

# Candidates closer than this to a building wall are dropped (no bins inside or against
# buildings, and doors need clear space). PLACEHOLDER.
BUILDING_SETBACK_M = 3

# Two candidates closer than this are treated as the same spot; one is dropped. PLACEHOLDER.
MIN_SITE_GAP_M = 10

# For each building, one extra candidate on the walkway closest to it, if a walkway is
# within this distance. Stands in for "near an entrance": OSM maps only 1 entrance on campus.
NEAR_BUILDING_MAX_M = 40

# Walkway pieces where a bin can't go: stairs, road crossings, traffic islands.
EXCLUDE_HIGHWAY = ["steps"]
EXCLUDE_FOOTWAY = ["crossing", "traffic_island"]

# How distance from a site to a building or parking lot is measured:
#   "edge"   = to the nearest wall / lot edge (people leave buildings through doors on the edge)
#   "center" = to the center point
# "edge" means a bin by the door of a big building can cover it; with "center" no outdoor
# site could ever be within 50 m of the middle of the library or the stadium.
DISTANCE_FROM = "edge"

# ---------------------------------------------------------------------------
# Current bins from Facilities (binopt/current_bins.py)
# ---------------------------------------------------------------------------

# The loader looks for data/private/current_bins.csv, .xlsx or .geojson (first found).
# An old .xls file: open it in Excel or Google Sheets and save it as .xlsx.
# Put a different file name here if you don't want to rename the file.
CURRENT_BINS_FILE = None   # e.g. "data/private/Bin Inventory 2026.xlsx"

# If the file has x/y in a map projection instead of lat/lon, set its EPSG code here.
# Example: California State Plane Zone 4 (feet), used by many California agencies = "EPSG:2228".
CURRENT_BINS_CRS = None

# ---------------------------------------------------------------------------
# Facilities' 2021 receptacle map (binopt/digitize.py)
# ---------------------------------------------------------------------------

# The PDF Facilities shared, saved in data/private/ (gitignored). digitize.py reads it and writes
# data/private/current_bins.csv (the yellow receptacle dots) and data/private/dumpsters_2021.csv.
MAP_2021_PDF = "RecepticlesMap-BW-lighter 2021.pdf"

# Control points: street corners we can see on the map AND look up in OpenStreetMap.
# px = (x, y) pixel position on the map rendered at 150 dpi (measured from the road bands).
# lat/lon = where the two street center lines cross in OpenStreetMap (data/osm/streets.json,
# fetched 2026-10-10). Public information, so it's fine in the repo.
MAP_2021_CONTROL_POINTS = {
    "Shaw x Cedar":      {"px": (489.5, 1312.0), "lat": 36.808613, "lon": -119.754210},
    "Shaw x Woodrow":    {"px": (1777.0, 1312.0), "lat": 36.808572, "lon": -119.740802},
    "Shaw x Chestnut":   {"px": (2214.0, 1312.0), "lat": 36.808553, "lon": -119.736326},
    "Barstow x Cedar":   {"px": (489.5, 449.5), "lat": 36.815870, "lon": -119.754182},
    "Barstow x Woodrow": {"px": (1752.0, 449.5), "lat": 36.815835, "lon": -119.740955},
    "Bulldog x Cedar":   {"px": (489.5, 882.0), "lat": 36.812243, "lon": -119.754195},
    "Bulldog x Woodrow": {"px": (1777.0, 870.0), "lat": 36.812096, "lon": -119.740772},
}

# ---------------------------------------------------------------------------
# Coverage settings (read by the model, the scenarios and the maps)
# ---------------------------------------------------------------------------

# A demand point counts as "covered" if a chosen bin site is within this many meters
# (straight line). Three values so the model can run a sensitivity check:
# "how much does the answer change if people will walk less, or more, to a bin?"
# PLACEHOLDER: 30 / 50 / 75 m are assumptions, not measured walking behavior.
COVERAGE_RADII_M = [30, 50, 75]
DEFAULT_RADIUS_M = 50  # PLACEHOLDER: the middle value; the one the map shows first

# How many bin stations the model may place (the "p" in the model).
# PLACEHOLDER until Facilities tells us how many stations they could add or move.
N_SITES = 20

# distances.csv only lists demand-to-site pairs up to this far apart (meters).
# Must be at least the largest coverage radius. Keeps the file small.
MAX_DISTANCE_M = 200
