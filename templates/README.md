# Templates for your own campus

Fill these in to run the model on your campus (see "Run it for your campus" in the main README).

- **`bins_template.csv`**: one row per outdoor bin or bin station.
  - `bin_id`: any label you use (optional; rows are numbered if it's missing)
  - `lat`, `lon`: the location in decimal degrees, as Google Maps or Apple Maps shows it (right-click a spot to copy it)
  - `units`: how many containers sit together at that spot (optional, default 1)
  - Column names are flexible: "Latitude", "GPS Lat" or one "lat, lon" column also work.
- **`tonnage_template.csv`**: one row per month from your hauler's report.
  - `year`, `month` (1 to 12), `trash_tons`, `recycling_tons`, and optionally `green_tons`.

The example rows are made up. Replace them with yours.
