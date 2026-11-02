# What's in the Bin? A Student-Run Plastic Pilot

**Fresno State · BEAM Circular / CBIO Collaborative Innovation Design Challenge, "Return to Earth" (Fall 2026)**
Eric Pineda Ramirez and Ronnie Pabelonio

Fresno State's recycling share fell from **46% in 2018 to 20% in 2021** (Mid Valley Disposal hauling data), and the hauler's photos show bagged trash inside recycling dumpsters. As far as we could find, nobody tracks which single-use plastic items end up in the wrong bin. We propose a one-semester, student-run pilot that measures exactly that, and gives Dining Services the data to swap the worst item.

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Rondo12/CoverageBinCA---CBIO-Collaborative-Innovation-Design-Challenge/blob/main/notebooks/01_bin_optimizer.ipynb)

**[Weekly log form (Google Form)](https://docs.google.com/forms/d/e/1FAIpQLSdniyxaJsIueUoeeq8BXDpIZOuk8H0s1ZG4AGfQ3AzdP8HmNQ/viewform?usp=dialog)**, built by [`scripts/create_weekly_log_form.gs`](scripts/create_weekly_log_form.gs)


## The pilot

One semester (Spring 2027), run by students at almost no cost to Facilities:
1. **A weekly plastic count.** A 5-minute log per site (Google Form): fill levels, a photo, and **counts** of the visible single-use plastic items in the wrong bin (recyclable plastic in the trash, and bags or trash in the recycling). Answers land in a Google Sheet automatically.
2. **A baseline first.** For the first three weeks, nothing changes at any site; we just count.
3. **One change to test.** Then at two of the four sites, we pair trash and recycling side by side (adding a recycling bin where there isn't one), with clear "no bags in recycling" signs. The other two stay the same for comparison.
4. **The counts go to Dining Services,** so the item that shows up most can be swapped: reusable first, compostable only where food waste is already composted.
5. **Measured numbers replace the model's estimates** (Summer 2027). In Fall 2027, Facilities adds recycling and signs where the pilot shows it works.

**Goals (targets, not results), by the end of spring 2027:**
- Recyclable plastic in the trash cut in half at the test sites, compared with their first three weeks. The comparison sites show whether a change comes from the paired bins or just the time of semester.
- Dining commits to swapping one single-use item; by fall 2027, we count how many fewer of that item campus buys.
- Facilities makes one decision using the pilot's data.

**Who runs it:** Eric and Ronnie lead it, with student volunteers for the weekly logs. Before we graduate, we hand it to a named student group, with the form, the model and every decision documented here.

## Where it runs, and why

We picked three pilot sites because Mid Valley photographed bagged trash in their recycling dumpsters in 2018 and 2019 (Fresno State Library, McLane Hall, Science II), plus the University Dining Hall, where single-use food ware is handed out. Our model backs that choice up: it ranks all 88 outdoor receptacles on Facilities' 2021 map by the estimated foot traffic each one serves, and all four sites rank in the top 10 (#1, #4, #7, #10).

Supporting analysis (in the notebook):
- About 90% of estimated foot traffic in the academic core already has *a* receptacle within 50 m. On our walks across campus, though, most outdoor receptacles we saw were trash only.
- Recycling beside the 10 top-ranked trash cans would reach about 46% of estimated foot traffic, versus about 9% beside 10 trash cans picked at random.
- In 2021 Fresno State hauled about 55 tons of trash and 14 tons of recycling a month; about 18 tons a month moved from trash to recycling would get back to 2018's 46% share.

## How it works

1. **Today's receptacles.** Facilities' 2021 receptacle map is a drawing, so `binopt/digitize.py` finds each marker by color and pins the drawing to GPS using 7 street corners that also appear in OpenStreetMap (positions good to about 10 to 20 m).
2. **Estimated foot traffic.** Every building, food spot and parking lot gets a weight from OpenStreetMap: footprint × floors × a use factor (dining highest, classrooms medium, offices low). These weights are labeled `PLACEHOLDER` until the pilot measures real numbers.
3. **Ranking.** Each place's foot traffic is credited to its nearest receptacle within 50 m (no double counting), and receptacles are sorted by their share (`binopt/rank.py`). Because shares don't overlap, the top *k* is the best set of *k* spots for new recycling (assuming people use their nearest bin). The random baseline is the expected value of *k* trash cans picked at random.
4. **Coverage model.** A Maximal Covering Location Problem (Church and ReVelle, 1974) solved exactly with PuLP (`binopt/model.py`) checks how well today's layout reaches people and what moving bins would do. Its answer is why we add recycling instead of moving bins: moves pulled bins out of the busy core.
5. **Tonnage.** `binopt/tonnage.py` reads the hauling report and sizes the prize in tons.

Full method, assumptions and every decision with its reason: [`docs/methods.md`](docs/methods.md) and [`docs/decisions.md`](docs/decisions.md).

**What we claim, and what we don't.** Reach and coverage are **projected** from estimated foot traffic, not measured recycling. Tonnage numbers are real. The pilot exists to measure what each new bin actually captures.

## Run it for your campus

Any campus can run the same model for free, in Google Colab, with no coding:

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Rondo12/CoverageBinCA---CBIO-Collaborative-Innovation-Design-Challenge/blob/main/notebooks/02_any_campus.ipynb)

1. Click the badge and type your campus name, for example `University of the Pacific, Stockton, California`.
2. **Runtime > Run all.** In a few minutes the notebook finds the campus on OpenStreetMap, estimates where waste-generating foot traffic is, and shows the spots where a small number of bin stations would reach the most people.
3. **Optional:** upload a list of your bins (`templates/bins_template.csv`: one row per bin with its latitude and longitude) to rank your own bins by the foot traffic each one serves. Add your hauler's monthly tons (`templates/tonnage_template.csv`) to track your recycling share.

Tested on Fresno State and University of the Pacific. Distances use each campus's own map projection, so results hold anywhere. Foot traffic is an estimate from building size and use: treat results as a starting point for a pilot like ours, which measures the real thing.

On a laptop: `python -m binopt.anycampus "University of the Pacific, Stockton, California"` (add `--bins my_bins.csv` to rank your bins).

## Run it (Fresno State)

**In Google Colab:** click the badge above, then **Runtime > Run all**. The first cell downloads the code and installs it. The hauling report and the 2021 map came from Fresno State Facilities and are not public. Without them, the notebook still runs top to bottom: it runs the placement model on the public OpenStreetMap data and skips the steps built on Facilities' files. Team members with the files set `USE_PRIVATE_DATA = True` in the first cell, which reads them from a Google Drive folder named `CoverageBin private data`.

**On a laptop:**
```
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e . -r requirements-dev.txt
pytest                      # 38 checks, including hand-worked answers
python -m binopt.build      # rebuild the public campus data from OpenStreetMap
python -m binopt.plan       # ranking, random baseline, size of the prize (needs the private files)
python -m binopt.figures    # charts and the campus map (needs the private files)
```

## What's in the repo

| Path | Contents |
|---|---|
| `notebooks/01_bin_optimizer.ipynb` | The main notebook: diagnosis, today's layout, the model, the pilot |
| `notebooks/02_any_campus.ipynb` | Run the model on any campus: type its name, get a foot-traffic map and suggested bin spots |
| `templates/` | Fill-in templates for your own bin list and hauling data |
| `binopt/` | The Python package. All assumptions live in `binopt/config.py` |
| `data/` | Model inputs built from OpenStreetMap (`demand.csv`, `candidates.csv`, `distances.csv`) and a small example dataset with hand-worked answers |
| `outputs/scenarios.csv` | Coverage numbers for every scenario (no receptacle locations) |
| `tests/` | Automated checks (`pytest`) |
| `docs/` | Method and decisions log |
| `scripts/` | The pilot's weekly log Google Form (`create_weekly_log_form.gs`), refresh the OpenStreetMap snapshots, rebuild the example data |

## Data and privacy

The repository is public. Files from Fresno State Facilities (the hauling report, the 2021 receptacle map, and anything built from them, such as receptacle positions) stay in `data/private/`, which git ignores.

## Sources and credits

- Mid Valley Disposal tonnage report (Jan 2018 to Jun 2022), dumpster maps and site-visit photos, shared by Fresno State Facilities
- Fresno State Facilities, 2021 receptacle map
- Church, R. and ReVelle, C. (1974). The maximal covering location problem. *Papers of the Regional Science Association*, 32, 101 to 118
- Map data © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, [ODbL](https://opendatacommons.org/licenses/odbl/). Snapshots in `data/osm/` fetched on 2026-09-28 (street center lines on 2026-10-10); everything derived from them is shared under the same license.
