"""Checks that the current-bins loader copes with the kinds of files Facilities might send.

Each test writes a small made-up file into a temporary folder (pytest's `tmp_path`, deleted
afterwards), loads it, and checks the tidy table. No real Facilities data is used.
"""

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point

from binopt.current_bins import COLUMNS, load_current_bins

# Two made-up spots near the middle of campus.
LAT = [36.8130, 36.8120]
LON = [-119.7460, -119.7450]


def load(path, **kwargs):
    return load_current_bins(path, verbose=False, **kwargs)


def test_no_file_means_no_bins(tmp_path, capsys):
    bins = load_current_bins(tmp_path / "current_bins.csv")
    assert list(bins.columns) == COLUMNS and bins.empty
    assert "No current-bin file found" in capsys.readouterr().out


def test_csv_with_odd_column_names(tmp_path):
    path = tmp_path / "bins.csv"
    pd.DataFrame({"Asset ID": ["A-1", "A-2"], "GPS Latitude": LAT, " Longitude ": LON}).to_csv(path, index=False)
    bins = load(path)
    assert list(bins.columns) == COLUMNS
    assert list(bins["bin_id"]) == ["A-1", "A-2"]
    assert list(bins["units"]) == [1, 1]          # default: 1 co-located station per row


def test_excel_with_units_column(tmp_path):
    path = tmp_path / "bins.xlsx"
    pd.DataFrame({"lat": LAT, "lon": LON, "Stations": [2, 1]}).to_excel(path, index=False)
    bins = load(path)
    assert list(bins["units"]) == [2, 1]
    assert list(bins["bin_id"]) == ["B001", "B002"]   # no ID column: numbered


def test_count_column_is_not_treated_as_stations(tmp_path):
    """'count' might be containers (3 containers = 1 station), so a person must decide."""
    path = tmp_path / "bins.csv"
    pd.DataFrame({"lat": LAT, "lon": LON, "count": [3, 3]}).to_csv(path, index=False)
    assert list(load(path)["units"]) == [1, 1]


def test_combined_column_and_swapped_values(tmp_path):
    path = tmp_path / "bins.csv"
    pd.DataFrame({"Location": [f"{LAT[0]}, {LON[0]}", f"{LAT[1]}, {LON[1]}"]}).to_csv(path, index=False)
    assert load(path)["lat"].tolist() == LAT
    path2 = tmp_path / "swapped.csv"
    pd.DataFrame({"lat": LON, "lon": LAT}).to_csv(path2, index=False)   # columns mixed up
    assert load(path2)["lat"].tolist() == LAT


def test_geojson(tmp_path):
    path = tmp_path / "bins.geojson"
    gpd.GeoDataFrame({"id": ["x", "y"]}, geometry=[Point(LON[0], LAT[0]), Point(LON[1], LAT[1])],
                     crs="EPSG:4326").to_file(path, driver="GeoJSON")
    bins = load(path)
    assert list(bins["bin_id"]) == ["x", "y"]
    assert bins["lat"].tolist() == LAT


def test_projected_coordinates(tmp_path):
    """State Plane feet: refused without a CRS, converted with one."""
    feet = gpd.GeoSeries([Point(LON[0], LAT[0])], crs="EPSG:4326").to_crs("EPSG:2228")
    path = tmp_path / "bins.csv"
    pd.DataFrame({"X": feet.x, "Y": feet.y}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="CURRENT_BINS_CRS"):
        load(path)
    bins = load(path, crs="EPSG:2228")
    assert abs(bins["lat"][0] - LAT[0]) < 1e-5 and abs(bins["lon"][0] - LON[0]) < 1e-5


def test_rows_without_location_are_dropped(tmp_path):
    path = tmp_path / "bins.csv"
    pd.DataFrame({"lat": [LAT[0], None], "lon": [LON[0], None]}).to_csv(path, index=False)
    assert len(load(path)) == 1
