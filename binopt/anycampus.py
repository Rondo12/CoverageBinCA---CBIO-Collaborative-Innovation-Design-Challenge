"""Run the bin model on ANY campus: type a campus name, get a foot-traffic map and bin advice.

Simple version:
    1. FIND the campus on OpenStreetMap (the free world map) by its name.
    2. DOWNLOAD its buildings, walkways, parking lots and food spots.
    3. ESTIMATE where waste-generating foot traffic is (same rules as for Fresno State).
    4. Then either:
       - you have a bin list (a CSV with lat/lon): RANK your bins by the foot traffic each one
         serves, so you know where recycling and signs matter most; or
       - you don't: SUGGEST where n bin stations would reach the most estimated foot traffic.
    Analogy: the same recipe, new kitchen. The steps don't change, only the ingredients.

Technical version:
    Nominatim geocoding (osmnx.geocode_to_gdf) -> campus polygon; Overpass (osmnx.features_from_polygon)
    -> the same layers scripts/fetch_osm.py saves for Fresno State. Distances use the campus's own
    UTM zone (GeoDataFrame.estimate_utm_crs), so meters are accurate anywhere in the world. The
    demand, candidate and distance builders from binopt/ are reused unchanged; only the meters
    projection is swapped in while they run (see local_meters below). Suggested sites come from the
    exact Maximal Covering Location model (binopt/model.py).

Honesty rules (same as the rest of the project):
    Foot traffic is an ESTIMATE from building size and use (PLACEHOLDER weights in config.py).
    Results are projected coverage, not measured recycling. A campus's own data replaces the
    estimates when it has some.

Use it:
    In Colab: notebooks/02_any_campus.ipynb (type the campus name, Run all).
    On a laptop:  python -m binopt.anycampus "University of the Pacific, Stockton, California"
                  python -m binopt.anycampus "California State University, Stanislaus" --bins my_bins.csv
Data (c) OpenStreetMap contributors, ODbL.
"""

import argparse
import contextlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd

from binopt import boundary as _boundary
from binopt import candidates as _candidates
from binopt import config
from binopt import demand as _demand
from binopt.boundary import LATLON
from binopt.model import covered_share, solve_mclp
from binopt.rank import rank_receptacles, recycling_curve, top_share

ROOT = Path(__file__).resolve().parent.parent
CAMPUS_DIR = ROOT / "data" / "campuses"

# The OpenStreetMap layers the model needs (the same ones scripts/fetch_osm.py saves for Fresno State).
AG_LANDUSE = ["farmland", "orchard", "vineyard", "meadow", "farmyard",
              "greenhouse_horticulture", "plant_nursery", "animal_keeping", "grass_farm"]
LAYERS = {
    "ag_landuse": {"landuse": AG_LANDUSE},
    "buildings": {"building": True},
    "walkways": {"highway": ["footway", "path", "pedestrian", "steps", "cycleway", "living_street"]},
    "parking": {"amenity": "parking"},
    "food_drink": {"amenity": ["cafe", "restaurant", "fast_food", "food_court", "vending_machine", "bar", "pub"]},
    "entrances": {"entrance": True},
}
# Public Overpass servers, tried in order. The main one is sometimes busy; the others are mirrors.
# Base addresses only: osmnx 2.x adds "/interpreter" (and "/status") itself.
OVERPASS_URLS = ["https://overpass-api.de/api",
                 "https://maps.mail.ru/osm/tools/overpass/api",
                 "https://overpass.kumi.systems/api"]
KEEP_COLUMNS = ["name", "building", "building:levels", "amenity", "landuse", "highway",
                "entrance", "cuisine", "vending", "parking", "access", "wheelchair",
                "footway", "shop", "leisure"]


