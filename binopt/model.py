"""The placement model: where should the bin stations go?

Simple version:
    Every demand point (a building, a cafe, a parking lot) has a weight: how much waste-generating
    foot traffic we estimate there. A point is "covered" if a station is within the radius
    (e.g. 50 m). Given p stations, pick the sites that cover the most weight.
    Analogy: placing p Wi-Fi routers so the most people get signal.

Technical version:
    Maximal Covering Location Problem (MCLP), Church & ReVelle (1974), solved as a 0/1 integer
    program with PuLP + the CBC solver:
        maximize   sum_i w_i * y_i                 (covered weight)
        subject to sum_j x_j <= p                  (at most p stations)
                   y_i <= sum_{j in N_i} x_j       (i counts only if a chosen site is within r)
                   x_j, y_i in {0, 1}
    N_i = sites within r of demand point i (from distances.csv).
    Optional "move at most m" rule: the current bins are also sites, and
        sum_{j current} (1 - x_j) <= m             (at most m current bins are removed/moved)
    A greedy heuristic (add the site that covers the most still-uncovered weight, repeat) is a
    baseline and a sanity check: the optimal answer can never cover less than greedy.

Every number this produces is PROJECTED COVERAGE under PLACEHOLDER weights, not diversion.
"""

import pandas as pd
import pulp


def coverage_sets(distances, radius_m, demand_ids=None):
    """{demand_id: set of site_ids within radius_m}. Points no site reaches are left out.
    demand_ids = only these demand points (lets us run the model on part of campus)."""
    near = distances[distances["distance_m"] <= radius_m]
    if demand_ids is not None:
        near = near[near["demand_id"].isin(set(demand_ids))]
    return near.groupby("demand_id")["site_id"].apply(set).to_dict()


def covered_share(demand, distances, sites, radius_m):
    """Share of total demand weight within radius_m of ANY of `sites`."""
    sites = set(sites)
    near = distances[(distances["distance_m"] <= radius_m) & distances["site_id"].isin(sites)]
    covered = demand["demand_id"].isin(near["demand_id"].unique())
    return demand.loc[covered, "weight"].sum() / demand["weight"].sum()


def solve_mclp(demand, distances, p, radius_m, current=None, max_moves=None, time_limit=120):
    """Return the list of chosen site_ids (optimal, or best found within time_limit seconds).

    current   = list of site_ids that are today's bins (they must be in distances).
    max_moves = if set, at most this many current bins may be dropped; the rest stay put.
    """
    weight = demand.set_index("demand_id")["weight"].to_dict()
    cover = coverage_sets(distances, radius_m, demand["demand_id"])
    sites = sorted(set(distances["site_id"]))

    prob = pulp.LpProblem("mclp", pulp.LpMaximize)
    # x[j] = 1 if site j gets a station. y[i] = 1 if demand point i is covered.
    x = pulp.LpVariable.dicts("x", sites, cat="Binary")
    y = pulp.LpVariable.dicts("y", list(cover), cat="Binary")

    prob += pulp.lpSum(weight[i] * y[i] for i in cover)               # goal: covered weight
    prob += pulp.lpSum(x.values()) <= p                                 # station budget
    for i, near in cover.items():                                       # i covered only if a
        prob += y[i] <= pulp.lpSum(x[j] for j in near)                  # chosen site is near
    if current is not None and max_moves is not None:
        prob += pulp.lpSum(1 - x[j] for j in current if j in x) <= max_moves

    prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit))
    return [j for j in sites if x[j].value() is not None and x[j].value() > 0.5]


def solve_greedy(demand, distances, p, radius_m):
    """Greedy baseline: repeatedly add the site that covers the most still-uncovered weight."""
    weight = demand.set_index("demand_id")["weight"].to_dict()
    near = distances[(distances["distance_m"] <= radius_m) & distances["demand_id"].isin(weight)]
    reach = near.groupby("site_id")["demand_id"].apply(set).to_dict()   # site -> points it covers
    covered, chosen = set(), []
    for _ in range(p):
        best, gain = None, 0.0
        for s, pts in reach.items():
            g = sum(weight[i] for i in pts - covered)
            if g > gain:
                best, gain = s, g
        if best is None:          # nothing left to gain
            break
        chosen.append(best)
        covered |= reach.pop(best)
    return chosen


def fewest_sites_for(demand, distances, target_share, radius_m, time_limit=120):
    """Smallest number of stations that reaches at least target_share coverage.

    Set-covering flavor of the same model: minimize sum x_j subject to covered weight >= target.
    This answers "could Facilities get today's coverage with fewer bins?"
    """
    weight = demand.set_index("demand_id")["weight"].to_dict()
    total = demand["weight"].sum()
    cover = coverage_sets(distances, radius_m, demand["demand_id"])
    sites = sorted(set(distances["site_id"]))
    prob = pulp.LpProblem("fewest", pulp.LpMinimize)
    x = pulp.LpVariable.dicts("x", sites, cat="Binary")
    y = pulp.LpVariable.dicts("y", list(cover), cat="Binary")
    prob += pulp.lpSum(x.values())
    prob += pulp.lpSum(weight[i] * y[i] for i in cover) >= target_share * total
    for i, near in cover.items():
        prob += y[i] <= pulp.lpSum(x[j] for j in near)
    prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit))
    return [j for j in sites if x[j].value() is not None and x[j].value() > 0.5]


def chosen_table(demand, distances, sites_df, chosen, radius_m, n_sites):
    """The data-contract output: one row per chosen site, each demand point credited only to
    its NEAREST chosen site, so covered_share adds up to the total coverage."""
    total = demand["weight"].sum()
    near = distances[(distances["distance_m"] <= radius_m) & distances["site_id"].isin(chosen)]
    nearest = near.sort_values("distance_m").drop_duplicates("demand_id")      # one site per point
    nearest = nearest.merge(demand[["demand_id", "weight"]], on="demand_id")
    per_site = nearest.groupby("site_id")["weight"].sum()
    out = sites_df[sites_df["site_id"].isin(chosen)][["site_id", "lat", "lon"]].copy()
    out["covered_weight"] = out["site_id"].map(per_site).fillna(0.0).round(1)
    out["covered_share"] = (out["covered_weight"] / total).round(5)
    out["radius_m"] = radius_m
    out["n_sites"] = n_sites
    return out.sort_values("covered_weight", ascending=False).reset_index(drop=True)
