# Method

**Honesty rule.** Reach and coverage numbers are **projected** from *estimated* foot traffic, not measured recycling. Every estimate is labeled `PLACEHOLDER` and set in `binopt/config.py`. Tonnage numbers come from Mid Valley Disposal's real hauling report.

## Pipeline

```
OpenStreetMap snapshots ──► binopt/build.py ──► data/demand.csv, data/candidates.csv, data/distances.csv
2021 receptacle map (private PDF) ──► binopt/digitize.py ──► 88 receptacles as GPS points (private)
                                         │
                                         ▼
          binopt/rank.py      rank receptacles by the foot traffic each one handles
          binopt/model.py     coverage model (Maximal Covering Location Problem, PuLP)
          binopt/scenarios.py today vs. optimal vs. moving 5 / 10 / 20, at 30 / 50 / 75 m
          binopt/tonnage.py   hauling data: recycling share by year, size of the prize
          binopt/plan.py      the recommendation: where to add recycling first, vs. random
                                         │
                                         ▼
          binopt/figures.py, binopt/maps.py, notebooks/01_bin_optimizer.ipynb
```

## Ranking and the random baseline

Every demand point is credited to its **nearest** receptacle within 50 m, so nothing is counted twice. A receptacle's share = the weight credited to it ÷ total estimated demand. Shares don't overlap, so taking the top *k* by share gives the most reach possible with *k* new recycling bins. The random baseline is the expected reach of *k* receptacles picked uniformly at random: *k* ÷ *n* × the total share served (linearity of expectation).

## Size of the prize

Keep a year's total tonnage the same and ask how many tons a month would have to go into recycling instead of trash to reach a target share: tons = target × (trash + recycling) − recycling. For 2021 and 2018's 46% share this is about 18 tons a month. SB 54's 65% is shown as a reference point only.

## Model inputs

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

After these, `demand.csv` has four **extra columns** that show how each weight was made: `osm_id` (the OpenStreetMap feature, e.g. `way/557192610`), `area_m2`, `levels`, `factor`. The model can ignore them. (Rule for any of these files: extra columns may be added at the end; the contract columns never change name or order.)

How `weight` is estimated (all factors in `binopt/config.py`, all `PLACEHOLDER`):
- Buildings: footprint area (m²) × number of floors (1 if unknown) × use-type factor (dining/food high, classrooms/library medium, offices low). The use type comes from OpenStreetMap tags, then from keywords in the name; any other named building counts as `academic`, unnamed ones as `unknown`. Shade canopies and covered bridges are left out.
- Parking lots: area × a low factor.
- Food and drink spots (cafes, restaurants, vending machines): a fixed extra weight, because eating and drinking is where single-use plastic shows up.

`lat`/`lon` is a point **inside** the building or lot (not always the exact center: for an L-shaped building the center can fall outside it).

### 2. `data/candidates.csv`: where a bin station could go

One row per **candidate site**: a spot along a walkway or just outside a building entrance. Never inside a building. Candidate sites are used by the coverage model's "what if we moved bins" scenarios.

| column | type | units | meaning |
|---|---|---|---|
| `site_id` | text | | Unique ID, e.g. `S0001`. |
| `lat`, `lon` | number | degrees | Where the site is. |
| `kind` | text | | `walkway` (a pin every 25 m along a walkway), `near_building` (the walkway spot closest to a building), or `entrance` (closest walkway spot to a door mapped in OpenStreetMap; only 1 door is mapped on campus, so `near_building` stands in for "near the entrance"). |
| `near` | text | | Name of the nearest building (helps Facilities find it). |
| `accessible` | text | | `unknown`, `yes` or `no`. Starts as `unknown` for every site: OpenStreetMap doesn't reliably record wheelchair routes, curb cuts or surfaces, so Facilities must confirm. The model may ignore this column for now. |

### 3. `data/distances.csv`: how far each demand point is from each site

One row per (demand point, site) pair that are **200 m or closer** (`MAX_DISTANCE_M`). Pairs farther apart are left out; treat a missing pair as "too far to cover".

| column | type | units | meaning |
|---|---|---|---|
| `demand_id` | text | | Matches `demand.csv`. |
| `site_id` | text | | Matches `candidates.csv`. |
| `distance_m` | number | meters | **Straight-line** distance. Real walking distance is longer, so real coverage may be a bit lower. |

**Measured to the edge.** For a building or parking lot, the distance is to its nearest **edge** (wall or lot edge), not its center, because people leave a building through doors on its edge. Otherwise no outdoor bin could ever be "within 50 m" of the middle of the library. Food and drink spots are points, so it's the distance to the point. (`DISTANCE_FROM` in `binopt/config.py` switches this to center distances.)

**"Covered" means:** `distance_m <= radius`. The radius comes from `binopt/config.py`:
```python
from binopt.config import DEFAULT_RADIUS_M, COVERAGE_RADII_M
# DEFAULT_RADIUS_M = 50            PLACEHOLDER
# COVERAGE_RADII_M = [30, 50, 75]  PLACEHOLDER, for the sensitivity check
```

## Limits we state openly

- Demand weights are estimates from building size and use until the pilot measures real numbers.
- Distances are straight lines, so real walking coverage may be a little lower.
- Receptacle positions come from a drawn map and are accurate to about 10 to 20 m.
- The 2021 map shows outdoor receptacles only; indoor bins are not modeled.
