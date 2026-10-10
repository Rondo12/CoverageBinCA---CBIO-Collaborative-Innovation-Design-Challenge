"""Still images for the video, the report and the notebook (matplotlib, no internet needed).

1. tonnage.png   Trash vs. recycling hauled per month, 2018 to mid-2022, with the recycling share.
2. plan_map.png  Campus map: receptacles that stay, the ones to move, where they go, and the
                 gaps (housing, event venues) to ask Facilities about.

Both are built from Facilities' data, so they're saved in data/private/figures/.
Colors: blue = recycling / recommended, orange = trash / today. Two hues only, checked for
color-blind separation; every series is also labeled in words, never color alone.
"""

from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from binopt.boundary import LATLON, METERS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "private" / "figures"
OSM = ROOT / "data" / "osm"

BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e4e2dc"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED})


def tonnage_figure(monthly, yearly, path=None):
    """Two stacked panels sharing the time axis (never two y-scales on one chart):
    top = tons per month for trash and recycling; bottom = recycling share per year."""
    fig, (a, b) = plt.subplots(2, 1, figsize=(11, 7), sharex=False,
                               gridspec_kw={"height_ratios": [3, 2], "hspace": 0.45})
    a.plot(monthly["date"], monthly["trash_tons"], color=ORANGE, lw=2)
    a.plot(monthly["date"], monthly["recycling_tons"], color=BLUE, lw=2)
    last = monthly.iloc[-1]
    a.annotate("Trash (landfill)", (last["date"], last["trash_tons"]), xytext=(8, 0),
               textcoords="offset points", color=INK, va="center")
    a.annotate("Recycling", (last["date"], last["recycling_tons"]), xytext=(8, 0),
               textcoords="offset points", color=INK, va="center")
    a.set_ylabel("Tons per month")
    a.set_title("Fresno State trash and recycling hauled by Mid Valley Disposal, Jan 2018 to Jun 2022",
                loc="left", color=INK, fontsize=12)
    a.grid(axis="y", color=GRID); a.set_ylim(bottom=0); a.set_axisbelow(True)
    for s in ("top", "right"):
        a.spines[s].set_visible(False)

    labels = [f"{y}" if m == 12 else f"{y}\n(Jan to Jun)" for y, m in zip(yearly["year"], yearly["months"])]
    shares = yearly["recycling_share"] * 100
    bars = b.bar(labels, shares, color=BLUE, width=0.55)
    for bar, v in zip(bars, shares):
        b.text(bar.get_x() + bar.get_width() / 2, v + 1.5, f"{v:.0f}%", ha="center", color=INK)
    b.set_ylabel("Recycling share (%)")
    b.set_title("Recycling as a share of trash + recycling", loc="left", color=INK, fontsize=12)
    b.set_ylim(0, 60); b.grid(axis="y", color=GRID); b.set_axisbelow(True)
    for s in ("top", "right"):
        b.spines[s].set_visible(False)
    fig.text(0.01, 0.005, "Source: Mid Valley Disposal tonnage report, shared by Fresno State Facilities. "
             "Latest data available to us runs through June 2022.", color=MUTED, fontsize=9)
    path = path or OUT / "tonnage.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def plan_map_figure(plan, path=None):
    """Campus base map from the OpenStreetMap snapshots, plus the plan."""
    to_m = lambda df: gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]),  # noqa: E731
                                       crs=LATLON).to_crs(METERS)
    boundary = gpd.read_file(OSM / "campus_boundary.geojson").to_crs(METERS)
    buildings = gpd.read_file(OSM / "buildings.geojson").to_crs(METERS)
    walk = gpd.read_file(OSM / "walkways.geojson").to_crs(METERS)
    clip = boundary.buffer(150).iloc[0]
    buildings = buildings[buildings.intersects(clip)]
    walk = walk.clip(clip)

    fig, ax = plt.subplots(figsize=(12, 9))
    boundary.plot(ax=ax, color="#f6f5f1", edgecolor=MUTED, lw=1)
    walk.plot(ax=ax, color="#d9d6cf", lw=0.8)
    buildings.plot(ax=ax, color="#cfccc4", edgecolor="#b9b5ab", lw=0.4)

    gaps = plan.demand[~plan.demand["in_core"] & ~plan.demand["covered_today"] &
                       plan.demand["use_type"].isin(["dormitory", "event"])]
    gid = set(gaps["osm_id"])
    gb = buildings[buildings["osm_id"].isin(gid)] if "osm_id" in buildings else buildings.iloc[0:0]
    if len(gb):
        gb.plot(ax=ax, facecolor="none", edgecolor=INK, lw=1.4, hatch="////")

    kept, frm, to = to_m(plan.kept), to_m(plan.moves_from), to_m(plan.moves_to)
    kept.plot(ax=ax, color=ORANGE, markersize=22, edgecolor="white", lw=0.6, zorder=3)
    frm.plot(ax=ax, color="white", markersize=60, edgecolor=ORANGE, lw=2, zorder=4)
    to.plot(ax=ax, color=BLUE, markersize=90, marker="D", edgecolor="white", lw=1, zorder=5)
    # Number each new spot on the map and list the names in a box: no overlapping labels.
    to = to.sort_values("lon").reset_index(drop=True)
    for k, r in to.iterrows():
        ax.annotate(str(k + 1), (r.geometry.x, r.geometry.y), xytext=(0, 11), textcoords="offset points",
                    ha="center", fontsize=9, fontweight="bold", color=INK)
    names = "\n".join(f"{k + 1}. near {r['near']}" for k, r in to.iterrows())
    ax.text(0.01, 0.99, "New spots\n" + names, transform=ax.transAxes, ha="left", va="top", fontsize=8.5,
            color=INK, bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=MUTED, lw=0.6))

    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    handles = [
        Line2D([], [], marker="o", ls="", color=ORANGE, markeredgecolor="white", markersize=7,
               label=f"Receptacle that stays ({len(kept)})"),
        Line2D([], [], marker="o", ls="", markerfacecolor="white", markeredgecolor=ORANGE, mew=2,
               markersize=8, label=f"Receptacle to move ({len(frm)})"),
        Line2D([], [], marker="D", ls="", color=BLUE, markeredgecolor="white", markersize=9,
               label=f"New spot ({len(to)})"),
        Patch(facecolor="none", edgecolor=INK, hatch="////", label="Gap: housing / event venue, ask Facilities"),
    ]
    ax.legend(handles=handles, loc="lower left", frameon=True, fontsize=9)
    ax.set_title(f"Move {len(frm)} of {len(kept) + len(frm)} receptacles: projected coverage of the academic "
                 f"core {plan.today_core:.0%} to {plan.after_core:.0%} (within {plan.radius_m} m)",
                 loc="left", color=INK, fontsize=12)
    ax.text(0.0, -0.03, "Receptacles from Facilities' 2021 map (positions within ~10 to 20 m). Demand is "
            "estimated from building size and use (PLACEHOLDER). Coverage is projected, not measured diversion. "
            "Base map (c) OpenStreetMap contributors.", transform=ax.transAxes, fontsize=8, color=MUTED, va="top",
            wrap=True)
    minx, miny, maxx, maxy = boundary.total_bounds
    ax.set_xlim(minx - 60, maxx + 60); ax.set_ylim(miny - 60, maxy + 60)
    ax.set_axis_off(); ax.set_aspect("equal")
    path = path or OUT / "plan_map.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


if __name__ == "__main__":
    from binopt.plan import make_plan
    from binopt.tonnage import load_tonnage, yearly_summary

    m = load_tonnage()
    print(tonnage_figure(m, yearly_summary(m)))
    print(plan_map_figure(make_plan()))
