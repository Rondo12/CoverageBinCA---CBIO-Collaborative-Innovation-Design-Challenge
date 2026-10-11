"""One concrete recommendation Facilities can act on: REBALANCE by foot traffic.

Simple version:
    1. RANK today's receptacles by the estimated foot traffic each one handles. A handful carry
       most of it. Those are the ones to upgrade first (paired trash + recycling, clear signs),
       and the pilot runs at four of them.
    2. REVIEW THE QUIET ONES: receptacles that no building uses as its closest bin AND that have
       another bin within 30 m. They're candidates to move or remove, decided by the pilot's
       weekly fill log, not by estimates alone.
    3. LIST the places with no outdoor receptacle within reach on the 2021 map (student housing,
       event venues, parking, the Student Recreation Center). These are questions for Facilities,
       not recommendations: the map shows outdoor receptacles only, and many buildings have
       bins inside.
    4. Optional: add = n lets the model ADD n receptacles where they'd reach the most uncovered
       demand (default 0, because indoor bins may already serve those places).

Why "add" and not "move": coverage only asks "is a bin within reach?", not "how full does it
get?". Moving bins out of the busy core looks free to the model but could make the remaining
bins overflow. Adding one bin has no such risk.

All coverage is PROJECTED under PLACEHOLDER weights. Which receptacles rank highest is private
(built from Facilities' map); the gap list names only public OpenStreetMap places.
"""

from dataclasses import dataclass

import pandas as pd

from binopt.model import covered_share, solve_mclp
from binopt.rank import quiet_candidates, rank_receptacles, top_share
from binopt.scenarios import NOT_CORE, load_inputs

PILOT_SITES = ["Fresno State Library", "McLane Hall", "Science II", "University Dining Hall"]


@dataclass
class Plan:
    radius_m: int
    add: int
    today_core: float
    after_core: float
    today_campus: float
    after_campus: float
    ranked: pd.DataFrame          # every receptacle, busiest first (bin_id, lat, lon, share, rank, serves)
    top_k: int
    top_k_share: float            # share of estimated foot traffic handled by the top_k receptacles
    new_spots: pd.DataFrame       # added receptacles (empty when add=0): site_id, lat, lon, near
    quiet: pd.DataFrame           # receptacles to review: bin_id, lat, lon, pair_m, near
    demand: pd.DataFrame          # every demand point + covered_today / covered_after / in_core / share
    gaps: pd.DataFrame            # non-core places uncovered today, biggest first


def covered_ids(distances, sites, radius_m):
    near = distances[(distances["distance_m"] <= radius_m) & distances["site_id"].isin(set(sites))]
    return set(near["demand_id"])


def make_plan(radius_m=50, add=0, top_k=10, quiet_pair_m=30):
    demand, sites, bins, _, dist_all = load_inputs()
    core = demand[~demand["use_type"].isin(NOT_CORE)]
    current = list(bins["bin_id"])

    # Tie-break: places outside the core count 0.1% so equally good core answers are broken the
    # same way every run (and toward helping the rest of campus).
    tie = demand.copy()
    tie.loc[tie["use_type"].isin(NOT_CORE), "weight"] *= 0.001
    chosen = solve_mclp(tie, dist_all, len(current) + add, radius_m, current=current, max_moves=0)
    added = sorted(set(chosen) - set(current))

    d = demand.copy()
    d["in_core"] = ~d["use_type"].isin(NOT_CORE)
    d["covered_today"] = d["demand_id"].isin(covered_ids(dist_all, current, radius_m))
    d["covered_after"] = d["demand_id"].isin(covered_ids(dist_all, chosen, radius_m))
    d["share"] = d["weight"] / d["weight"].sum()

    # Name each new spot after the biggest named core place it newly reaches (more honest than the
    # nearest building's name, which can be a neighbor the spot doesn't serve).
    new = sites[sites["site_id"].isin(added)][["site_id", "lat", "lon", "near"]].reset_index(drop=True)
    for i, sid in enumerate(new["site_id"]):
        reach = dist_all[(dist_all["site_id"] == sid) & (dist_all["distance_m"] <= radius_m)]["demand_id"]
        gained = d[d["demand_id"].isin(reach) & ~d["covered_today"] & d["name"].notna() & (d["name"] != "")]
        if len(gained):
            # prefer a place in the academic core (that's what the model optimizes for)
            new.loc[i, "near"] = gained.sort_values(["in_core", "weight"], ascending=False)["name"].iloc[0]

    # Questions for Facilities: places with no outdoor receptacle within reach on the 2021 map.
    # Non-core places (housing, events, parking) plus sizable core buildings (1%+ of demand).
    gaps = d[~d["covered_today"] & (~d["in_core"] | (d["share"] >= 0.01))].copy()
    gaps["group"] = gaps["use_type"].map({"dormitory": "Student housing", "event": "Event venues",
                                          "parking": "Parking lots"})
    gaps.loc[gaps["in_core"], "group"] = "Core buildings (check indoor bins)"
    gaps = gaps.sort_values("weight", ascending=False)

    ranked = rank_receptacles(demand, bins, dist_all, radius_m)
    return Plan(
        radius_m=radius_m, add=add,
        today_core=covered_share(core, dist_all, current, radius_m),
        after_core=covered_share(core, dist_all, chosen, radius_m),
        today_campus=covered_share(demand, dist_all, current, radius_m),
        after_campus=covered_share(demand, dist_all, chosen, radius_m),
        ranked=ranked, top_k=top_k, top_k_share=top_share(ranked, top_k),
        new_spots=new, quiet=quiet_candidates(ranked, demand, quiet_pair_m), demand=d, gaps=gaps,
    )


def pilot_ranks(plan):
    """{pilot site name: rank of the busiest receptacle serving it} (None if no receptacle serves it)."""
    out = {}
    for name in PILOT_SITES:
        hit = plan.ranked[plan.ranked["serves"].str.contains(name, regex=False)]
        out[name] = int(hit["rank"].min()) if len(hit) else None
    return out


if __name__ == "__main__":
    p = make_plan()
    print(f"Top {p.top_k} of {len(p.ranked)} receptacles handle {p.top_k_share:.1%} of estimated foot traffic")
    print(p.ranked.head(p.top_k)[["rank", "bin_id", "share", "serves"]].to_string(index=False))
    print("Pilot sites' receptacle ranks:", pilot_ranks(p))
    print(f"Quiet receptacles to review ({len(p.quiet)}):", list(zip(p.quiet['bin_id'], p.quiet['near'], p.quiet['pair_m'].round())))
    print(f"Academic core coverage today: {p.today_core:.1%} (whole campus {p.today_campus:.1%})")
    print("\nGaps to ask Facilities about:")
    for grp, g in p.gaps.groupby("group", dropna=False):
        names = [n for n in g["name"].fillna("") if n]
        print(f"  {grp or 'Other'}: {g['share'].sum():.1%} of estimated demand  {names[:6]}")
