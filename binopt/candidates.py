"""Build candidate bin sites and the demand-to-site distances.

Simple version:
    Walk along every campus walkway and drop a pin every 25 m: each pin is a spot where a bin
    station COULD go. Add one pin on the walkway closest to each building (standing in for
    "near the entrance"). Throw away pins that are inside or right against a building, and
    pins that are almost on top of each other. Then measure how far every demand point is from
    every pin (straight line), keeping pairs up to 200 m apart.

Technical version:
    Walkway lines (minus steps/crossings) are clipped to the boundary, the stretches within
    BUILDING_SETBACK_M of any building are cut out (difference), the rest is merged into chains
    (line_merge) and sampled with LineString.interpolate every CANDIDATE_SPACING_M. Building-side
    candidates come from shapely.ops.nearest_points(building, usable walkways). A greedy thinning
    then drops any site within MIN_SITE_GAP_M of one already kept (entrance and building-side
    sites are kept first).
    Distances: spatial join with predicate="dwithin" (MAX_DISTANCE_M), then exact distances.

Data (c) OpenStreetMap contributors, ODbL.
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.ops import nearest_points

from binopt import config
from binopt.boundary import LATLON, METERS, OSM_DIR, load_boundary
from binopt.demand import DATA_DIR, read_layer

CONTRACT_COLUMNS = ["site_id", "lat", "lon", "kind", "near", "accessible"]

# When two sites are too close, the one with the lower number here is kept.
KIND_PRIORITY = {"entrance": 0, "near_building": 1, "walkway": 2}


def walkway_network(boundary, osm_dir=OSM_DIR):
    """All usable walkway lines inside the boundary, merged into one (Multi)LineString."""
    w = read_layer("walkways", osm_dir)
    if "footway" not in w.columns:
        w["footway"] = None
    w = w[w.geom_type.isin(["LineString", "MultiLineString"])]
    w = w[~w["highway"].isin(config.EXCLUDE_HIGHWAY) & ~w["footway"].isin(config.EXCLUDE_FOOTWAY)]
    lines = w.clip(boundary).union_all()
    # line_merge joins pieces that meet end to end into longer chains, so pins are spaced
    # evenly along a path instead of restarting at every short OSM segment.
    return shapely.line_merge(lines)


def points_along(network, spacing):
    """Points every `spacing` meters along each chain, including both ends."""
    points = []
    for line in shapely.get_parts(network):        # get_parts: one chain at a time
        n = max(1, int(np.ceil(line.length / spacing)))
        # np.linspace(0, L, n+1) gives n+1 evenly spaced distances from start to end.
        for d in np.linspace(0, line.length, n + 1):
            points.append(line.interpolate(d))     # the point d meters along the line
    return points


def thin(sites, min_gap):
    """Greedy thinning: walk through sites in priority order, keep one only if no kept site
    is within min_gap meters. Returns the kept rows."""
    sites = sites.assign(_p=sites["kind"].map(KIND_PRIORITY)).sort_values("_p", kind="stable")
    xy = np.column_stack([sites.geometry.x, sites.geometry.y])
    kept = []
    for i in range(len(xy)):
        if not kept or np.min(np.hypot(*(xy[kept] - xy[i]).T)) >= min_gap:
            kept.append(i)
    return sites.iloc[kept].drop(columns="_p")


def build_candidates(demand, boundary=None, osm_dir=OSM_DIR):
    """Return candidate sites as a GeoDataFrame of points in meters.

    demand = the output of binopt.demand.build_demand (used to find building footprints).
    """
    if boundary is None:
        boundary = load_boundary(osm_dir).to_crs(METERS).geometry.iloc[0]
    # Never inside a building: cut the walkways where they come within the setback of ANY
    # building outline (including canopies and bridges we left out of demand). Walkways that
    # pass through or hug a building lose that stretch, so no pin can land there.
    all_buildings = read_layer("buildings", osm_dir)
    all_buildings = all_buildings[all_buildings.geom_type.isin(["Polygon", "MultiPolygon"])]
    no_go = all_buildings.buffer(config.BUILDING_SETBACK_M).union_all()
    network = shapely.line_merge(walkway_network(boundary, osm_dir).difference(no_go))

    rows = [{"kind": "walkway", "geometry": p} for p in points_along(network, config.CANDIDATE_SPACING_M)]

    # One site on the usable walkway nearest to each building (if it's close enough).
    buildings = demand[demand["source"] == "building"]
    for footprint in buildings.geometry:
        on_building, on_walkway = nearest_points(footprint, network)
        if on_building.distance(on_walkway) <= config.NEAR_BUILDING_MAX_M:
            rows.append({"kind": "near_building", "geometry": on_walkway})

    # Mapped entrances (entrance=* nodes): the nearest usable walkway point to the door.
    entrances = read_layer("entrances", osm_dir)
    for door in entrances.geometry:
        if door.within(boundary):
            on_walkway = nearest_points(door, network)[1]
            if door.distance(on_walkway) <= config.NEAR_BUILDING_MAX_M:
                rows.append({"kind": "entrance", "geometry": on_walkway})

    sites = gpd.GeoDataFrame(rows, crs=METERS)
    # Safety check: every pin is on campus and outside every building's setback.
    # (A tiny tolerance, because a pin on the cut edge sits exactly AT the setback distance.)
    sites = sites[sites.within(boundary) & ~sites.within(no_go.buffer(-0.01))]

    sites = thin(sites, config.MIN_SITE_GAP_M)

    # "near": the closest named building within 150 m, so Facilities can find the spot.
    named = demand[(demand["source"] == "building") & (demand["name"] != "")][["name", "geometry"]]
    sites = gpd.sjoin_nearest(sites, named, how="left", max_distance=150)
    sites = sites[~sites.index.duplicated()]       # ties: keep the first match
    sites["near"] = sites["name"].fillna("")

    # OpenStreetMap doesn't reliably record wheelchair routes, curb cuts or surfaces here,
    # so every site starts as "unknown" until Facilities confirms.
    sites["accessible"] = "unknown"

    latlon = sites.geometry.to_crs(LATLON)
    sites["lat"] = latlon.y.round(6)
    sites["lon"] = latlon.x.round(6)
    # Stable order (north to south, then west to east) so IDs don't shuffle between runs.
    sites = sites.sort_values(["lat", "lon"], ascending=[False, True]).reset_index(drop=True)
    sites["site_id"] = [f"S{i:04d}" for i in range(1, len(sites) + 1)]
    return gpd.GeoDataFrame(sites[CONTRACT_COLUMNS + ["geometry"]], crs=METERS)


def build_distances(demand, sites, max_m=None):
    """Straight-line meters between every demand point and site that are max_m or closer.

    With DISTANCE_FROM = "edge", distance to a building or lot is to its nearest edge;
    with "center", to the point at lat/lon.
    """
    max_m = config.MAX_DISTANCE_M if max_m is None else max_m
    targets = demand[["demand_id", "geometry"]].copy()
    if config.DISTANCE_FROM == "center":
        targets["geometry"] = targets.representative_point()

    # Spatial join: pair up rows whose shapes are within max_m of each other (fast, uses an index).
    pairs = gpd.sjoin(sites[["site_id", "geometry"]], targets, predicate="dwithin", distance=max_m)
    # Then the exact distance for each pair. shapely.distance works on whole arrays at once.
    site_geom = sites.geometry.loc[pairs.index].values
    target_geom = targets.geometry.loc[pairs["index_right"]].values
    pairs["distance_m"] = np.round(shapely.distance(site_geom, target_geom), 1)

    out = pd.DataFrame(pairs[["demand_id", "site_id", "distance_m"]])
    return out.sort_values(["demand_id", "distance_m", "site_id"]).reset_index(drop=True)


def save_candidates(sites, distances, data_dir=DATA_DIR):
    """Write data/candidates.csv and data/distances.csv."""
    data_dir = Path(data_dir)
    sites.drop(columns="geometry").to_csv(data_dir / "candidates.csv", index=False)
    distances.to_csv(data_dir / "distances.csv", index=False)
    return data_dir / "candidates.csv", data_dir / "distances.csv"
