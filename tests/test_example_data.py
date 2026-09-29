"""Checks that the example dataset follows the data contract and that its answers are right.

Simple version:
    pytest runs every function whose name starts with "test_". Each one checks a fact with
    `assert`. If the fact is false, the test fails and tells you which line.

Technical version:
    The expected answers in expected_chosen_sites.csv were worked out by hand. Here we confirm
    them by brute force: try every pair of sites (only 10 pairs for 5 sites) and score each
    pair. This is NOT the optimization model (that's Ronnie's PuLP model in 02_model.ipynb);
    brute force only works because the example is tiny.
"""

from itertools import combinations
from pathlib import Path

import pandas as pd

EXAMPLE = Path(__file__).resolve().parent.parent / "data" / "example"


def load(name):
    return pd.read_csv(EXAMPLE / name)


def test_columns_match_contract():
    assert list(load("demand.csv").columns) == ["demand_id", "lat", "lon", "weight", "source", "use_type", "name"]
    assert list(load("candidates.csv").columns) == ["site_id", "lat", "lon", "kind", "near", "accessible"]
    assert list(load("distances.csv").columns) == ["demand_id", "site_id", "distance_m"]
    assert list(load("expected_chosen_sites.csv").columns) == [
        "site_id", "lat", "lon", "covered_weight", "covered_share", "radius_m", "n_sites"]


def test_ids_are_unique_and_linked():
    demand, cands, dist = load("demand.csv"), load("candidates.csv"), load("distances.csv")
    assert demand["demand_id"].is_unique
    assert cands["site_id"].is_unique
    assert set(dist["demand_id"]) <= set(demand["demand_id"])  # "<=" on sets means "is a subset of"
    assert set(dist["site_id"]) <= set(cands["site_id"])
    assert (demand["weight"] > 0).all()


def score(chosen, dist, weights, radius):
    """Covered weight per chosen site; each demand point counts once, for its nearest chosen site."""
    near = dist[dist["site_id"].isin(chosen) & (dist["distance_m"] <= radius)]
    nearest = near.sort_values("distance_m").drop_duplicates("demand_id")
    return nearest.groupby("site_id")["demand_id"].apply(lambda ids: weights[ids].sum()).to_dict()


def test_expected_answers_are_optimal():
    demand, cands, dist = load("demand.csv"), load("candidates.csv"), load("distances.csv")
    weights = demand.set_index("demand_id")["weight"]
    expected = load("expected_chosen_sites.csv")
    for radius, exp in expected.groupby("radius_m"):
        results = {pair: score(pair, dist, weights, radius) for pair in combinations(cands["site_id"], 2)}
        best = max(results, key=lambda pair: sum(results[pair].values()))
        assert set(best) == set(exp["site_id"]), f"radius {radius}"
        got = results[best]
        for _, row in exp.iterrows():
            assert got.get(row["site_id"], 0) == row["covered_weight"]
        # the best pair must be the ONLY best pair, so the check is unambiguous
        best_total = sum(got.values())
        assert sum(1 for p in results if sum(results[p].values()) == best_total) == 1
