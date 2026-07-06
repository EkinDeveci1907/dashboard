import csv
import sys
import datetime

# Combine two scan files into one. We match columns by NAME, not by position,
# so the fields always line up even if a file's column order ever changes.
# We keep only the columns the dashboard reads, and drop duplicate sites.
COLS = ["site", "sector", "country", "tls_version", "key_exchange", "cert", "cdn"]

old_scan = sys.argv[1]
new_scan = sys.argv[2]
out_path = sys.argv[3] if len(sys.argv) > 3 else "data/scan-" + datetime.date.today().isoformat() + ".csv"

rows = list(csv.DictReader(open(old_scan))) + list(csv.DictReader(open(new_scan)))

# keep the first time we see each site, skip repeats
seen = set()
combined = []
for r in rows:
    site = (r.get("site") or "").strip()
    if site == "" or site in seen:
        continue
    seen.add(site)
    combined.append(r)

out = open(out_path, "w", newline="")
writer = csv.DictWriter(out, fieldnames=COLS, extrasaction="ignore")
writer.writeheader()
for r in combined:
    writer.writerow({c: (r.get(c) or "") for c in COLS})
out.close()

print("wrote " + out_path + " with " + str(len(combined)) + " sites")
print("now run: python3 aggregate.py")
