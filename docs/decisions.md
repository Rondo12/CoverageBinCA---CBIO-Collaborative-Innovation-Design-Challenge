# Decisions log

A short record of each choice and the reason for it, so we can explain it to judges and to each other.
Newest at the bottom.

| Date | Decision | Why |
|---|---|---|
| 2026-09-28 | We report projected **coverage**, never measured diversion. | We have no bin-weight or audit data. Coverage (the share of estimated waste-generating foot traffic that has a bin within reach) is what the model can actually claim. |
| 2026-09-28 | Every estimated number is labeled `PLACEHOLDER`. | So judges and Facilities can tell measured values from assumptions. |
| 2026-09-28 | Python 3.12 locally. | Google Colab runs 3.12, so "works on my laptop" means "works in Colab". |
| 2026-09-28 | The model places one **co-located station** (trash + recycling + compost) per site. | Keeps a first model simple and matches how current bins will be counted (1 station = 1 unit). |
| 2026-09-28 | Campus data ships a precomputed `distances.csv` (demand point to candidate site, meters). | Ronnie's model only has to choose sites; no geometry code in the model notebook. |
| 2026-09-28 | Distances are straight-line, not walking routes. | Simple and reproducible. Walking distance is longer, so real coverage may be lower; we state this limitation. |
| 2026-09-28 | OpenStreetMap data is saved as snapshots in `data/osm/`. | Notebooks never depend on the Overpass API being up, and results are reproducible. |
| 2026-09-28 | Anything from Facilities goes in `data/private/` (gitignored). | The repo is public. We share Facilities data only once they say it's OK. |
| 2026-09-28 | `outputs/chosen_sites.csv` and `outputs/map.html` are tracked in git; the rest of `outputs/` is ignored. | The map reads the model's output, so it has to reach GitHub, and we want to share the map. |
| 2026-09-28 | One owner per file. | Avoids merge conflicts for a first-time GitHub team. Ronnie owns `notebooks/02_model.ipynb`; Eric owns the data, maps and `01_campus_data.ipynb`. |
