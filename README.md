# CoverageBinCA---CBIO-Collaborative-Innovation-Design-Challenge

**Where should Fresno State put its bins?** A data-driven pilot for the BEAM Circular / CBIO Collaborative "Return to Earth" challenge, focused on single-use plastic packaging and food ware under California SB 54.

We estimate where waste-generating foot traffic happens on the main campus (buildings, dining, cafes, vending, parking), list the spots where a bin station could go (along walkways and near entrances, never inside buildings), and use an optimization model (a Maximal Covering Location Problem, built with PuLP) to choose the stations that cover the most of it. Places where people eat and drink get extra weight.

**What we claim, and what we don't.** Results are projected **coverage**: the share of *estimated* demand within reach of a bin station. We do not measure diversion. Every estimated number is labeled `PLACEHOLDER`, and every choice is logged with its reason in [`docs/decisions.md`](docs/decisions.md).

| Notebook | What it does | Owner | Open |
|---|---|---|---|
| `notebooks/02_model.ipynb` | Chooses bin station sites (PuLP model) | Ronnie | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Rondo12/CoverageBinCA---CBIO-Collaborative-Innovation-Design-Challenge/blob/main/notebooks/02_model.ipynb) |

Start with [`docs/data-contract.md`](docs/data-contract.md): it lists every file the notebooks share, its columns and units, and a small example dataset with known answers.

## What's in the repo

| Folder | Contents |
|---|---|
| `binopt/` | Python code for campus data and maps. All tunable assumptions are in `binopt/config.py`. |
| `data/osm/` | Saved OpenStreetMap snapshots and the campus boundary (main campus, farm land excluded). |
| `data/example/` | Tiny made-up dataset for testing the model. |
| `data/private/` | Files from Facilities. **Never uploaded** (see below). |
| `notebooks/` | Colab notebooks. |
| `outputs/` | Results. Only `chosen_sites.csv` and `map.html` are saved to GitHub. |
| `docs/` | Data contract and decisions log. |
| `scripts/` | One-time scripts (refresh the OpenStreetMap snapshots, rebuild the example data). |
| `tests/` | Automated checks (`pytest`). |

## How we work

New to GitHub? This is everything you need.

**One owner per file.** Each file has one person who edits it. Ronnie owns `notebooks/02_model.ipynb`. Eric owns the campus data, maps, `binopt/` and the other notebooks. If you want a change in someone else's file, ask them (or leave a comment on a pull request). This keeps us from overwriting each other's work.

**Open a notebook in Colab.** Click the **Open in Colab** badge in the table above. Colab opens a copy of the notebook from GitHub. Run the first cell (**Setup**): it downloads the project and installs the libraries. Then run the cells top to bottom (Shift + Enter runs one cell).

**Save your changes back to GitHub from Colab.**
1. In Colab: **File > Save a copy in GitHub**.
2. Pick this repository, and pick a **branch**. Don't save straight to `main`; type a new branch name like `ronnie/model` so the change can be reviewed first.
3. Write a short commit message (what you changed) and click OK.
4. Colab saves the notebook only. Files the notebook writes (like `outputs/chosen_sites.csv`) must be downloaded and then uploaded on github.com: open the folder on GitHub, then **Add file > Upload files**, and choose the same branch.

**Review and merge a pull request on github.com.** A pull request (PR) asks "please add the changes on my branch to `main`".
1. Open the repo on github.com and click the **Pull requests** tab, then the PR.
2. **Files changed** tab: read what changed. Click the **+** next to a line to leave a comment.
3. Click **Review changes**, then pick **Approve** or **Request changes**, and submit.
4. When it's approved, click **Merge pull request** (choose **Create a merge commit**), then **Confirm merge**.
5. Don't delete the branch if the author says they're still working on it.

## Data privacy

This repository is **public**. Anything Facilities sends (bin locations, maps, spreadsheets) goes in `data/private/`, which is listed in `.gitignore` so git never uploads it. It stays there until Facilities says sharing is OK. Never commit personal emails or phone numbers. Before every commit, run `git status` and check that nothing from `data/private/` is listed.

## Credits

Map data © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, available under the [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/). The snapshots in `data/osm/` were fetched on 2026-09-28. Anything derived from them (the campus boundary, and later the demand and candidate files) is shared under the same license.
