"""Checks on the real campus files: data/demand.csv, candidates.csv, distances.csv.

Simple version:
    Rebuild the files from the snapshots and check the rules in docs/methods.md:
    the right columns, every weight above zero, no bin site inside a building, IDs that match.

Technical version:
    Builds in memory (does not overwrite data/), then also checks the committed CSVs match the
    contract, so a stale or hand-edited file is caught.
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest

from binopt import config
from binopt.boundary import METERS, OSM_DIR
from binopt.candidates import build_candidates, build_distances
from binopt.demand import CONTRACT_COLUMNS as DEMAND_COLUMNS, build_demand

DATA = Path(__file__).resolve().parent.parent / "data"


# A fixture is set-up code that pytest runs once and hands to every test that asks for it by name.
@pytest.fixture(scope="module")
def built():
    demand = build_demand()
    sites = build_candidates(demand)
    distances = build_distances(demand, sites)
    return demand, sites, distances


def test_demand_rules(built):
    demand, _, _ = built
    assert list(demand.columns[:len(DEMAND_COLUMNS)]) == DEMAND_COLUMNS
    assert demand["demand_id"].is_unique
    assert (demand["weight"] > 0).all()
    assert set(demand["source"]) == {"building", "food_drink", "parking"}
    assert set(demand["use_type"]) <= set(config.USE_FACTORS) | set(config.FOOD_DRINK_WEIGHTS) | {"parking"}


def test_candidates_never_inside_a_building(built):
    _, sites, _ = built
    assert list(sites.columns[:-1]) == ["site_id", "lat", "lon", "kind", "near", "accessible"]
    assert sites["site_id"].is_unique
    assert (sites["accessible"] == "unknown").all()
    buildings = gpd.read_file(OSM_DIR / "buildings.geojson").to_crs(METERS)
    buildings = buildings[buildings.geom_type != "Point"]
    # sjoin with "dwithin": any (site, building) pair closer than the setback is a failure.
    too_close = gpd.sjoin(sites, buildings, predicate="dwithin", distance=config.BUILDING_SETBACK_M - 0.01)
    assert too_close.empty, too_close[["site_id"]].head()


def test_candidates_are_spread_out(built):
    _, sites, _ = built
    nearest = gpd.sjoin_nearest(sites, sites, exclusive=True, distance_col="gap")
    assert nearest["gap"].min() >= config.MIN_SITE_GAP_M - 0.01


def test_distances_link_and_stay_under_cutoff(built):
    demand, sites, distances = built
    assert list(distances.columns) == ["demand_id", "site_id", "distance_m"]
    assert set(distances["demand_id"]) <= set(demand["demand_id"])
    assert set(distances["site_id"]) <= set(sites["site_id"])
    assert distances["distance_m"].between(0, config.MAX_DISTANCE_M).all()
    assert not distances.duplicated(["demand_id", "site_id"]).any()


def test_committed_files_follow_contract():
    """The CSVs in data/ (what the model reads) have the contract columns."""
    demand = pd.read_csv(DATA / "demand.csv")
    candidates = pd.read_csv(DATA / "candidates.csv")
    distances = pd.read_csv(DATA / "distances.csv")
    assert list(demand.columns[:len(DEMAND_COLUMNS)]) == DEMAND_COLUMNS
    assert list(candidates.columns) == ["site_id", "lat", "lon", "kind", "near", "accessible"]
    assert list(distances.columns) == ["demand_id", "site_id", "distance_m"]
    assert set(distances["demand_id"]) <= set(demand["demand_id"])
    assert set(distances["site_id"]) <= set(candidates["site_id"])
