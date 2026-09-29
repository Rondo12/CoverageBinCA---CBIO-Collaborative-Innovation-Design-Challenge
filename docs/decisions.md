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
| 2026-09-28 | Campus boundary = OSM university outline (way/44175866) minus farm land (farmland, orchard, vineyard, meadow, farmyard, greenhouse, nursery, animal keeping). Farm roads under 40 m wide are then removed (`STRIP_WIDTH_M` = 20, PLACEHOLDER), and only the main piece is kept. Result: 1.84 km². Approved by Eric on the map. | The OSM university outline includes the farm, and our scope is the main campus. The strip removal stops farm roads from counting as campus. |
| 2026-09-28 | The 2 parking lots just outside the university outline (north-west of the fields; south across Shaw Ave) stay OUT. | Not confirmed as Fresno State lots. |
| 2026-09-28 | The 7 unnamed buildings on the north edge that were cut out with the farm stay OUT. | They sit on farm land (likely farm-unit buildings). |
| 2026-09-28 | The farmyard enclosed by campus south of Barstow, west of Chestnut (`way/1216348399`, `landuse=farmyard`, no name in OSM, ~61,000 m²) stays OUT for now. Eric will check it on campus. The small enclosed vineyard at Barstow (`way/1216348392`, ~7,200 m²) is also out. | Unsure what they are on the ground. Either can be added back by putting its id in `ADD_BACK` in `binopt/config.py`. |
| 2026-09-28 | `ADD_BACK` list in `binopt/config.py` (empty) for farm-tagged areas that should count as campus. | Makes boundary corrections a one-line, documented change. |
| 2026-09-28 | Coverage radii 30 / 50 / 75 m (default 50), p = 20 stations, distances kept up to 200 m. All PLACEHOLDER, in `binopt/config.py`. | Assumptions until Facilities gives a station budget. Three radii let the model show how sensitive the answer is. |
| 2026-09-28 | A demand point covered by two chosen sites is credited only to the nearest one. | Per-site coverage then adds up to the total, with no double counting. |
| 2026-09-28 | Example dataset in `data/example/` (8 made-up points, 5 sites) with hand-worked answers for p = 2. | Ronnie can build and check his model before touching real data. |
| 2026-09-28 | From Colab, `chosen_sites.csv` reaches GitHub by download, then upload on github.com. | Colab's "Save a copy in GitHub" saves only the notebook, not files it writes. |
