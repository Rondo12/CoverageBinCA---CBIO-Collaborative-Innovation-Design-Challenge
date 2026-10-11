"""Checks for size_of_prize: tons a month to move from trash to recycling to hit a target share."""
import pandas as pd
import pytest

from binopt.tonnage import size_of_prize


def yearly():
    # 2018: 40 t recycling of 100 total (40%); 2021: 20 of 100 (20%)
    return pd.DataFrame({"year": [2018, 2021], "trash_tons": [60.0, 80.0], "recycling_tons": [40.0, 20.0],
                         "recycling_share": [0.40, 0.20]})


def test_back_to_first_year_by_hand():
    p = size_of_prize(yearly(), year=2021)
    assert p["base"]["recycling_share"] == pytest.approx(0.20)
    assert p["back to 2018"]["tons_per_month"] == pytest.approx(20.0)   # 40% of 100 t - 20 t
    assert p["back to 2018"]["tons_per_year"] == pytest.approx(240.0)
    assert p["SB 54 reference"]["tons_per_month"] == pytest.approx(45.0)  # 65% of 100 t - 20 t


def test_never_negative_when_already_above_target():
    p = size_of_prize(yearly(), year=2018, targets={"low": 0.10})
    assert p["low"]["tons_per_month"] == 0.0
