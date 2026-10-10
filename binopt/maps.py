"""Interactive web map of the plan (Folium = a Python remote control for Leaflet web maps).

Layers you can switch on and off: estimated demand, receptacles that stay, receptacles to move,
new spots, and the gaps (housing / event venues) to ask Facilities about. Street map and
satellite backgrounds.

It shows Facilities' receptacle layout, so it's saved privately: data/private/plan_map.html.
In Colab, the notebook displays it inline.
"""

from pathlib import Path

import folium

ROOT = Path(__file__).resolve().parent.parent
BLUE, ORANGE = "#2a78d6", "#eb6834"


def plan_map(plan, path=ROOT / "data" / "private" / "plan_map.html"):
    m = folium.Map(location=[36.8125, -119.746], zoom_start=16, tiles=None)
    folium.TileLayer("OpenStreetMap", name="Street map").add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Satellite").add_to(m)

    # Demand: circle area grows with estimated weight. Gray = covered today, black ring = not covered.
    dem = folium.FeatureGroup(name="Estimated demand (PLACEHOLDER)", show=False).add_to(m)
    wmax = plan.demand["weight"].max()
    for _, r in plan.demand.iterrows():
        folium.CircleMarker([r["lat"], r["lon"]], radius=3 + 12 * (r["weight"] / wmax) ** 0.5,
                            color="#0b0b0b" if not r["covered_today"] else "#8a8880", weight=1,
                            fill=True, fill_opacity=0.15,
                            tooltip=f"{r['name'] if isinstance(r['name'], str) else '(no name)'} "
                                    f"[{r['use_type']}] {r['share']:.1%} of demand; "
                                    f"{'covered' if r['covered_today'] else 'NOT covered'} today").add_to(dem)

    gaps = folium.FeatureGroup(name="Gaps to ask Facilities about").add_to(m)
    for _, r in plan.gaps[plan.gaps["group"].notna()].iterrows():
        folium.Marker([r["lat"], r["lon"]], icon=folium.Icon(color="black", icon="question-sign"),
                      tooltip=f"{r['group']}: {r['name'] if isinstance(r['name'], str) else '(no name)'} "
                              f"({r['share']:.1%} of demand), no receptacle within {plan.radius_m} m "
                              "on the 2021 map").add_to(gaps)

    keep = folium.FeatureGroup(name=f"Receptacles that stay ({len(plan.kept)})").add_to(m)
    for _, r in plan.kept.iterrows():
        folium.CircleMarker([r["lat"], r["lon"]], radius=5, color="white", weight=1, fill=True,
                            fill_color=ORANGE, fill_opacity=1, tooltip=r["bin_id"]).add_to(keep)
    mv = folium.FeatureGroup(name=f"Receptacles to move ({len(plan.moves_from)})").add_to(m)
    for _, r in plan.moves_from.iterrows():
        folium.CircleMarker([r["lat"], r["lon"]], radius=8, color=ORANGE, weight=3, fill=True,
                            fill_color="white", fill_opacity=1, tooltip=f"move {r['bin_id']}").add_to(mv)
    new = folium.FeatureGroup(name=f"New spots ({len(plan.moves_to)})").add_to(m)
    for _, r in plan.moves_to.iterrows():
        folium.RegularPolygonMarker([r["lat"], r["lon"]], number_of_sides=4, radius=9, color="white",
                                    weight=1, fill_color=BLUE, fill_opacity=1,
                                    tooltip=f"new spot near {r['near']}").add_to(new)
        folium.Circle([r["lat"], r["lon"]], radius=plan.radius_m, color=BLUE, weight=1,
                      fill=True, fill_opacity=0.08).add_to(new)

    title = (f"Move {len(plan.moves_from)} receptacles: academic core {plan.today_core:.0%} to "
             f"{plan.after_core:.0%} projected coverage (within {plan.radius_m} m). PLACEHOLDER demand; not diversion.")
    m.get_root().html.add_child(folium.Element(
        f'<div style="position:fixed;top:10px;left:50px;z-index:9999;background:white;padding:6px 10px;'
        f'border-radius:6px;font:14px sans-serif;box-shadow:0 1px 4px rgba(0,0,0,.3)">{title}</div>'))
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(path)
    return m
