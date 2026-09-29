# Data contract

**What this is.** An agreement about the files that pass between the campus data (Eric) and the optimization model (Ronnie). If both sides stick to these file names and column names, either side can change its code without breaking the other.

**The flow:**

```
OpenStreetMap snapshots ──► 01_campus_data.ipynb (Eric) ──► data/demand.csv
                                                           data/candidates.csv
                                                           data/distances.csv
                                                                  │
                                                                  ▼
                                                   02_model.ipynb (Ronnie, PuLP)
                                                                  │
                                                                  ▼
                                                      outputs/chosen_sites.csv ──► map (Eric)
```

**Honesty rule.** Every number here is projected **coverage**: the share of estimated waste-generating foot traffic that has a bin station within reach. None of it is measured diversion. Anything marked `PLACEHOLDER` is an assumption, set in `binopt/config.py`.

**How to read a CSV in Python.** A CSV is a spreadsheet saved as plain text: one row per line, columns separated by commas.
```python
import pandas as pd
demand = pd.read_csv("data/demand.csv")   # a DataFrame: a table you can filter and sum
demand.head()                             # shows the first 5 rows
```

---

## Inputs to the model (written by Eric)

### 1. `data/demand.csv`: where waste is generated

One row per **demand point**: a place where people generate single-use packaging waste. Most rows are the center of a building; the rest are food/drink spots and parking lots.

| column | type | units | meaning |
|---|---|---|---|
| `demand_id` | text | | Unique ID, e.g. `D0001`. |
| `lat`, `lon` | number | degrees (WGS84) | Where the point is. |
| `weight` | number | relative demand units | How much waste-generating foot traffic we **estimate** here. Bigger = more. **Not a count of people or pounds.** `PLACEHOLDER` (see below). |
| `source` | text | | `building`, `food_drink` or `parking`. |
| `use_type` | text | | What the place is used for, e.g. `dining`, `classroom`, `library`, `office`, `cafe`, `vending_machine`. |
| `name` | text | | Name from OpenStreetMap, blank if none. |

How `weight` is estimated (all factors in `binopt/config.py`, all `PLACEHOLDER`):
- Buildings: footprint area (m²) × number of floors (1 if unknown) × use-type weight (dining/food high, classrooms/library medium, offices low).
- Parking lots: area × a low weight.
- Food and drink spots (cafes, restaurants, vending machines): a fixed extra weight, because eating and drinking is where single-use plastic shows up.

### 2. `data/candidates.csv`: where a bin station could go

One row per **candidate site**: a spot along a walkway or just outside a building entrance. Never inside a building. One site = one **co-located station** (trash + recycling + compost together).

| column | type | units | meaning |
|---|---|---|---|
| `site_id` | text | | Unique ID, e.g. `S0001`. |
| `lat`, `lon` | number | degrees | Where the site is. |
| `kind` | text | | `walkway` or `entrance`. |
| `near` | text | | Name of the nearest building (helps Facilities find it). |
| `accessible` | text | | `unknown`, `yes` or `no`. Starts as `unknown` for every site: OpenStreetMap doesn't reliably record wheelchair routes, curb cuts or surfaces, so Facilities must confirm. The model may ignore this column for now. |

### 3. `data/distances.csv`: how far each demand point is from each site

One row per (demand point, site) pair that are **200 m or closer** (`MAX_DISTANCE_M`). Pairs farther apart are left out; treat a missing pair as "too far to cover".

| column | type | units | meaning |
|---|---|---|---|
| `demand_id` | text | | Matches `demand.csv`. |
| `site_id` | text | | Matches `candidates.csv`. |
| `distance_m` | number | meters | **Straight-line** distance. Real walking distance is longer, so real coverage may be a bit lower. |

**"Covered" means:** `distance_m <= radius`. The radius comes from `binopt/config.py`:
```python
from binopt.config import DEFAULT_RADIUS_M, COVERAGE_RADII_M, N_SITES
# DEFAULT_RADIUS_M = 50            PLACEHOLDER
# COVERAGE_RADII_M = [30, 50, 75]  PLACEHOLDER, for the optional sensitivity check
# N_SITES = 20                     PLACEHOLDER: how many stations to place ("p")
```

