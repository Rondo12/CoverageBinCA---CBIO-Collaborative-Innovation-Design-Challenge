"""Run the model on Fresno State and compare against today's layout.

Simple version:
    Four questions, all with the same PLACEHOLDER demand weights and the same 'covered' rule:
    1. TODAY: how much demand do the 88 receptacles on the 2021 map cover?
    2. SAME BINS, BETTER SPOTS: if those 88 could go anywhere, how much could they cover?
    3. SMALL CHANGE: if Facilities moves only 5, 10 or 20 of them, how much does coverage rise?
    Each is answered at 30, 50 and 75 m so we can show the answer isn't luck of one setting,
    and for two areas: the whole campus, and the academic core (without student housing, event
    venues and parking lots, which may be served by Housing or event staff rather than the
    receptacles on Facilities' map).
    Note: coverage counts a building as covered if ANY bin is within reach. It ignores how much a
    bin holds, so it can't say how many bins a place needs, only whether people have one nearby.

Run from the repo root:  python -m binopt.scenarios
Writes outputs/scenarios.csv (only coverage numbers, nothing private) and, privately,
data/private/scenario_sites.csv (which bins move where).
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd

from binopt import config
from binopt.boundary import LATLON, METERS, load_boundary
from binopt.candidates import build_distances
from binopt.current_bins import PRIVATE_DIR, load_current_bins
from binopt.demand import build_demand
from binopt.model import covered_share, solve_greedy, solve_mclp

ROOT = Path(__file__).resolve().parent.parent
MOVE_LIMITS = [5, 10, 20]   # PLACEHOLDER: how many bins Facilities might move in one semester
NOT_CORE = ["dormitory", "event", "parking"]   # use types left out of the "academic core" view


def load_inputs():
    """Demand (with shapes), candidate sites, and distances from demand to BOTH the candidate
    sites and today's bins, so 'move a bin' and 'keep a bin' live in the same model."""
    boundary = load_boundary().to_crs(METERS).geometry.iloc[0]
    demand = build_demand(boundary)                       # GeoDataFrame in meters
    sites = pd.read_csv(ROOT / "data" / "candidates.csv")
    dist_cand = pd.read_csv(ROOT / "data" / "distances.csv")
    bins = load_current_bins(verbose=False)
    pts = gpd.GeoDataFrame({"site_id": bins["bin_id"]},
                           geometry=gpd.points_from_xy(bins["lon"], bins["lat"]), crs=LATLON).to_crs(METERS)
    dist_bins = build_distances(demand, pts)
    dist_all = pd.concat([dist_cand, dist_bins], ignore_index=True)
    demand_tbl = pd.DataFrame(demand.drop(columns="geometry"))
    return demand_tbl, sites, bins, dist_cand, dist_all


def main():
    demand, sites, bins, dist_cand, dist_all = load_inputs()
    current = list(bins["bin_id"])
    n = len(current)
    if n == 0:
        raise SystemExit("No current bins found in data/private/. Run: python -m binopt.digitize")
    rows, moves = [], []
    areas = {"whole campus": demand, "academic core": demand[~demand["use_type"].isin(NOT_CORE)]}
    for area, dem in areas.items():
        for r in config.COVERAGE_RADII_M:
            base = dict(area=area, radius_m=r)
            today = covered_share(dem, dist_all, current, r)
            rows.append(dict(base, scenario="today", stations=n, moved=0, coverage=today))
            best = solve_mclp(dem, dist_cand, n, r)
            rows.append(dict(base, scenario="same number, best spots", stations=len(best), moved=None,
                             coverage=covered_share(dem, dist_cand, best, r)))
            greedy = solve_greedy(dem, dist_cand, n, r)
            rows.append(dict(base, scenario="greedy check", stations=len(greedy), moved=None,
                             coverage=covered_share(dem, dist_cand, greedy, r)))
            for m in MOVE_LIMITS:
                chosen = solve_mclp(dem, dist_all, n, r, current=current, max_moves=m)
                out_ = sorted(set(current) - set(chosen))
                in_ = sorted(set(chosen) - set(current))
                rows.append(dict(base, scenario=f"move up to {m}", stations=len(chosen), moved=len(out_),
                                 coverage=covered_share(dem, dist_all, chosen, r)))
                moves += [dict(base, max_moves=m, action="move from", site_id=b) for b in out_]
                moves += [dict(base, max_moves=m, action="move to", site_id=x) for x in in_]
            print(f"{area}, radius {r} m done")

    out = pd.DataFrame(rows)
    out["coverage"] = out["coverage"].round(4)
    out.to_csv(ROOT / "outputs" / "scenarios.csv", index=False)
    pd.DataFrame(moves).to_csv(PRIVATE_DIR / "scenario_moves.csv", index=False)
    print("\nPROJECTED coverage (PLACEHOLDER weights; not diversion):")
    for (area, r), g in out.groupby(["area", "radius_m"], sort=False):
        print(f"\n  {area}, radius {r} m")
        for _, row in g.iterrows():
            print(f"    {row['scenario']:<32} {int(row['stations']):3d} stations  {row['coverage']:6.1%}")
    return out


if __name__ == "__main__":
    main()
