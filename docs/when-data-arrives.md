# When Facilities sends data: checklist

**Goal:** real data in, new map out, in under 30 minutes. Everything already runs on OpenStreetMap proxy data, so real data is a **file swap**, not new code.

**Before you start:** a laptop with the repo and its `.venv` (see the README), on the `eric/campus-data` branch, with a clean `git status`. All commands run from the repo folder.

---

## 1. Read what they sent (3 min)

Write down in one line what it is, e.g. "Bin inventory, Excel, 142 rows, lat/lon columns". Then sort it:

| They sent | Where it goes | Section |
|---|---|---|
| Current bin locations (spreadsheet, CSV, map file) | `data/private/current_bins.<ext>` | 2 |
| How many stations they can add or move (a budget) | `N_SITES` in `binopt/config.py` | 5 |
| Spots where bins are not allowed, or ADA notes | Don't code it yet: save it in `data/private/` and note it in `docs/decisions.md` | — |
| Foot-traffic counts, building occupancy | Don't code it yet: save it in `data/private/`. It can replace `PLACEHOLDER` weights later. | — |
| Only descriptions ("north door of the Library"), no coordinates | Place them by hand on a map first. This takes longer than 30 min. | — |

If the file has names, emails or phone numbers of staff, it still goes **only** in `data/private/`. Never paste it into a commit, an issue or a pull request.

## 2. Drop the file in (2 min)

1. Save it as `data/private/current_bins.csv` (or `.xlsx`, `.geojson`; an old `.xls` must be saved as `.xlsx` first). Renaming is easiest. To keep the original name instead, set `CURRENT_BINS_FILE = "data/private/<name>"` in `binopt/config.py`.
2. Check it is invisible to git:
   ```
   git status
   ```
   Nothing under `data/private/` may be listed. If it is, stop and fix `.gitignore` before anything else.

## 3. Run the one command (1 min)

```
.venv/bin/python -m binopt.build
```

This rebuilds the boundary, `data/demand.csv`, `data/candidates.csv` and `data/distances.csv`, and reads the current bins into `data/private/current_bins_clean.csv`.

## 4. Check the output (10 min)

Read section **4. Current bins** of the printout:

- [ ] **Row count.** "Read N rows" matches what Facilities said.
- [ ] **Location columns.** The `location:` line names the right columns. If it says "Couldn't find location columns", rename them to `lat` and `lon` in the file and run again.
- [ ] **"Coordinates are too big to be lat/lon".** The file uses a map projection. Ask Facilities which one, set `CURRENT_BINS_CRS` in `binopt/config.py` (California State Plane Zone 4, feet = `"EPSG:2228"`), and run again.
- [ ] **Units.** Our unit is one **co-located station** (trash + recycling + compost together). Look at the `not used:` list:
  - A `count` or `bins` column might count *containers*, not stations. The loader ignores it on purpose. If it really means stations, rename it to `units`.
  - A `type`/`stream` column (trash, recycling, ...) usually means **one row per container**. Then several rows at one spot are **one** station. Tell Claude/Eric before going further; this needs a grouping step, and we log the rule in `docs/decisions.md`.
- [ ] **Warnings.** "dropped N rows with no usable location" and "more than ~5 km from campus" list the bin IDs. Check them in the original file.
- [ ] **Baseline.** "Projected coverage of the CURRENT layout" gives today's coverage at 30/50/75 m. It is our before number. It uses the same PLACEHOLDER weights, so compare it only with the model's coverage, never present it as a measured value.

Sections 1–3 of the printout don't change when only bin locations arrive. If they do change, something else changed (config or snapshots): find out what before going on.

## 5. Rebuild the map (5 min)

> `binopt/maps.py` is built in step 5 of the plan. Until then, skip to 6.

```
.venv/bin/python -m binopt.maps
```

- [ ] Open the map in a browser. Current bins should sit on walkways or next to buildings. A bin in the middle of a building or a road usually means swapped or misread coordinates.
- [ ] **Privacy.** While current bins are private, the map that shows them is written to a file git ignores (not `outputs/map.html`). `outputs/map.html` is public and must not show them. Run `git status` and check.

## 6. Rerun the model (5 min)

The model reads `data/demand.csv`, `data/candidates.csv` and `data/distances.csv`. Current bins don't change those files, so the model's answer only changes if `N_SITES` or another setting changed.

- **Ronnie, in Colab:** push first (section 7) so Colab clones the new files. Open `02_model.ipynb` from the branch, set `DATA_DIR = "data"`, run all cells, then download `outputs/chosen_sites.csv` and upload it to the branch on github.com.
- **Eric, on the laptop**, once Ronnie's notebook has a working model and uses `DATA_DIR = "data"`. This runs it **without editing it**; the run copy goes to `outputs/`, which git ignores:
  ```
  .venv/bin/jupyter nbconvert --to notebook --execute notebooks/02_model.ipynb --output-dir outputs/
  ```
  Then rebuild the map again (section 5) so it shows the new `chosen_sites.csv`.

## 7. Save and log (4 min)

- [ ] Add one row to `docs/decisions.md`: the date, what arrived, what you changed (e.g. "N_SITES 20 → 12, Facilities budget").
- [ ] `git status`: only public files listed (`binopt/config.py`, `docs/decisions.md`, `data/*.csv`, `outputs/chosen_sites.csv`). **Nothing from `data/private/`.**
- [ ] Commit and push:
  ```
  git add binopt/config.py docs/decisions.md data/*.csv
  git commit -m "Facilities data: <what arrived>"
  git push
  ```
- [ ] Ask Facilities whether the current bin locations may be shared publicly. Until they say yes, they stay in `data/private/` and off the public map.
