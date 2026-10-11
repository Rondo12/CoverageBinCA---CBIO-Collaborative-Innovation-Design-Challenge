"""Interactive web map of the plan (Folium = a Python remote control for Leaflet web maps).

Layers you can switch on and off: estimated demand, every receptacle, the busiest ones to
upgrade first, the added receptacle, and the gaps (housing / event venues) to ask Facilities
about. Street map and satellite backgrounds. Fresno State colors: red #C41230, blue #13284C.

It shows Facilities' receptacle layout, so it's saved privately: data/private/plan_map.html.
In Colab, the notebook displays it inline.
"""

from pathlib import Path

import folium

ROOT = Path(__file__).resolve().parent.parent
BLUE, RED, GRAY = "#13284C", "#C41230", "#9aa0a6"


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

    gaps = folium.FeatureGroup(name="No outdoor bin nearby: ask Facilities").add_to(m)
    for _, r in plan.gaps[plan.gaps["group"].notna()].iterrows():
        folium.Marker([r["lat"], r["lon"]], icon=folium.Icon(color="black", icon="question-sign"),
                      tooltip=f"{r['group']}: {r['name'] if isinstance(r['name'], str) else '(no name)'} "
                              f"({r['share']:.1%} of demand), no receptacle within {plan.radius_m} m "
                              "on the 2021 map").add_to(gaps)

    rest = folium.FeatureGroup(name=f"Other receptacles ({len(plan.ranked) - plan.top_k})").add_to(m)
    top = folium.FeatureGroup(name=f"Busiest {plan.top_k} receptacles (upgrade first)").add_to(m)
    for _, r in plan.ranked.iterrows():
        tip = f"#{r['rank']} {r['bin_id']}: about {r['share']:.1%} of estimated foot traffic" + (f" ({r['serves']})" if r["serves"] else "")
        if r["rank"] <= plan.top_k:
            folium.CircleMarker([r["lat"], r["lon"]], radius=9, color="white", weight=2, fill=True,
                                fill_color=RED, fill_opacity=1, tooltip=tip).add_to(top)
        else:
            folium.CircleMarker([r["lat"], r["lon"]], radius=4, color="white", weight=1, fill=True,
                                fill_color=GRAY, fill_opacity=1, tooltip=tip).add_to(rest)
    qt = folium.FeatureGroup(name=f"Quiet receptacles to review ({len(plan.quiet)})").add_to(m)
    for _, r in plan.quiet.iterrows():
        folium.CircleMarker([r["lat"], r["lon"]], radius=9, color="#0b0b0b", weight=3, fill=True, fill_color="white",
                            fill_opacity=1, tooltip=f"Review {r['bin_id']} near {r['near']}: no building's closest bin, "
                                                    f"another bin {r['pair_m']:.0f} m away. Check the fill log before moving.").add_to(qt)
    new = folium.FeatureGroup(name=f"Add {plan.add} receptacle", show=bool(plan.add)).add_to(m)
    for _, r in plan.new_spots.iterrows():
        folium.RegularPolygonMarker([r["lat"], r["lon"]], number_of_sides=4, radius=11, color="white",
                                    weight=1, fill_color=BLUE, fill_opacity=1,
                                    tooltip=f"Add a receptacle here: reaches {r['near']}").add_to(new)
        folium.Circle([r["lat"], r["lon"]], radius=plan.radius_m, color=BLUE, weight=1,
                      fill=True, fill_opacity=0.10).add_to(new)

    title = (f"Rebalance by foot traffic: {plan.top_k} of {len(plan.ranked)} receptacles handle about {plan.top_k_share:.0%} of it; "
             f"{len(plan.quiet)} quiet ones to review. Academic core coverage today {plan.today_core:.0%}. PLACEHOLDER demand; not diversion.")
    m.get_root().html.add_child(folium.Element(
        f'<div style="position:fixed;top:10px;left:50px;right:220px;z-index:9999;background:white;padding:6px 10px;'
        f'border-left:5px solid {RED};border-radius:6px;font:14px sans-serif;box-shadow:0 1px 4px rgba(0,0,0,.3)">{title}</div>'))
    folium.LayerControl(collapsed=False).add_to(m)
    m.save(path)
    return m
