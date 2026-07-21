# Adds the two derived columns to a scan, so the scan file itself carries them:
#   pqc_source      - for a site that does PQC, did it come from the CDN in front
#                     of it ("provider") or from the organization itself ("own")?
#                     "none" if the site has no PQC; blank if it never answered.
#   readiness_score - the 0-100 quantum-readiness score.
#
# Both are worked out from columns the scan already has (tls_version, key_exchange,
# cert, cdn), so this runs on ANY scan we've ever taken - no re-scanning needed.
# It imports the exact rules from cdn_attribution.py and readiness_score.py, so
# there's still only one definition of each and the numbers can't drift apart.
#
# usage: python3 enrich.py [data/scan-YYYY-MM-DD.csv]
#        no argument = enrich every data/scan-*.csv we have

import csv
import sys
import glob

from cdn_attribution import attribution_for
from readiness_score import score_site, stars_for

# turn the attribution label into the short value that goes in the column
SOURCE = {
    "PQC via provider": "provider",
    "PQC own effort": "own",
    "No PQC": "none",
    "unreachable": "",
}


def enrich_one(scan_path):
    rows = list(csv.DictReader(open(scan_path)))
    columns = ["site", "sector", "country", "tls_version", "key_exchange",
               "cert", "cdn", "pqc_source", "readiness_score", "stars"]

    out_path = scan_path.replace(".csv", "-enriched.csv")
    out = open(out_path, "w", newline="")
    writer = csv.DictWriter(out, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()

    for row in rows:
        attribution = attribution_for(row)
        row["pqc_source"] = SOURCE.get(attribution, "")
        # a site that never answered gets blank columns, not a fake score of 0
        if attribution == "unreachable":
            row["readiness_score"] = ""
            row["stars"] = ""
        else:
            score, band, tls, kex, sig = score_site(row)
            row["readiness_score"] = score
            row["stars"] = stars_for(tls, kex, sig)
        writer.writerow(row)

    out.close()
    print("wrote " + out_path + " (" + str(len(rows)) + " rows)")


# enrich one scan if named, otherwise every scan we have (skip already-enriched)
if len(sys.argv) > 1:
    targets = [sys.argv[1]]
else:
    targets = []
    for path in sorted(glob.glob("data/scan-*.csv")):
        if "-enriched" not in path:
            targets.append(path)

for path in targets:
    enrich_one(path)
