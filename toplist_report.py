# Builds a small standalone page just for the most-visited-by-Canadians list:
# how post-quantum-ready the sites Canadians actually connect to are. It reads
# the enriched toplist scan (the one with pqc_source and readiness_score) and
# bakes the numbers straight into canada-topvisited.html, so you open it by just
# double-clicking. no server, nothing else to run.
#
# The page shares style.css and report-card.js with the main dashboard, so the
# table and the click-through report card look and behave the same on both tabs.
#
# usage: python3 toplist_report.py [data/toplist-YYYY-MM-DD-enriched.csv]
#        no argument = the newest toplist-*-enriched.csv in data/

import csv
import sys
import glob
import json
import os

if len(sys.argv) > 1:
    in_file = sys.argv[1]
else:
    toplist_scans = sorted(glob.glob("data/toplist-*-enriched.csv"))
    if not toplist_scans:
        print("No data/toplist-*-enriched.csv found.")
        print("Scan the list first:  python3 scan.py data/sites-ca-toplist.csv data/toplist-<date>.csv")
        print("then:                 python3 enrich.py data/toplist-<date>.csv")
        sys.exit(1)
    in_file = toplist_scans[-1]

scan_date = os.path.basename(in_file).replace("toplist-", "").replace("-enriched.csv", "")

# bump this when style.css or report-card.js changes, and bump the matching one
# in index.html too. Pages tells browsers to hold on to js and css, so without it
# a returning visitor runs last week's script against this week's page.
ASSETS = "2026-08-05-3"

# keep the sites that actually answered. same test aggregate.py uses, so this
# tab and the main one agree on what counts as a scanned site
sites = []
for row in csv.DictReader(open(in_file)):
    if (row["tls_version"].strip() and row["key_exchange"].strip()
            and row["cert"].strip() and row["cdn"].strip()):
        sites.append(row)

# the headline counts
total = len(sites)
tls13 = 0
pqc = 0
via = 0
own = 0
for r in sites:
    if "1.3" in r["tls_version"]:
        tls13 = tls13 + 1
    if "MLKEM" in r["key_exchange"].upper():
        pqc = pqc + 1
    if r["pqc_source"] == "provider":
        via = via + 1
    if r["pqc_source"] == "own":
        own = own + 1

if total == 0:
    print("nothing in " + in_file + " answered, so there is no page to build")
    sys.exit(1)

pqc_pct = round(100 * pqc / total)

# how many sites were on the list to begin with, so the line under the heading
# can say how many we asked, otherwise the ones that never replied vanish
listed = len(list(csv.DictReader(open("data/sites-ca-toplist.csv"))))

def by_score(row):
    return row["score"]


# the rows for the table, best score first. Same columns as the main dashboard
# table so the two tabs line up. The score and stars come straight out of the
# enriched csv, where enrich.py already worked them out. no reason to redo it here.
# Both have to be numbers, not the strings csv hands back, or the star cell's
# stars === 3 test never fires.
# cert is not in the table itself, but the report card prints it on the signature
# line, and leaving it out is why that line used to read "undefined".
table = []
for r in sites:
    table.append({"site": r["site"], "sector": r["sector"], "country": r["country"],
                  "tls": r["tls_version"], "kex": r["key_exchange"], "cert": r["cert"],
                  "cdn": r["cdn"], "source": r["pqc_source"],
                  "score": int(r["readiness_score"]), "stars": int(r["stars"])})
table.sort(key=by_score, reverse=True)

# the four number boxes across the top. the headline right above already gives the
# percentage and how many sites answered, so these give the four numbers behind it
# instead of repeating it
boxes = [
    (str(listed), "sites on the list"),
    (str(tls13), "on TLS 1.3"),
    (str(pqc), "PQC-enabled (hybrid post-quantum key exchange)"),
    (str(via) + " / " + str(own), "PQC endpoint: CDN edge / no CDN detected"),
]
cards = ""
for number, label in boxes:
    cards = cards + "<div class='box'><div class='num'>" + number + "</div>"
    cards = cards + "<div class='label'>" + label + "</div></div>"

headline = ("<strong>" + str(pqc_pct) + "%</strong> of the " + str(total) +
            " sites Canadians visit most negotiate post-quantum key exchange (X25519MLKEM768).")

