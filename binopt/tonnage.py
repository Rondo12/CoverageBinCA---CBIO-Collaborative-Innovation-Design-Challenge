"""Read Facilities' hauling report: how many tons of trash and recycling left campus each month.

Simple version:
    The spreadsheet "2018-2020 Tonnage Report.xlsx" (from Facilities, via Mid Valley Disposal)
    has one block per year with a row per month: Trash, Recycle, Green Waste, Total. We read the
    Mid Valley columns (the campus hauler for trash and recycling) into one tidy table:
    year, month, trash_tons, recycling_tons, green_tons.
    Then "recycling share" = recycling / (trash + recycling): of the material in the trash and
    recycling bins, how much went to recycling. (Green waste is mostly tree trimmings, so it's
    kept separate.)

Technical version:
    The sheet is laid out for people, not code: a year number on its own row, then a header
    row, then month rows. We walk the rows, remember the last year we saw, and keep rows whose
    first cell is a month name and whose Trash and Recycle cells are numbers.

Data runs Jan 2018 to Jun 2022: the latest available to us. Private (data/private/).
"""

from pathlib import Path

import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = ROOT / "data" / "private" / "2018-2020 Tonnage Report.xlsx"
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def load_tonnage(path=DEFAULT_FILE):
    """Monthly Mid Valley tonnage: year, month (1-12), trash_tons, recycling_tons, green_tons."""
    ws = openpyxl.load_workbook(path, data_only=True)["Tonnage"]
    year, rows = None, []
    for r in ws.iter_rows(values_only=True):
        first = r[0]
        if isinstance(first, (int, float)) and 2000 < first < 2100:   # a year label row
            year = int(first)
            continue
        if year and isinstance(first, str) and first.strip()[:3].lower() in MONTHS:
            trash, recyc, green = r[1], r[2], r[3]
            if isinstance(trash, (int, float)) and isinstance(recyc, (int, float)):
                rows.append({"year": year, "month": MONTHS.index(first.strip()[:3].lower()) + 1,
                             "trash_tons": float(trash), "recycling_tons": float(recyc),
                             "green_tons": float(green) if isinstance(green, (int, float)) else None})
    df = pd.DataFrame(rows).drop_duplicates(["year", "month"])
    df["date"] = pd.to_datetime(dict(year=df["year"], month=df["month"], day=1))
    return df.sort_values("date").reset_index(drop=True)


def yearly_summary(df):
    """Per year: months of data, average tons per month, and recycling share."""
    g = df.groupby("year").agg(months=("month", "count"), trash_tons=("trash_tons", "mean"),
                               recycling_tons=("recycling_tons", "mean"),
                               green_tons=("green_tons", "mean"))
    sums = df.groupby("year")[["trash_tons", "recycling_tons"]].sum()
    g["recycling_share"] = sums["recycling_tons"] / (sums["trash_tons"] + sums["recycling_tons"])
    return g.round(3).reset_index()


def size_of_prize(yearly, year=2021, targets=None):
    """How many tons a month would have to move from trash to recycling to hit a target share?

    Simple: keep the total tonnage of that year the same, and ask how much of the trash would need
    to go into recycling instead for recycling to be, say, 46% (2018's level) or 65% (SB 54's
    target for single-use packaging, used here only as a reference point).
    Returns {label: {"share": target, "tons_per_month": t, "tons_per_year": 12 * t}} plus the
    year's own numbers under "base".
    """
    if targets is None:
        first = yearly.sort_values("year").iloc[0]
        targets = {f"back to {int(first['year'])}": float(first["recycling_share"]), "SB 54 reference": 0.65}
    row = yearly[yearly["year"] == year].iloc[0]
    total = float(row["trash_tons"] + row["recycling_tons"])
    out = {"base": {"year": year, "trash_tons": float(row["trash_tons"]), "recycling_tons": float(row["recycling_tons"]),
                    "recycling_share": float(row["recycling_share"])}}
    for label, share in targets.items():
        t = max(0.0, share * total - float(row["recycling_tons"]))
        out[label] = {"share": share, "tons_per_month": t, "tons_per_year": 12 * t}
    return out


if __name__ == "__main__":
    print(yearly_summary(load_tonnage()).to_string(index=False))
