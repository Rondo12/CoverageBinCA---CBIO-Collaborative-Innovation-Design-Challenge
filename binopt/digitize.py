"""Turn Facilities' 2021 receptacle map (a PDF picture) into real map points.

Simple version:
    The 2021 map is a drawing, not GPS data. We do two things:
    1. FIND the markers. Every yellow dot (a receptacle people use), red square (trash dumpster),
       blue square (recycling dumpster) and green square (organics) has its own color, so we look
       for blobs of that color and record where each one sits on the picture (pixel x, y).
    2. PIN the picture to the real world. Seven street corners (Shaw x Cedar, Barstow x Woodrow,
       ...) are both on the drawing and in OpenStreetMap, so we know their pixel position AND their
       GPS position. From those pairs we work out one formula that turns ANY pixel into GPS.
       Analogy: pinning a paper map onto Apple Maps at a few corners so every dot lands on real
       ground.

Technical version:
    Rendering: PyMuPDF at 150 dpi. Detection: per-color RGB thresholds -> connected components
    (scipy.ndimage.label). Yellow dots that touch each other merge into one blob, so blob area /
    typical dot area estimates how many dots it holds, and k-means splits it. Georeferencing: a
    least-squares affine transform (6 numbers: scale, rotation, shear, shift) from pixels to UTM
    zone 11N meters, fitted on the control points, then converted to lat/lon.

Accuracy: the map is a simplified drawing, so positions are good to roughly 10 to 20 m (the
script prints the exact error). Fine for "which walkway is this bin on", not for surveying.

Privacy: the map came from Facilities, so the PDF and everything made from it stay in
data/private/ (gitignored). The control points (street corners) are public and live in config.py.

Run from the repo root:
    python -m binopt.digitize
"""

from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy import ndimage
from scipy.cluster.vq import kmeans2

from binopt import config

ROOT = Path(__file__).resolve().parent.parent
PRIVATE_DIR = ROOT / "data" / "private"
UTM = "EPSG:32611"   # UTM zone 11N: x/y in meters, good for Fresno

# Colors of each marker type on the 2021 map (R, G, B rules). A pixel belongs to a type when its
# color passes the rule. Found by sampling the PDF; "kind" is what the legend says it means.
COLOR_RULES = {
    "receptacle": lambda r, g, b: (r > 170) & (g > 170) & (b < 90) & (abs(r - g) < 30),  # yellow
    "trash": lambda r, g, b: (r > 140) & (g < 70) & (b < 80),                             # red
    "recycling": lambda r, g, b: (b > 190) & (r < 120) & (g > 120) & (g < 215),           # blue
    "organics": lambda r, g, b: (g > 120) & (r < 80) & (b < 120) & (g - r > 60),          # green
}
MIN_BLOB_PX = 60        # smaller blobs are anti-aliasing specks, not markers
DOT_AREA_PX = 480       # one yellow dot at 150 dpi; a blob of ~960 px is two dots touching


def render(pdf_path, dpi=150):
    """PDF page 1 -> numpy array of shape (height, width, 3), values 0-255."""
    import pymupdf  # imported here so the rest of binopt doesn't need it

    page = pymupdf.open(pdf_path)[0]
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).astype(int)


def in_legend(x, y):
    """The legend box (top left) and the footer (bottom) use the same colors; skip them."""
    return (x < 470 and y < 380) or y > 1330


def find_markers(img):
    """Return a table: kind, px, py (pixel center of each marker)."""
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    rows = []
    for kind, rule in COLOR_RULES.items():
        mask = rule(r, g, b)
        if kind == "receptacle":
            # Dots have a black outline and some are drawn over buildings, which can split one
            # dot into pieces. Closing + filling holes glues the pieces back together.
            mask = ndimage.binary_fill_holes(ndimage.binary_closing(mask, iterations=4))
        labels, n = ndimage.label(mask)                 # number each separate blob 1..n
        for i, box in enumerate(ndimage.find_objects(labels), start=1):
            ys, xs = np.nonzero(labels[box] == i)
            ys, xs = ys + box[0].start, xs + box[1].start
            if len(xs) <= MIN_BLOB_PX or in_legend(xs.mean(), ys.mean()):
                continue
            count = max(1, round(len(xs) / DOT_AREA_PX)) if kind == "receptacle" else 1
            if count == 1:
                centers = [(xs.mean(), ys.mean())]
            else:   # several dots touching: split the blob into `count` groups (k-means)
                centers, _ = kmeans2(np.c_[xs, ys].astype(float), count, seed=1, minit="++")
            for x, y in centers:
                rows.append({"kind": kind, "px": round(float(x), 1), "py": round(float(y), 1)})
    markers = pd.DataFrame(rows)
    return drop_overlap_green(markers)


def drop_overlap_green(markers, max_px=30):
    """Where a yellow dot is drawn over a blue square, the overlap prints as green and looks like
    an organics bin. Real organics squares sit away from yellow dots, so a "green" within
    max_px of a receptacle is an overlap, not a bin. (Checked by eye on the 2021 map.)"""
    rec = markers.loc[markers["kind"] == "receptacle", ["px", "py"]].to_numpy()
    if len(rec) == 0:
        return markers
    def near_dot(row):
        return np.hypot(rec[:, 0] - row["px"], rec[:, 1] - row["py"]).min() < max_px
    fake = (markers["kind"] == "organics") & markers.apply(near_dot, axis=1)
    return markers[~fake].reset_index(drop=True)


