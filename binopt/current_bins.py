"""Load the CURRENT bin locations from whatever file Facilities sends.

Simple version:
    Facilities might send a spreadsheet, a CSV, or a map file, with columns named anything.
    This file finds the location columns, gives every bin an ID, and turns it into one tidy
    table: bin_id, lat, lon, units. One unit = one co-located station (trash + recycling +
    compost together). If there is no file, we say so and return an EMPTY table. We never make
    up a current layout.

Technical version:
    Reads .csv / .xlsx / .geojson (/ .json / .shp / .kml via geopandas). Column names are
    normalized (lowercase, letters and digits only) and matched against lists of common names.
    Handles one combined "lat, lon" column, swapped lat/lon, and projected x/y when
    CURRENT_BINS_CRS is set. Prints every assumption so a person can check it.

Privacy: the input lives in data/private/ (gitignored). Don't commit it or anything made from it
until Facilities says sharing is OK.
"""

import re
from pathlib import Path

import geopandas as gpd
import pandas as pd

from binopt import config
from binopt.boundary import LATLON

ROOT = Path(__file__).resolve().parent.parent
PRIVATE_DIR = ROOT / "data" / "private"
COLUMNS = ["bin_id", "lat", "lon", "units"]

# Possible column names, already normalized (lowercase, only letters and digits).
LAT_NAMES = ["lat", "latitude", "y", "ycoord", "ycoordinate", "pointy", "gpslat", "gpslatitude", "latdd"]
LON_NAMES = ["lon", "long", "lng", "longitude", "x", "xcoord", "xcoordinate", "pointx",
             "gpslon", "gpslong", "gpslongitude", "londd"]
BOTH_NAMES = ["latlon", "latlong", "latlng", "coordinates", "coords", "location", "gps", "gpscoordinates"]
ID_NAMES = ["binid", "id", "assetid", "asset", "assetnumber", "bin", "binnumber", "stationid", "station"]
# Only these count as "number of stations". A column called "count" or "bins" is NOT used:
# it might count containers (3 containers can be 1 station), so a person has to decide.
UNIT_NAMES = ["units", "stations", "stationcount", "numstations"]

# Fresno State is near lat 36.81, lon -119.75. Used to sanity-check the coordinates.
CAMPUS_LAT, CAMPUS_LON = 36.81, -119.75


def normalize(name):
    """'GPS Latitude ' -> 'gpslatitude'. Lowercase and keep only letters and digits."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def find_column(df, names):
    """Return the first column of df whose normalized name is in `names`, else None."""
    lookup = {normalize(c): c for c in df.columns}
    for n in names:
        if n in lookup:
            return lookup[n]
    return None


def find_file(private_dir=PRIVATE_DIR):
    """The current-bins file: CURRENT_BINS_FILE if set, else data/private/current_bins.*"""
    if config.CURRENT_BINS_FILE:
        path = Path(config.CURRENT_BINS_FILE)
        return path if path.is_absolute() else ROOT / path
    for ext in ["csv", "xlsx", "geojson"]:
        path = Path(private_dir) / f"current_bins.{ext}"
        if path.exists():
            return path
    return None


def empty():
    return pd.DataFrame({"bin_id": pd.Series(dtype=str), "lat": pd.Series(dtype=float),
                         "lon": pd.Series(dtype=float), "units": pd.Series(dtype=int)})


def read_any(path):
    """Read a table or a map file. Map files come back with lat/lon columns already filled."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        # utf-8-sig also handles the invisible marker Excel puts at the start of CSVs it saves.
        return pd.read_csv(path, encoding="utf-8-sig")
    if suffix == ".xlsx":
        return pd.read_excel(path)          # first sheet
    if suffix == ".xls":
        raise ValueError("Old Excel format (.xls): open it in Excel or Google Sheets and save as .xlsx.")
    gdf = gpd.read_file(path)               # .geojson, .json, .shp, .kml, ...
    if gdf.crs is not None:
        gdf = gdf.to_crs(LATLON)
    points = gdf.geometry.representative_point()   # a point even if bins were drawn as shapes
    df = pd.DataFrame(gdf.drop(columns="geometry"))
    df["lat"], df["lon"] = points.y, points.x
    return df


