"""Rank today's receptacles by how much estimated foot traffic each one handles.

Simple version:
    Every place on campus (a building, food spot or parking lot) sends its people to the
    closest receptacle within reach. Add up what each receptacle receives, sort from busiest
    to quietest, and you get a priority list: the receptacles to upgrade first (paired trash +
    recycling, clear "no bags in recycling" signs).

    Analogy: a checkout line. Most shoppers end up at a few registers near the entrance, so those
    are the registers you staff and improve first.

Technical version:
    Each demand point i is credited to its nearest receptacle j with distance d_ij <= radius
    (same nearest-site crediting the model uses, so nothing is double counted). A receptacle's
    load is the sum of the weights credited to it; its share is load / total demand weight.
    Weights are PLACEHOLDER estimates (building size x floors x use factor), so this ranks
    receptacles by ESTIMATED foot traffic, not measured fill.
"""

import pandas as pd


def rank_receptacles(demand, bins, distances, radius_m=50):
    """Return one row per receptacle, busiest first:
    bin_id, lat, lon, load, share (of all demand weight), cum_share, rank, serves (named places)."""
    cur = set(bins["bin_id"])
    near = distances[distances["site_id"].isin(cur) & (distances["distance_m"] <= radius_m)]
    near = near.sort_values(["distance_m", "site_id"]).drop_duplicates("demand_id")
    near = near.join(demand.set_index("demand_id")[["weight", "name"]], on="demand_id")
    total = demand["weight"].sum()

    def names(s):
        return ", ".join(sorted({n for n in s if isinstance(n, str) and n}))

    load = near.groupby("site_id").agg(load=("weight", "sum"), serves=("name", names))
    out = bins[["bin_id", "lat", "lon"]].join(load, on="bin_id")
    out["load"] = out["load"].fillna(0.0)
    out["serves"] = out["serves"].fillna("")
    out["share"] = out["load"] / total
    out = out.sort_values(["load", "bin_id"], ascending=[False, True]).reset_index(drop=True)
    out["cum_share"] = out["share"].cumsum()
    out["rank"] = range(1, len(out) + 1)
    return out


def top_share(ranked, k):
    """Share of all estimated foot traffic handled by the k busiest receptacles."""
    return float(ranked["share"].head(k).sum())