### 4. Current bins (optional, from Facilities)

If Facilities sends their current bin locations, the file goes in `data/private/` (never committed while the repo is public) and `binopt/current_bins.py` turns it into a table with `bin_id, lat, lon, units` (`units` = number of co-located stations, default 1). For now this is only drawn on the map; the model doesn't need it. If there's no file, there are no current bins. We never make up a current layout.

---

## Output of the model (written by Ronnie)

### `outputs/chosen_sites.csv`

One row per **chosen site**. This file is committed to GitHub so the map can read it.

| column | type | units | meaning |
|---|---|---|---|
| `site_id` | text | | A `site_id` from `candidates.csv`. |
| `lat`, `lon` | number | degrees | Copied from `candidates.csv`. |
| `covered_weight` | number | relative demand units | Total `weight` of the demand points this site covers. |
| `covered_share` | number | fraction 0–1 | `covered_weight` ÷ total weight of **all** demand points. |
| `radius_m` | number | meters | The coverage radius used in this run. |
| `n_sites` | integer | | How many sites the model was allowed to choose (p). |

**No double counting.** A demand point within reach of two chosen sites is credited only to the **nearest** one. That way the per-site numbers add up to the total, and:

> **Total projected coverage** for a run = sum of `covered_share` over that run's rows.

Print that total in the notebook, for example "Projected coverage: 55.6% of estimated demand within 50 m of a station".

**Optional: sensitivity check.** Run the model once per radius in `COVERAGE_RADII_M` (PLACEHOLDER values) and stack all the results in the same `chosen_sites.csv`. The `radius_m` column tells the runs apart. The map shows one radius at a time (`DEFAULT_RADIUS_M` first).

**Getting the file to GitHub from Colab.** Colab's "Save a copy in GitHub" only saves the notebook, not files it writes. After the model runs, download `outputs/chosen_sites.csv` (the notebook's last cell does this) and upload it on github.com: open the `outputs/` folder, then **Add file > Upload files**. Upload it to a new branch and open a pull request.

---

## The example dataset: `data/example/`

Made-up points (not real buildings) on a small grid near the middle of campus, so you can build and test the model before using the real data. Same columns as above.

**Demand (8 points, total weight 225):**

| id | weight | what |
|---|---|---|
| D1 | 50 | dining hall |
| D2 | 20 | cafe |
| D3 | 30 | classroom building |
| D4 | 40 | library |
| D5 | 10 | office |
| D6 | 35 | snack bar |
| D7 | 15 | vending machine |
| D8 | 25 | parking lot |

**Sites:** S1–S5. **Distances that matter** (everything else is over 80 m):

| pair | meters | | pair | meters |
|---|---|---|---|---|
| D1–S1 | 14.1 | | D6–S5 | 28.3 |
| D2–S1 | 36.1 | | D7–S3 | 36.1 |
| D3–S2 | 22.4 | | D7–S5 | 76.2 |
| D4–S3 | 31.6 | | D8–S2, D8–S3, D8–S4 | 70.7 each |
| D5–S4 | 28.0 | | | |

### Check your model: the right answers for p = 2 sites

| radius | best sites | covered weight per site | total | coverage |
|---|---|---|---|---|
| 30 m | S1, S5 | S1 = 50 (D1), S5 = 35 (D6) | 85 | 37.8% |
| 50 m | S1, S3 | S1 = 70 (D1+D2), S3 = 55 (D4+D7) | 125 | 55.6% |
| 75 m | S1, S3 | S1 = 70 (D1+D2), S3 = 80 (D4+D7+D8) | 150 | 66.7% |

Worked through for 50 m: the sites cover S1 → D1, D2 (70); S2 → D3 (30); S3 → D4, D7 (55); S4 → D5 (10); S5 → D6 (35). Nothing is covered by two sites at 50 m, so the best two are the two biggest: S1 + S3 = 125 of 225 = 55.6%.

The same answers are in `data/example/expected_chosen_sites.csv`, in the exact output format. `tests/test_example_data.py` double-checks them by trying all 10 pairs.