def load_current_bins(path=None, crs=None, verbose=True):
    """Return current bins as a table with columns bin_id, lat, lon, units.

    path = the file (default: find_file()). crs = projection of x/y columns, if not lat/lon
    (default: config.CURRENT_BINS_CRS). No file -> an empty table and a message.
    """
    say = print if verbose else (lambda *a, **k: None)
    path = Path(path) if path is not None else find_file()
    if path is None or not path.exists():
        say("No current-bin file found (looked for data/private/current_bins.csv/.xlsx/.geojson); "
            "the map will show no current bins.")
        return empty()

    df = read_any(path)
    say(f"Read {len(df)} rows from {path.name}. Columns: {list(df.columns)}")

    # --- find the location -------------------------------------------------------------
    lat_col, lon_col = find_column(df, LAT_NAMES), find_column(df, LON_NAMES)
    both_col = find_column(df, BOTH_NAMES)
    if lat_col and lon_col:
        lat = pd.to_numeric(df[lat_col], errors="coerce")
        lon = pd.to_numeric(df[lon_col], errors="coerce")
        say(f"  location: '{lat_col}' and '{lon_col}'")
    elif both_col:
        # One column like "36.8123, -119.7456" (what Google Maps copies). Pull out the 2 numbers.
        nums = df[both_col].astype(str).str.findall(r"-?\d+(?:\.\d+)?")
        lat = pd.to_numeric(nums.str[0], errors="coerce")
        lon = pd.to_numeric(nums.str[1], errors="coerce")
        say(f"  location: '{both_col}' split into lat, lon")
    else:
        raise ValueError(f"Couldn't find location columns in {path.name}. Columns are "
                         f"{list(df.columns)}. Rename them to 'lat' and 'lon' and run again.")

    # Projected x/y (e.g. State Plane feet) -> lat/lon, if we were told the projection.
    crs = crs or config.CURRENT_BINS_CRS
    if crs:
        ok = lat.notna() & lon.notna()
        pts = gpd.GeoSeries(gpd.points_from_xy(lon[ok], lat[ok]), crs=crs).to_crs(LATLON)
        lat[ok], lon[ok] = pts.y.values, pts.x.values
        say(f"  converted x/y from {crs} to lat/lon")
    else:
        # Swapped columns? Near campus, lat is positive (~36.8) and lon negative (~-119.7).
        if lat.median() < 0 < lon.median():
            lat, lon = lon, lat
            say("  lat and lon looked swapped; swapped them back")
        if (lat.abs() > 90).any() or (lon.abs() > 180).any():
            raise ValueError("Coordinates are too big to be lat/lon; they're probably in a map projection "
                             "(e.g. State Plane feet). Ask Facilities which one, then set CURRENT_BINS_CRS "
                             "in binopt/config.py (California State Plane Zone 4 feet = 'EPSG:2228').")

    # --- ID and units -----------------------------------------------------------------
    id_col = find_column(df, ID_NAMES)
    unit_col = find_column(df, UNIT_NAMES)
    out = pd.DataFrame({
        "bin_id": df[id_col].astype(str) if id_col else [f"B{i:03d}" for i in range(1, len(df) + 1)],
        "lat": lat.round(6),
        "lon": lon.round(6),
        "units": pd.to_numeric(df[unit_col], errors="coerce").fillna(1).astype(int) if unit_col else 1,
    })
    say(f"  bin_id: {repr(id_col) if id_col else 'none found, numbered B001, B002, ...'}")
    say(f"  units: {repr(unit_col) if unit_col else 'none found, each row = 1 co-located station'}")

    # --- checks -----------------------------------------------------------------------
    missing = out["lat"].isna() | out["lon"].isna()
    if missing.all():
        raise ValueError(f"No row in {path.name} has a usable location. If Facilities sent only "
                         "descriptions (e.g. 'north door of the Library'), the bins have to be placed "
                         "by hand on a map first.")
    if missing.any():
        say(f"  WARNING: dropped {missing.sum()} rows with no usable location: "
            f"{list(out.loc[missing, 'bin_id'])}")
        out = out[~missing]
    far = (out["lat"] - CAMPUS_LAT).abs().gt(0.05) | (out["lon"] - CAMPUS_LON).abs().gt(0.05)
    if far.any():
        say(f"  WARNING: {far.sum()} bins are more than ~5 km from campus; check them: "
            f"{list(out.loc[far, 'bin_id'])[:10]}")
    unused = [c for c in df.columns if c not in (lat_col, lon_col, both_col, id_col, unit_col)]
    if unused:
        say(f"  not used (check nothing important is here, e.g. a container count): {unused}")
    say(f"  -> {len(out)} current bins, {out['units'].sum()} stations")
    return out.reset_index(drop=True)
