"""Checks for binopt/digitize.py that don't need the private PDF.

1. The georeference puts every street corner close to its real GPS spot.
2. Marker detection finds dots and squares on a small fake image we draw ourselves.
"""

import numpy as np

from binopt import config
from binopt.digitize import find_markers, fit_georeference, to_latlon
import pandas as pd


def test_georeference_is_accurate():
    coef, err, loo = fit_georeference()
    # The map is a simplified drawing, so ~20 m is the honest limit; anything worse means a
    # control point was typed wrong.
    assert max(err.values()) < 20
    assert max(loo) < 30


def test_control_points_round_trip():
    coef, _, _ = fit_georeference()
    cps = config.MAP_2021_CONTROL_POINTS
    pts = pd.DataFrame([{"px": c["px"][0], "py": c["px"][1]} for c in cps.values()])
    ll = to_latlon(pts, coef)
    for (_, row), c in zip(ll.iterrows(), cps.values()):
        # 0.0002 degrees is about 20 m
        assert abs(row["lat"] - c["lat"]) < 0.0002
        assert abs(row["lon"] - c["lon"]) < 0.0002


def test_find_markers_on_fake_image():
    img = np.full((1300, 1500, 3), 255)            # white page, away from the legend areas
    img[600:625, 700:725] = (255, 255, 0)          # one yellow dot
    img[600:625, 900:925] = (255, 255, 0)          # another
    img[800:810, 700:722] = (200, 30, 40)          # red square = trash dumpster
    img[800:810, 760:782] = (40, 150, 230)         # blue square = recycling dumpster
    img[1000:1010, 700:722] = (20, 160, 60)        # green square = organics, far from any dot
    img[1095:1120, 1000:1025] = (255, 255, 0)      # a yellow dot drawn over a blue square:
    img[1102:1112, 1025:1045] = (20, 160, 60)      # the overlap prints green right next to the dot
    img[1102:1112, 1045:1060] = (40, 150, 230)     # and the rest of the blue square shows
    m = find_markers(img)
    counts = m["kind"].value_counts().to_dict()
    # The overlap green must NOT count as organics.
    assert counts == {"receptacle": 3, "trash": 1, "recycling": 2, "organics": 1}
