"""Checks for binopt/anycampus.py, offline: they run on the saved Fresno State snapshot in data/osm.

Simple version: the "any campus" path must work end to end, use the campus's own meters
projection, and never change the Fresno State settings the rest of the project depends on.
"""
from pathlib import Path

import pandas as pd
import pytest

from binopt import anycampus, boundary, candidates, demand
from binopt.tonnage import load_tonnage_csv, size_of_prize, yearly_summary

ROOT = Path(__file__).resolve().parent.parent


def test_slugify():
    assert anycampus.slugify("University of the Pacific, Stockton") == "university-of-the-pacific-stockton"


def test_local_meters_restores_fresno_setting():
    before = (boundary.METERS, demand.METERS, candidates.METERS)
    with anycampus.local_meters("EPSG:32610"):
        assert demand.METERS == "EPSG:32610" and candidates.METERS == "EPSG:32610"
    assert (boundary.METERS, demand.METERS, candidates.METERS) == before


def test_analyze_runs_on_a_saved_campus():
    bins = pd.DataFrame({"bin_id": ["A", "B"], "lat": [36.8124, 36.8146], "lon": [-119.7489, -119.7456]})
    r = anycampus.analyze(ROOT / "data" / "osm", "Fresno State", bins=bins, n_sites=3, verbose=False)
    assert r.meters == "EPSG:32611"                    # Fresno State is in UTM zone 11N
    assert len(r.suggested) == 3
    assert 0 < r.suggested_share <= 1
    assert list(r.ranked["rank"]) == [1, 2]
    assert r.ranked["share"].sum() <= 1 + 1e-9


def test_tonnage_template_reads_and_sizes_the_prize():
    m = load_tonnage_csv(ROOT / "templates" / "tonnage_template.csv")
    assert list(m.columns[:4]) == ["year", "month", "trash_tons", "recycling_tons"]
    y = yearly_summary(m)
    p = size_of_prize(y, year=2024, targets={"half": 0.5})
    assert p["half"]["tons_per_month"] == pytest.approx(0.5 * (52.3 + 49.8 + 55.0 + 14.1 + 13.6 + 15.2) / 3 - (14.1 + 13.6 + 15.2) / 3, abs=0.01)


def test_overpass_urls_are_base_addresses():
    # osmnx 2.x adds "/interpreter" itself; a full address would request .../interpreter/interpreter
    for url in anycampus.OVERPASS_URLS:
        assert url.endswith("/api") and "interpreter" not in url
