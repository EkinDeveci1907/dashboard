# Re-run only the rows a scan left blank.
#
# scan.py writes a row for every site whether or not it answered, which is the
# right call: a site that refuses a handshake is a finding, not a gap. But it
# means an interrupted scan - the laptop slept, the wifi dropped, the coffee shop
# captive portal came back - still produces a full-length file, and the sites it
# never really reached look exactly like the handful that genuinely don't answer.
# This goes back over the blank rows, scans those and only those, and writes the
# answers into the same file. Rows that already have data are not touched.
#
# How to tell an interrupted scan from a normal one: a normal full scan leaves
# something like thirty blanks, scattered. If a run leaves hundreds, and they all
# sit after one point in the file, the machine stopped talking to the network
# partway through and this is the tool for it.
#
# usage: python3 rescan.py [data/scan-YYYY-MM-DD.csv]
#        no argument = the newest data/scan-*.csv
#
# afterwards, same as after any scan:
#        python3 enrich.py <the file>
#        python3 aggregate.py

import csv
import glob
import os
import sys

# scan.py lives next to this file, and importing it rather than copying the
# handshake means a repaired row is measured exactly like every other row.
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scan

COLUMNS = ["site", "sector", "country", "tls_version", "key_exchange", "cert", "cdn"]


def newest_scan():
    # the newest data/scan-<date>.csv, ignoring the enriched copies enrich.py makes
    candidates = []
    for path in sorted(glob.glob(os.path.join(HERE, "data", "scan-*.csv"))):
        if not path.endswith("-enriched.csv"):
            candidates.append(path)
    if not candidates:
        return ""
    return candidates[-1]


def write_out(path, rows):
    # write to a temp file and move it into place, so a crash halfway through
    # writing leaves the previous version intact rather than half a file.
    tmp = path + ".tmp"
    out = open(tmp, "w", newline="")
    writer = csv.DictWriter(out, fieldnames=COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    out.close()
    os.replace(tmp, path)


path = newest_scan()
if len(sys.argv) > 1:
    path = sys.argv[1]
if path == "" or not os.path.exists(path):
    print("no scan file to repair. usage: python3 rescan.py data/scan-YYYY-MM-DD.csv")
    sys.exit(1)

rows = list(csv.DictReader(open(path)))
todo = []
for i in range(len(rows)):
    if (rows[i].get("tls_version") or "").strip() == "":
        todo.append(i)

print(path + ": " + str(len(rows)) + " rows, " + str(len(todo)) + " of them blank")
if not todo:
    print("nothing to redo.")
    sys.exit(0)

recovered = 0
count = 0
for i in todo:
    count = count + 1
    row = rows[i]
    site = (row.get("site") or "").strip()

    tls, kex, cert = scan.get_tls(site)
    if tls == "" or kex == "" or cert == "":
        # genuinely no answer this time either. leave the row blank, which is
        # what it already said, and move on.
        print(str(count) + "/" + str(len(todo)) + "  " + site + "  still no answer")
        continue

    cdn = scan.detect_cdn(site, scan.get_ip(site))
    row["tls_version"] = tls
    row["key_exchange"] = kex
    row["cert"] = cert
    row["cdn"] = cdn
    recovered = recovered + 1
    print(str(count) + "/" + str(len(todo)) + "  " + site + "  " + tls + "  " + cdn)

    # save after every recovered row. the whole point of this tool is that the
    # last run got interrupted, so assume this one can be too.
    write_out(path, rows)

write_out(path, rows)
still_blank = len(todo) - recovered
print("")
print("recovered " + str(recovered) + " of " + str(len(todo)) + ", " + str(still_blank) + " still not answering")
print("now run:  python3 enrich.py " + path)
print("    then: python3 aggregate.py")
