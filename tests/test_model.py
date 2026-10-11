"""The model must match the hand-worked answers in data/example/ (see docs/methods.md)."""

from pathlib import Path

import pandas as pd
import pytest

from binopt.model import chosen_table, covered_share, fewest_sites_for, solve_greedy, solve_mclp

EX = Path(__file__).resolve().parent.parent / "data" / "example"


@pytest.fixture(scope="module")
def ex():
    return (pd.read_csv(EX / "demand.csv"), pd.read_csv(EX / "candidates.csv"),
            pd.read_csv(EX / "distances.csv"), pd.read_csv(EX / "expected_chosen_sites.csv"))


@pytest.mark.parametrize("radius", [30, 50, 75])
def test_mclp_matches_known_answers(ex, radius):
    demand, sites, dist, expected = ex
    chosen = solve_mclp(demand, dist, p=2, radius_m=radius)
    exp = expected[expected["radius_m"] == radius]
    assert sorted(chosen) == sorted(exp["site_id"])
    assert covered_share(demand, dist, chosen, radius) == pytest.approx(exp["covered_share"].sum(), abs=1e-3)


@pytest.mark.parametrize("radius", [30, 50, 75])
def test_optimal_never_below_greedy(ex, radius):
    demand, _, dist, _ = ex
    opt = covered_share(demand, dist, solve_mclp(demand, dist, 2, radius), radius)
    greedy = covered_share(demand, dist, solve_greedy(demand, dist, 2, radius), radius)
    assert opt >= greedy - 1e-9


def test_budget_and_moves(ex):
    demand, _, dist, _ = ex
    assert len(solve_mclp(demand, dist, p=3, radius_m=50)) <= 3
    # Today's bins are S2 and S4. Allowing 0 moves must keep both.
    chosen = solve_mclp(demand, dist, p=2, radius_m=50, current=["S2", "S4"], max_moves=0)
    assert sorted(chosen) == ["S2", "S4"]


def test_chosen_table_adds_up(ex):
    demand, sites, dist, _ = ex
    chosen = solve_mclp(demand, dist, p=2, radius_m=50)
    t = chosen_table(demand, dist, sites, chosen, 50, 2)
    assert t["covered_share"].sum() == pytest.approx(covered_share(demand, dist, chosen, 50), abs=1e-4)


def test_fewest_sites(ex):
    demand, _, dist, _ = ex
    # 37.8% at 30 m needs both S1 and S5 (each alone covers less).
    assert len(fewest_sites_for(demand, dist, 85 / 225, 30)) == 2