def fit_georeference(control_points=None):
    """Fit pixel -> UTM meters. Returns (coef 3x2, per-point error in m, leave-one-out errors).

    Each control point gives two equations (one for x, one for y). With 7 points we have 14
    equations for 6 unknowns, so least squares finds the best compromise and the leftover
    error tells us how good the fit is.
    """
    cps = control_points or config.MAP_2021_CONTROL_POINTS
    to_utm = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
    px = np.array([c["px"] for c in cps.values()], dtype=float)
    lat = np.array([c["lat"] for c in cps.values()])
    lon = np.array([c["lon"] for c in cps.values()])
    east, north = to_utm.transform(lon, lat)
    A = np.c_[px, np.ones(len(px))]          # each row: [px, py, 1]
    target = np.c_[east, north]
    coef, *_ = np.linalg.lstsq(A, target, rcond=None)
    err = np.linalg.norm(A @ coef - target, axis=1)
    # Leave-one-out: fit without point i, then see how far off point i lands. An honest check.
    loo = []
    for i in range(len(A)):
        keep = np.arange(len(A)) != i
        c, *_ = np.linalg.lstsq(A[keep], target[keep], rcond=None)
        loo.append(float(np.linalg.norm(A[i] @ c - target[i])))
    return coef, dict(zip(cps, err.round(1))), loo


def to_latlon(markers, coef):
    to_ll = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)
    A = np.c_[markers[["px", "py"]].to_numpy(), np.ones(len(markers))]
    east, north = (A @ coef).T
    lon, lat = to_ll.transform(east, north)
    out = markers.copy()
    out["lat"], out["lon"] = np.round(lat, 6), np.round(lon, 6)
    return out


def main(pdf_path=None):
    pdf_path = Path(pdf_path or PRIVATE_DIR / config.MAP_2021_PDF)
    if not pdf_path.exists():
        raise SystemExit(f"Not found: {pdf_path}. Put Facilities' 2021 receptacle map in data/private/.")
    img = render(pdf_path)
    markers = find_markers(img)
    coef, err, loo = fit_georeference()
    print("Georeference (pixel -> GPS) fit, error at each street corner:")
    for name, e in err.items():
        print(f"  {name:<20} {e:5.1f} m")
    print(f"  leave-one-out: mean {np.mean(loo):.1f} m, worst {np.max(loo):.1f} m")
    points = to_latlon(markers, coef)
    print("Markers found:", points["kind"].value_counts().to_dict())
    print("  (map legend says trash 40, recycling 29, organics 3; check the counts are close."
          " Stacked squares at one enclosure count separately; a marker hidden under another can't be seen.)")

    # Receptacles = the layout the model compares against. One row per receptacle.
    rec = points[points["kind"] == "receptacle"].reset_index(drop=True)
    rec.insert(0, "bin_id", [f"R{i:03d}" for i in range(1, len(rec) + 1)])
    rec["units"] = 1
    rec[["bin_id", "lat", "lon", "units", "px", "py"]].to_csv(PRIVATE_DIR / "current_bins.csv", index=False)

    dump = points[points["kind"] != "receptacle"].reset_index(drop=True)
    dump.insert(0, "dumpster_id", [f"D{i:03d}" for i in range(1, len(dump) + 1)])
    dump.to_csv(PRIVATE_DIR / "dumpsters_2021.csv", index=False)
    print(f"Wrote data/private/current_bins.csv ({len(rec)} receptacles) and "
          f"data/private/dumpsters_2021.csv ({len(dump)} dumpsters). Private: not committed.")
    check_map(rec, dump)
    return points


def check_map(rec, dump, path=PRIVATE_DIR / "digitize_check.html"):
    """A map to check the digitizing by eye: every marker on a satellite photo and a street map.

    Open it in a browser and ask: do the yellow dots sit on walkways and by doors? Do the
    dumpsters sit in service areas? Private (it shows Facilities' layout), so it stays in
    data/private/.
    """
    import folium

    m = folium.Map(location=[36.8125, -119.746], zoom_start=16, tiles=None)
    folium.TileLayer("OpenStreetMap", name="Street map").add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Satellite").add_to(m)
    colors = {"receptacle": "#e6c200", "trash": "#c0392b", "recycling": "#2e86de", "organics": "#27ae60"}
    layer = folium.FeatureGroup(name=f"Receptacles ({len(rec)})").add_to(m)
    for _, r in rec.iterrows():
        folium.CircleMarker([r["lat"], r["lon"]], radius=5, color="black", weight=1, fill=True,
                            fill_color=colors["receptacle"], fill_opacity=0.9,
                            tooltip=r["bin_id"]).add_to(layer)
    for kind, g in dump.groupby("kind"):
        layer = folium.FeatureGroup(name=f"{kind.title()} dumpsters ({len(g)})").add_to(m)
        for _, r in g.iterrows():
            folium.RegularPolygonMarker([r["lat"], r["lon"]], number_of_sides=4, radius=6,
                                        color="black", weight=1, fill_color=colors[kind],
                                        fill_opacity=0.9, tooltip=f"{r['dumpster_id']} {kind}").add_to(layer)
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(path)
    print(f"Check map: {path.relative_to(ROOT)} (open it in a browser)")


if __name__ == "__main__":
    main()
