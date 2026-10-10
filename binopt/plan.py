"""One concrete recommendation: which receptacles to move, where to, and what's still uncovered.

Simple version:
    Take today's receptacles, allow Facilities to move at most `max_moves` of them, and let the
    model pick which ones and where. Then list:
      - the moves (from receptacle R0xx to a spot near building X),
      - the places still not covered,
      - the GAPS: student housing, event venues and parking lots that today's map doesn't serve.
        These are questions for Facilities (maybe Housing or event staff handle them), not
        recommendations.

All coverage is PROJECTED under PLACEHOLDER weights. Which bins move is private (built from
Facilities' map); the gap list names only public OpenStreetMap places.
"""

from dataclasses import dataclass

import pandas as pd

from binopt.model import covered_share, solve_mclp
from binopt.scenarios import NOT_CORE, load_inputs


@dataclass
class Plan:
    radius_m: int
    max_moves: int
    today_core: float
    after_core: float
    today_campus: float
    after_campus: float
    moves_from: pd.DataFrame      # receptacles to move: bin_id, lat, lon
    moves_to: pd.DataFrame        # new spots: site_id, lat, lon, near
    kept: pd.DataFrame            # receptacles that stay: bin_id, lat, lon
    demand: pd.DataFrame          # every demand point + covered_today / covered_after / in_core
    gaps: pd.DataFrame            # non-core places uncovered today, biggest first


def covered_ids(distances, sites, radius_m):
    near = distances[(distances["distance_m"] <= radius_m) & distances["site_id"].isin(set(sites))]
    return set(near["demand_id"])


def make_plan(radius_m=50, max_moves=5):
    demand, sites, bins, _, dist_all = load_inputs()
    core = demand[~demand["use_type"].isin(NOT_CORE)]
    current = list(bins["bin_id"])
    # The model works on the academic core: that's where Facilities' receptacles are.
    chosen = solve_mclp(core, dist_all, len(current), radius_m, current=current, max_moves=max_moves)
    out_ids = sorted(set(current) - set(chosen))
    in_ids = sorted(set(chosen) - set(current))

    d = demand.copy()
    d["in_core"] = ~d["use_type"].isin(NOT_CORE)
    d["covered_today"] = d["demand_id"].isin(covered_ids(dist_all, current, radius_m))
    d["covered_after"] = d["demand_id"].isin(covered_ids(dist_all, chosen, radius_m))
    total = d["weight"].sum()
    d["share"] = d["weight"] / total

    gaps = d[~d["in_core"] & ~d["covered_today"]].copy()
    gaps["group"] = gaps["use_type"].map({"dormitory": "Student housing", "event": "Event venues",
                                          "parking": "Parking lots"})
    gaps = gaps.sort_values("weight", ascending=False)

    return Plan(
        radius_m=radius_m, max_moves=max_moves,
        today_core=covered_share(core, dist_all, current, radius_m),
        after_core=covered_share(core, dist_all, chosen, radius_m),
        today_campus=covered_share(demand, dist_all, current, radius_m),
        after_campus=covered_share(demand, dist_all, chosen, radius_m),
        moves_from=bins[bins["bin_id"].isin(out_ids)][["bin_id", "lat", "lon"]].reset_index(drop=True),
        moves_to=sites[sites["site_id"].isin(in_ids)][["site_id", "lat", "lon", "near"]].reset_index(drop=True),
        kept=bins[~bins["bin_id"].isin(out_ids)][["bin_id", "lat", "lon"]].reset_index(drop=True),
        demand=d, gaps=gaps,
    )


if __name__ == "__main__":
    p = make_plan()
    print(f"Academic core, {p.radius_m} m, move up to {p.max_moves}: "
          f"{p.today_core:.1%} -> {p.after_core:.1%} (whole campus {p.today_campus:.1%} -> {p.after_campus:.1%})")
    print("Move to spots near:", list(p.moves_to["near"]))
    print("\nGaps to ask Facilities about (not served by any receptacle on the 2021 map):")
    for grp, g in p.gaps.groupby("group", dropna=False):
        names = [n for n in g["name"].fillna("") if n]
        print(f"  {grp or 'Other'}: {g['share'].sum():.1%} of estimated demand  {names[:6]}")
