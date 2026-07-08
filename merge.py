# Small helper to stitch two scan CSVs into one, e.g. an old full scan plus a
# small re-scan of just the sites I added that week. If a site turns up in both
# files the first one wins. Only the columns the dashboard needs are kept.

import csv
import sys
import datetime

COLUMNS = ["site", "sector", "country", "tls_version", "key_exchange", "cert", "cdn"]

# read the two input file names (and an optional output name) from the command line
old_file = sys.argv[1]
new_file = sys.argv[2]
if len(sys.argv) > 3:
    out_file = sys.argv[3]
else:
    out_file = "data/scan-" + datetime.date.today().isoformat() + ".csv"

# read every row from each file, then join them with the old file first
old_rows = list(csv.DictReader(open(old_file)))
new_rows = list(csv.DictReader(open(new_file)))
all_rows = old_rows + new_rows

# walk the rows and keep the first time we see each site; skip blanks and repeats
seen_sites = set()
kept_rows = []
for row in all_rows:
    site = (row.get("site") or "").strip()
    if site == "" or site in seen_sites:
        continue
    seen_sites.add(site)
    kept_rows.append(row)

# write the combined file, keeping only the columns we care about
out = open(out_file, "w", newline="")
writer = csv.DictWriter(out, fieldnames=COLUMNS, extrasaction="ignore")
writer.writeheader()
for row in kept_rows:
    tidy_row = {}
    for column in COLUMNS:
        tidy_row[column] = row.get(column) or ""
    writer.writerow(tidy_row)
out.close()

print("wrote " + out_file + " with " + str(len(kept_rows)) + " sites")
print("now run: python3 aggregate.py")
