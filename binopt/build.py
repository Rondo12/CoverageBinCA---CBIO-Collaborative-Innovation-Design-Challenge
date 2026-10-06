"""Rebuild every campus data file with one command, then print checks to read.

Run from the repo root:
    .venv/bin/python -m binopt.build

Simple version:
    Boundary -> demand points -> candidate sites -> distances -> current bins (if Facilities sent
    them). Each file is rewritten from the OpenStreetMap snapshots and binopt/config.py, so after
    you change a setting or drop in a new file, this one command brings everything up to date.

Technical version:
    Calls the build_* functions in order and writes data/osm/campus_boundary.geojson,
    data/demand.csv, data/candidates.csv, data/distances.csv and (private) data/private/
    current_bins_clean.csv. The summary includes the coverage CEILING per radius: the share of
    demand within reach of ANY candidate, i.e. what you'd get by building every site. The model's
    answer with p sites can't be higher.
"""

import geopandas as gpd

from binopt import config
from binopt.boundary import LATLON, METERS, save_boundary, load_boundary
from binopt.candidates import build_candidates, build_distances, save_candidates
from binopt.current_bins import PRIVATE_DIR, load_current_bins
from binopt.demand import build_demand, save_demand


def share_within(demand, distances, radius_m):
    """Share of total demand weight that has at least one site within radius_m."""
    reached = distances.loc[distances["distance_m"] <= radius_m, "demand_id"].unique()
    return demand.loc[demand["demand_id"].isin(reached), "weight"].sum() / demand["weight"].sum()


def current_coverage(demand, bins):
    """Share of demand weight within each radius of ANY current bin: {radius_m: share}.

    Uses build_distances, so it's measured exactly like the candidate sites (edge distance,
    straight line). Current bins play the part of "sites" here.
    """
    points = gpd.GeoDataFrame({"site_id": bins["bin_id"]},
                              geometry=gpd.points_from_xy(bins["lon"], bins["lat"]),
                              crs=LATLON).to_crs(METERS)
    distances = build_distances(demand, points)
    return {r: share_within(demand, distances, r) for r in config.COVERAGE_RADII_M}


def main():
    print("1. Boundary")
    save_boundary()
    boundary_gdf = load_boundary()
    boundary = boundary_gdf.to_crs(METERS).geometry.iloc[0]
    print(f"   {boundary.area / 1e6:.2f} km2   (ADD_BACK = {config.ADD_BACK})")

    print("2. Demand points (weights are PLACEHOLDER estimates, relative units)")
    demand = build_demand(boundary)
    path = save_demand(demand)
    total = demand["weight"].sum()
    print(f"   {len(demand)} points -> {path.relative_to(path.parents[1])}")
    # groupby: split rows by source, then count rows and add up weights within each group.
    for source, g in demand.groupby("source"):
        print(f"     {source:<11} {len(g):4d} points  {g['weight'].sum() / total:5.1%} of total weight")
    print("   Biggest 8 (check these look right):")
    top = demand.nlargest(8, "weight")
    for _, r in top.iterrows():
        print(f"     {r['weight'] / total:5.1%}  {r['name'] or '(no name)'}  [{r['use_type']}]")

    print("3. Candidate sites and distances")
    sites = build_candidates(demand, boundary)
    distances = build_distances(demand, sites)
    save_candidates(sites, distances)
    print(f"   {len(sites)} sites: " + ", ".join(f"{k} {v}" for k, v in sites["kind"].value_counts().items()))
    print(f"   {len(distances)} demand-site pairs within {config.MAX_DISTANCE_M} m")

    print("   Coverage ceiling (if EVERY candidate got a station; the model can't beat this):")
    for r in config.COVERAGE_RADII_M:
        print(f"     {r} m: {share_within(demand, distances, r):.1%}")
    r = config.DEFAULT_RADIUS_M
    reachable = set(distances.loc[distances["distance_m"] <= r, "demand_id"])
    stranded = demand[~demand["demand_id"].isin(reachable)].nlargest(5, "weight")
    if len(stranded):
        print(f"   Largest demand points with NO site within {r} m (bins can't reach them):")
        for _, row in stranded.iterrows():
            print(f"     {row['weight'] / total:5.1%}  {row['name'] or '(no name)'}  [{row['source']}]")

    print("4. Current bins (Facilities)")
    bins = load_current_bins()
    if len(bins):
        out = PRIVATE_DIR / "current_bins_clean.csv"
        bins.to_csv(out, index=False)
        print(f"   saved {out.relative_to(out.parents[2])} (private, not committed)")
        # The same coverage measure, for the layout that exists today: our baseline.
        print("   Projected coverage of the CURRENT layout (same PLACEHOLDER weights, same rule):")
        for r, share in current_coverage(demand, bins).items():
            print(f"     {r} m: {share:.1%}")

    print("\nDone. Weights and distances are PLACEHOLDER estimates: report coverage, never diversion.")


if __name__ == "__main__":
    main()