# reuses the dashboard's style.css and report-card.js, so this tab matches the main 
# one without any of that code being written out twice. report-card.js has to load before
#  the script  at the bottom runs, which is why it sits down there and not up in the head.
PAGE = """<!DOCTYPE html>
<html lang='en'>
<head>
<meta charset='UTF-8'>
<meta name='viewport' content='width=device-width, initial-scale=1.0'>
<title>PQC Monitor - Most visited by Canadians</title>
<link rel='stylesheet' href='style.css?v=__ASSETS__'>
</head>
<body>
<div class='page'>
<header class='header'><div><h1>PQC Deployment Monitor</h1><p class='tagline'>Tracking post-quantum TLS deployment, with a focus on Canadian websites</p></div></header>
<nav class='nav'><a href='index.html'>Canada &amp; the world</a><a href='canada-topvisited.html' class='active'>Most visited by Canadians</a><a href='check.html'>Scan a site</a></nav>
<p class='headline'>__HEADLINE__</p>
<h2 class='section-head'>Most visited by Canadians <span class='tag tag-ca'>this list</span></h2>
<p class='scope'>The sites Canadians actually connect to most, from Semrush's Most Visited Websites in Canada ranking (adult and pirate-stream sites excluded). __LISTED__ sites on the list, __TOTAL__ answered a TLS handshake when the monitor scanned on __SCANDATE__.</p>
<section class='summary'>__CARDS__</section>
<section class='card'>
<h2>Measured domains</h2>
<p class='hint'>Every site in the list, highest readiness first. Sites showing the post-quantum group are highlighted. Stars work like on the main page: one per migration step done, best today is <span class='stars'>__STARS__</span>. Hover the stars for the breakdown, and click any row for that site's full report card.</p>
<div id='siteDetail' class='site-detail' style='display:none'></div>
<div class='filters'><input id='search' placeholder='Search a site, e.g. netflix.com' oninput='draw()'></div>
<div class='table-scroll'><table><thead><tr><th>Site</th><th>Sector</th><th>Country</th><th>TLS</th><th>Key exchange</th><th>CDN</th><th>PQC endpoint</th><th>Readiness</th></tr></thead><tbody id='rows'></tbody></table></div>
</section>
<section class='card'><h2>About this view</h2>
<p>This page answers a simple question: of the websites Canadians actually visit most, how many already protect the connection against a future quantum computer? It is the same scan as the main monitor, run over a most-visited-by-Canadians list instead of the Canadian-institutions list. Most sites that pass do so at their CDN's edge rather than on their own servers, and the <strong>PQC endpoint</strong> column shows which. That column says where the connection terminates, not who turned the post-quantum key exchange on, which a handshake cannot tell you.</p>
<p>The list itself is <a href='https://www.semrush.com/trending-websites/ca/all'>Semrush's Most Visited Websites in Canada</a> ranking, in rank order, with the adult and pirate-stream sites dropped. The selection rule is the published ranking rather than our own judgement, so the sample means the same thing every month.</p>
</section>
</div>
<script src='report-card.js?v=__ASSETS__'></script>
<script>
const DATA = __DATA__;
const SCAN_DATE = __SCANDATEJSON__;
// report-card.js holds starCell(), showSite() and the rest, the same code the
// main dashboard uses. All this page has to do is hand it the rows and draw
// the table.
setReportCard(DATA, SCAN_DATE);

function draw() {
  let q = document.getElementById('search').value.toLowerCase();
  let out = '';
  for (let i = 0; i < DATA.length; i++) {
    let r = DATA[i];
    if (q && r.site.toLowerCase().indexOf(q) === -1) continue;
    let kex = r.kex.indexOf('MLKEM') !== -1 ? "<span class='kex-pqc'>" + esc(r.kex) + "</span>" : esc(r.kex);
    let src = r.source ? r.source : 'none';   // sourceLabel() and esc() are in report-card.js
    out += "<tr onclick='showSite(" + i + ")'><td>" + esc(r.site) + "</td><td>" + esc(r.sector) + "</td><td>" + esc(r.country) +
           "</td><td>" + esc(r.tls) + "</td><td>" + kex + "</td><td>" + esc(r.cdn) +
           "</td><td><span class='pill pill-" + src + "'>" + sourceLabel(src) + "</span></td><td>" + starCell(r) + "</td></tr>";
  }
  document.getElementById('rows').innerHTML = out;
}
draw();
</script>
</body>
</html>"""

page = PAGE
page = page.replace("__ASSETS__", ASSETS)
page = page.replace("__HEADLINE__", headline)
page = page.replace("__LISTED__", str(listed))
page = page.replace("__TOTAL__", str(total))
page = page.replace("__SCANDATE__", scan_date)
page = page.replace("__CARDS__", cards)
page = page.replace("__STARS__", "★★")
# the rows go inside a <script> block, and a browser ends that block at the
# first </script> it sees no matter what the JSON thinks. json.dumps has no
# reason to escape a slash, so do it here.
page = page.replace("__DATA__", json.dumps(table).replace("</", "<\\/"))
page = page.replace("__SCANDATEJSON__", json.dumps(scan_date))

open("canada-topvisited.html", "w").write(page)
print("wrote canada-topvisited.html")
print("  " + str(total) + " sites, " + str(tls13) + " on TLS 1.3, " + str(pqc_pct) + "% PQC-enabled")