def slugify(name):
    """'University of the Pacific, Stockton' -> 'university-of-the-pacific-stockton'."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]


@contextlib.contextmanager
def local_meters(crs):
    """Temporarily use this campus's meters projection inside the shared builders.

    binopt/ was written for Fresno State, where every module uses UTM zone 11N. Another campus
    needs its own zone, or distances drift. This swaps the setting in while the builders run and
    puts it back afterwards, so Fresno State results never change.
    """
    modules = [_boundary, _demand, _candidates]
    old = [m.METERS for m in modules]
    for m in modules:
        m.METERS = crs
    try:
        yield
    finally:
        for m, o in zip(modules, old):
            m.METERS = o


def _empty_layer():
    return gpd.GeoDataFrame({"osm_id": pd.Series(dtype=str)}, geometry=[], crs=LATLON)


def _save_layer(gdf, path):
    """Keep only useful columns, add the OSM id, and write a GeoJSON file (empty layers too)."""
    if gdf is None or len(gdf) == 0:
        out = _empty_layer()
    else:
        gdf = gdf.reset_index()
        cols = [c for c in KEEP_COLUMNS if c in gdf.columns]
        out = gdf[["element", "id"] + cols + ["geometry"]].copy()
        out["osm_id"] = out["element"].astype(str) + "/" + out["id"].astype(str)
        out = out.drop(columns=["element", "id"])
    out.to_file(path, driver="GeoJSON")
    return len(out)


def fetch_campus(name, out_dir=None, verbose=True):
    """Find the campus on OpenStreetMap and save its layers. Returns the folder they're in.

    name = what you'd type into a map search, e.g. "University of the Pacific, Stockton, California".
           An OpenStreetMap id also works, e.g. "W44175866" (Fresno State) or "R3465402".
    """
    import osmnx as ox   # only needed for downloading, so imported here

    say = print if verbose else (lambda *a, **k: None)
    by_id = bool(re.fullmatch(r"[NWR]\d+", name.strip()))
    place = ox.geocode_to_gdf(name.strip(), by_osmid=by_id)
    area = place.geometry.iloc[0]
    if area.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError(f"OpenStreetMap found '{name}' only as a point, not a campus outline. Try the full "
                         "official name plus the city and state, or the campus's OpenStreetMap id.")
    label = place.get("display_name", pd.Series([name])).iloc[0]
    out_dir = Path(out_dir) if out_dir else CAMPUS_DIR / slugify(name) / "osm"
    out_dir.mkdir(parents=True, exist_ok=True)
    say(f"Found: {label}")

    uni = gpd.GeoDataFrame({"name": [str(label).split(",")[0]], "osm_id": [name]}, geometry=[area], crs=LATLON)
    uni.to_file(out_dir / "university.geojson", driver="GeoJSON")

    search = area.buffer(0.001)   # about 100 m past the outline, so edge features are included
    ox.settings.use_cache = False
    for layer, tags in LAYERS.items():
        gdf = _download(ox, search, tags, say)
        n = _save_layer(gdf, out_dir / f"{layer}.geojson")
        say(f"  {layer:<11} {n:5d} features")
        if layer == "buildings" and n == 0:
            say("  Note: OpenStreetMap has no buildings mapped here, so foot traffic comes only from "
                "parking and food spots. Check the campus name, or treat these results as rough.")
    (out_dir / "FETCHED.txt").write_text(
        f"OpenStreetMap snapshot of '{label}' fetched {date.today().isoformat()} via Overpass API (osmnx).\n"
        "Data (c) OpenStreetMap contributors, ODbL: https://www.openstreetmap.org/copyright\n")
    return out_dir


def _download(ox, polygon, tags, say):
    """One OpenStreetMap layer, trying each Overpass server until one answers. None = nothing there."""
    last = None
    for url in OVERPASS_URLS:
        ox.settings.overpass_url = url
        try:
            return ox.features_from_polygon(polygon, tags)
        except Exception as e:
            if "No matching features" in str(e):
                return None   # the layer is simply empty here (e.g. no farm land)
            last = e   # anything else (busy, error page, timeout) means try the next server
            say(f"  ({url.split('/')[2]} didn't answer: {type(e).__name__}; trying the next server)")
    raise ConnectionError(f"No OpenStreetMap server answered; try again in a minute. Last error: {last}")


def _ensure_layers(osm_dir):
    """A campus can lack a layer (no mapped doors, no farm land). Write it as empty so the
    shared builders, which expect every file, still run."""
    if not (osm_dir / "university.geojson").exists():
        raise FileNotFoundError(f"No campus outline in {osm_dir}; run fetch_campus first.")
    for layer in LAYERS:
        if not (osm_dir / f"{layer}.geojson").exists():
            _empty_layer().to_file(osm_dir / f"{layer}.geojson", driver="GeoJSON")


def campus_boundary(osm_dir, meters):
    """The campus outline minus farm land (if any), in meters. Simpler than Fresno State's version:
    no hand-picked exceptions, so any campus works without editing config.py."""
    uni = gpd.read_file(osm_dir / "university.geojson").to_crs(meters)
    shape = uni.geometry.union_all()
    ag = gpd.read_file(osm_dir / "ag_landuse.geojson")
    if len(ag):
        ag = ag.to_crs(meters)
        ag = ag[ag.geom_type.isin(["Polygon", "MultiPolygon"])]
        if len(ag):
            trimmed = shape.difference(ag.union_all())
            if trimmed.area > 0.25 * shape.area:   # never cut away most of a campus
                shape = trimmed
    return shape


@dataclass
class CampusResult:
    name: str
    meters: str
    area_km2: float
    demand: gpd.GeoDataFrame        # estimated foot-traffic points
    sites: gpd.GeoDataFrame         # candidate bin spots along walkways
    distances: pd.DataFrame
    suggested: pd.DataFrame         # best n spots (no bin list) with their coverage
    suggested_share: float          # share of estimated foot traffic the suggested spots reach
    ranked: pd.DataFrame = None     # your bins, busiest first (only with a bin list)
    curve: pd.DataFrame = None      # recycling beside top-k bins vs. random (only with a bin list)


def analyze(osm_dir, name="campus", bins=None, n_sites=10, radius_m=50, verbose=True):
    """Run the model on a saved campus folder. bins = a DataFrame with lat/lon (optional)."""
    say = print if verbose else (lambda *a, **k: None)
    osm_dir = Path(osm_dir)
    _ensure_layers(osm_dir)
    uni = gpd.read_file(osm_dir / "university.geojson")
    meters = str(uni.estimate_utm_crs())
    with local_meters(meters):
        shape = campus_boundary(osm_dir, meters)
        demand = _demand.build_demand(shape, osm_dir)
        sites = _candidates.build_candidates(demand, shape, osm_dir)
        distances = _candidates.build_distances(demand, sites)
        say(f"{name}: {shape.area / 1e6:.2f} km2, {len(demand)} foot-traffic points, {len(sites)} candidate spots")

        chosen = solve_mclp(demand, distances, n_sites, radius_m) if len(sites) else []
        share = covered_share(demand, distances, chosen, radius_m) if chosen else 0.0
        suggested = sites[sites["site_id"].isin(chosen)][["site_id", "lat", "lon", "near"]].reset_index(drop=True)
        say(f"  {n_sites} suggested bin spots reach about {share:.0%} of estimated foot traffic within {radius_m} m")

        ranked = curve = None
        if bins is not None and len(bins):
            b = bins.copy()
            if "bin_id" not in b:
                b["bin_id"] = [f"B{i:03d}" for i in range(1, len(b) + 1)]
            pts = gpd.GeoDataFrame({"site_id": b["bin_id"].astype(str)},
                                   geometry=gpd.points_from_xy(b["lon"], b["lat"]), crs=LATLON).to_crs(meters)
            bin_dist = _candidates.build_distances(demand, pts)
            b["bin_id"] = b["bin_id"].astype(str)
            ranked = rank_receptacles(demand, b, bin_dist, radius_m)
            curve = recycling_curve(ranked, ks=range(1, min(30, len(ranked)) + 1))
            k = min(10, len(ranked))
            say(f"  your {len(ranked)} bins ranked: the busiest {k} serve about {top_share(ranked, k):.0%} "
                f"of estimated foot traffic")
    return CampusResult(name, meters, round(shape.area / 1e6, 2), demand, sites, distances,
                        suggested, share, ranked, curve)


def campus_map(result, path=None):
    """Interactive map: estimated foot traffic, suggested spots, and your ranked bins if given."""
    import folium

    d = result.demand.to_crs(LATLON)
    m = folium.Map(location=[d["lat"].mean(), d["lon"].mean()], zoom_start=16, tiles="OpenStreetMap")
    wmax = d["weight"].max()
    dem = folium.FeatureGroup(name="Estimated foot traffic (bigger = busier)").add_to(m)
    for _, r in d.iterrows():
        folium.CircleMarker([r["lat"], r["lon"]], radius=3 + 12 * (r["weight"] / wmax) ** 0.5, color="#52514e",
                            weight=1, fill=True, fill_opacity=0.2,
                            tooltip=f"{r['name'] or '(no name)'} [{r['use_type']}]").add_to(dem)
    sug = folium.FeatureGroup(name=f"Suggested bin spots ({len(result.suggested)})").add_to(m)
    for _, r in result.suggested.iterrows():
        folium.CircleMarker([r["lat"], r["lon"]], radius=9, color="white", weight=2, fill=True,
                            fill_color="#13284C", fill_opacity=1,
                            tooltip=f"Suggested spot {r['site_id']}" + (f" near {r['near']}" if r["near"] else "")).add_to(sug)
    if result.ranked is not None:
        rk = folium.FeatureGroup(name="Your bins, ranked (red = busiest 10)").add_to(m)
        for _, r in result.ranked.iterrows():
            top = r["rank"] <= 10
            folium.CircleMarker([r["lat"], r["lon"]], radius=8 if top else 4, color="white", weight=1, fill=True,
                                fill_color="#C41230" if top else "#9aa0a6", fill_opacity=1,
                                tooltip=f"#{r['rank']} {r['bin_id']}: {r['share']:.1%} of estimated foot traffic").add_to(rk)
    folium.LayerControl(collapsed=False).add_to(m)
    if path:
        m.save(path)
    return m


def run(name, bins_csv=None, n_sites=10, radius_m=50, verbose=True):
    """The whole thing in one call: download the campus, analyze it, save the map. Returns the result."""
    from binopt.current_bins import load_current_bins

    osm_dir = fetch_campus(name, verbose=verbose)
    bins = None
    if bins_csv:
        uni = gpd.read_file(osm_dir / "university.geojson").to_crs(LATLON)
        c = uni.geometry.iloc[0].representative_point()
        bins = load_current_bins(bins_csv, center=(c.y, c.x), verbose=verbose)
    result = analyze(osm_dir, name, bins, n_sites, radius_m, verbose)
    out = osm_dir.parent
    result.suggested.to_csv(out / "suggested_sites.csv", index=False)
    if result.ranked is not None:
        result.ranked.to_csv(out / "ranked_bins.csv", index=False)
    campus_map(result, out / "campus_map.html")
    if verbose:
        print(f"Saved: {out / 'suggested_sites.csv'}, {out / 'campus_map.html'}"
              + (f", {out / 'ranked_bins.csv'}" if result.ranked is not None else ""))
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Run the bin model on any campus.")
    ap.add_argument("campus", help='e.g. "University of the Pacific, Stockton, California"')
    ap.add_argument("--bins", help="optional CSV of your bins with lat/lon columns (see templates/)")
    ap.add_argument("--sites", type=int, default=10, help="how many bin spots to suggest (default 10)")
    ap.add_argument("--radius", type=int, default=50, help="walking reach in meters (default 50)")
    a = ap.parse_args()
    run(a.campus, a.bins, a.sites, a.radius)
