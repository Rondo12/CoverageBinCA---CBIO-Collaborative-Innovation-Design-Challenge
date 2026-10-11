"""One concrete recommendation Facilities can act on: PUT RECYCLING WHERE PEOPLE ARE.

Simple version:
    On our walks across campus, most outdoor receptacles we saw were trash only. So the question
    is: if Facilities adds a recycling bin beside some of today's trash cans, which ones first?
    1. RANK today's receptacles by the estimated foot traffic each one handles (binopt/rank.py).
    2. ADD RECYCLING beside the top k (default 10). Count how much estimated foot traffic then has
       recycling within reach, and compare with adding the same k bins beside trash cans picked at random.
    3. SIZE THE PRIZE from the real hauling data: how many tons a month would have to move from
       trash to recycling to get back to 2018's recycling share (binopt/tonnage.py).
    The pilot then measures what each new recycling bin actually captures.

Also kept for the report (not the headline):
    - QUIET receptacles: no building's closest bin AND another bin within 30 m (review with the
      pilot's fill log before moving anything).
    - Places with no OUTDOOR receptacle within reach on the 2021 map (student housing, event
      venues, parking). Many have bins indoors or are served by other departments.
    - add = n still lets the coverage model ADD n receptacles anywhere (default 0).

All coverage is PROJECTED under PLACEHOLDER weights; tonnage numbers are real (Mid Valley
Disposal). Which receptacles rank highest is private (built from Facilities' map).
"""

from dataclasses import dataclass, field

import pandas as pd

from binopt.model import covered_share, solve_mclp
from binopt.rank import quiet_candidates, rank_receptacles, recycling_curve, top_share
from binopt.scenarios import NOT_CORE, load_inputs
from binopt.tonnage import load_tonnage, size_of_prize, yearly_summary

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
    top_k_share: float            # share of estimated foot traffic the top_k recycling additions reach
    random_k_share: float         # same number beside random trash cans (expected value)
    curve: pd.DataFrame           # k, algorithm, random, ratio
    prize: dict = field(default_factory=dict)   # tons a month to move from trash to recycling
    new_spots: pd.DataFrame = None              # coverage-model additions (empty when add=0)
    quiet: pd.DataFrame = None                  # receptacles to review: bin_id, lat, lon, pair_m, near
    demand: pd.DataFrame = None                 # every demand point + covered_today / in_core / share
    gaps: pd.DataFrame = None                   # non-core places with no outdoor receptacle within reach


def covered_ids(distances, sites, radius_m):
    near = distances[(distances["distance_m"] <= radius_m) & distances["site_id"].isin(set(sites))]
    return set(near["demand_id"])


def make_plan(radius_m=50, top_k=10, add=0, quiet_pair_m=30, prize_year=2021):
    demand, sites, bins, _, dist_all = load_inputs()
    core = demand[~demand["use_type"].isin(NOT_CORE)]
    current = list(bins["bin_id"])

    chosen = current
    if add:
        tie = demand.copy()   # outside-core places count 0.1%, so ties break the same way every run
        tie.loc[tie["use_type"].isin(NOT_CORE), "weight"] *= 0.001
        chosen = solve_mclp(tie, dist_all, len(current) + add, radius_m, current=current, max_moves=0)
    added = sorted(set(chosen) - set(current))

    d = demand.copy()
    d["in_core"] = ~d["use_type"].isin(NOT_CORE)
    d["covered_today"] = d["demand_id"].isin(covered_ids(dist_all, current, radius_m))
    d["share"] = d["weight"] / d["weight"].sum()

    gaps = d[~d["in_core"] & ~d["covered_today"]].copy()
    gaps["group"] = gaps["use_type"].map({"dormitory": "Student housing", "event": "Event venues",
                                          "parking": "Parking lots"})
    gaps = gaps.sort_values("weight", ascending=False)

    ranked = rank_receptacles(demand, bins, dist_all, radius_m)
    curve = recycling_curve(ranked)
    at_k = curve[curve["k"] == top_k].iloc[0]
    return Plan(
        radius_m=radius_m, add=add,
        today_core=covered_share(core, dist_all, current, radius_m),
        after_core=covered_share(core, dist_all, chosen, radius_m),
        today_campus=covered_share(demand, dist_all, current, radius_m),
        after_campus=covered_share(demand, dist_all, chosen, radius_m),
        ranked=ranked, top_k=top_k, top_k_share=top_share(ranked, top_k),
        random_k_share=float(at_k["random"]), curve=curve,
        prize=size_of_prize(yearly_summary(load_tonnage()), year=prize_year),
        new_spots=sites[sites["site_id"].isin(added)][["site_id", "lat", "lon", "near"]].reset_index(drop=True),
        quiet=quiet_candidates(ranked, demand, quiet_pair_m), demand=d, gaps=gaps,
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
    print(f"Add recycling beside the top {p.top_k} of {len(p.ranked)} trash cans: reaches {p.top_k_share:.1%} of "
          f"estimated foot traffic vs {p.random_k_share:.1%} at random ({p.top_k_share / p.random_k_share:.1f}x)")
    print(p.curve[p.curve["k"].isin([5, 10, 15, 20, 30])].round(3).to_string(index=False))
    print(p.ranked.head(p.top_k)[["rank", "bin_id", "share", "serves"]].to_string(index=False))
    print("Pilot sites' ranks:", pilot_ranks(p))
    b = p.prize["base"]
    print(f"\nSize of the prize ({b['year']}: {b['trash_tons']:.1f} t trash, {b['recycling_tons']:.1f} t recycling a month, "
          f"{b['recycling_share']:.0%} recycling):")
    for label, v in p.prize.items():
        if label != "base":
            print(f"  {label} ({v['share']:.0%}): move {v['tons_per_month']:.1f} t/month ({v['tons_per_year']:.0f} t/year)")
    print(f"\nQuiet receptacles to review ({len(p.quiet)}):", list(zip(p.quiet['bin_id'], p.quiet['near'])))
    print(f"Academic core coverage today: {p.today_core:.1%} (whole campus {p.today_campus:.1%})")
