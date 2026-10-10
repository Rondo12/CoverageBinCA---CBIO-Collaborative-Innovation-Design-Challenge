"""Checks for binopt/rank.py on a tiny hand-made campus.

Two receptacles: A near two places, B near one. Each place goes to its NEAREST receptacle,
so the loads (and shares) can be worked out by hand.
"""
import pandas as pd
import pytest

from binopt.rank import rank_receptacles, top_share


def tiny():
    demand = pd.DataFrame({"demand_id": ["d1", "d2", "d3", "d4"], "weight": [50.0, 30.0, 15.0, 5.0],
                           "name": ["Library", "Union", "Lab", None]})
    bins = pd.DataFrame({"bin_id": ["A", "B", "C"], "lat": [0, 0, 0], "lon": [0, 0, 0]})
    dist = pd.DataFrame({"demand_id": ["d1", "d1", "d2", "d3", "d4"],
                         "site_id":   ["A",  "B",  "A",  "B",  "C"],
                         "distance_m": [10,   40,   20,   30,   80]})   # d4 is out of reach (80 m)
    return demand, bins, dist


def test_nearest_crediting_and_order():
    r = rank_receptacles(*tiny(), radius_m=50)
    assert list(r["bin_id"]) == ["A", "B", "C"]                  # A gets d1+d2, B gets d3, C nothing
    assert r["load"].tolist() == pytest.approx([80.0, 15.0, 0.0])
    assert r["share"].tolist() == pytest.approx([0.80, 0.15, 0.0])
    assert r["serves"].iloc[0] == "Library, Union"


def test_shares_never_double_count():
    r = rank_receptacles(*tiny(), radius_m=50)
    assert r["share"].sum() <= 1.0 + 1e-9
    assert top_share(r, 2) == pytest.approx(0.95)
