# Builds a small standalone page just for the most-visited-by-Canadians list:
# how post-quantum-ready the sites Canadians actually connect to are. It reads
# the enriched toplist scan (the one with pqc_source and readiness_score) and
# bakes the numbers straight into canada-topvisited.html, so you open it by just
# double-clicking - no server, nothing else to run.
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

from cdn_attribution import provider_pqc_rates
from readiness_score import stars_site

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

# keep the sites that actually answered
sites = []
for row in csv.DictReader(open(in_file)):
    if row["tls_version"].strip() != "":
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

pqc_pct = round(100 * pqc / total)

# how many sites were on the list to begin with, so the page can say "91 of 93
# answered" instead of quietly reporting only the ones that did
listed = len(list(csv.DictReader(open("data/sites-ca-toplist.csv"))))

# The provider PQC rates the report card quotes come from the main scan, not
# from this list - 91 sites is far too few to say what Akamai is doing. Same
# numbers the main dashboard uses.
main_scans = []
for path in sorted(glob.glob("data/scan-*.csv")):
    if "-enriched" not in path:
        main_scans.append(path)
cdn_rates = provider_pqc_rates(list(csv.DictReader(open(main_scans[-1]))))


def by_score(row):
    if row["score"] == "":
        return 0
    return int(row["score"])


# the rows for the table, best score first. Same columns as the main dashboard
# table, so the two tabs line up. Stars are worked out fresh from the scan
# columns with the same rule the main page uses.
table = []
for r in sites:
    table.append({"site": r["site"], "sector": r["sector"], "country": r["country"],
                  "tls": r["tls_version"], "kex": r["key_exchange"], "cdn": r["cdn"],
                  "source": r["pqc_source"], "score": r["readiness_score"],
                  "stars": stars_site(r)})
table.sort(key=by_score, reverse=True)

# Build the page. It reuses the dashboard's style.css and report-card.js, so it
# matches the main tab without any of that code being written out twice.
cards = ""
cards += "<div class='box'><div class='num'>" + str(total) + " / " + str(listed) + "</div><div class='label'>sites answered, of the list</div></div>"
cards += "<div class='box'><div class='num'>" + str(tls13) + "</div><div class='label'>on TLS 1.3</div></div>"
cards += "<div class='box'><div class='num'>" + str(pqc_pct) + "%</div><div class='label'>quantum-safe (PQC key exchange)</div></div>"
cards += "<div class='box'><div class='num'>" + str(via) + " / " + str(own) + "</div><div class='label'>PQC via CDN / own effort</div></div>"

headline = ("<strong>" + str(pqc_pct) + "%</strong> of the " + str(total) +
            " sites Canadians visit most that answered our handshake negotiate post-quantum "
            "key exchange (X25519MLKEM768).")

html = "<!DOCTYPE html>\n<html lang='en'>\n<head>\n<meta charset='UTF-8'>\n"
html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>\n"
html += "<title>PQC Monitor - Most visited by Canadians</title>\n"
html += "<link rel='stylesheet' href='style.css'>\n</head>\n<body>\n"
html += "<div class='page'>\n"
html += "<header class='header'><div><h1>PQC Deployment Monitor</h1>"
html += "<p class='tagline'>Post-quantum readiness of Canadian websites</p></div></header>\n"
html += "<nav class='nav'>"
html += "<a href='index.html'>Canada &amp; the world</a>"
html += "<a href='canada-topvisited.html' class='active'>Most visited by Canadians</a></nav>\n"
html += "<p class='headline'>" + headline + "</p>\n"
html += "<h2 class='section-head'>Most visited by Canadians <span class='tag tag-ca'>this list</span></h2>\n"
html += "<p class='scope'>The sites Canadians actually connect to most, from Semrush's Most Visited Websites in Canada ranking (adult and pirate-stream sites excluded). "
html += str(listed) + " sites on the list, " + str(total) + " answered a TLS handshake when we scanned on " + scan_date + ".</p>\n"
html += "<section class='summary'>" + cards + "</section>\n"
html += "<section class='card'>\n<h2>Site directory</h2>\n"
html += "<p class='hint'>Every site in the list, most quantum-ready first. Sites showing the post-quantum group are highlighted. "
html += "Stars work like on the main page: one per migration step done, best today is <span class='stars'>★★</span>. Hover the stars for the breakdown, and click any row for that site's full report card.</p>\n"
html += "<div id='siteDetail' class='site-detail' style='display:none'></div>\n"
html += "<div class='filters'><input id='search' placeholder='Search a site, e.g. netflix.com' oninput='draw()'></div>\n"
html += "<div class='table-scroll'><table><thead><tr>"
html += "<th>Site</th><th>Sector</th><th>Country</th><th>TLS</th><th>Key exchange</th><th>CDN</th><th>PQC from</th><th>Readiness</th>"
html += "</tr></thead><tbody id='rows'></tbody></table></div>\n</section>\n"
html += "<section class='card'><h2>About this view</h2>\n"
html += "<p>This page answers a simple question: of the websites Canadians actually visit most, how many already protect the connection against a future quantum computer? It is the same scan as the main monitor, run over a most-visited-by-Canadians list instead of the Canadian-institutions list. Most sites that pass do so because of their CDN, not their own servers - the <strong>PQC from</strong> column shows which.</p>\n"
html += "<p>The list itself is <a href='https://www.semrush.com/trending-websites/ca/all'>Semrush's "
html += "Most Visited Websites in Canada</a> ranking, in rank order, with the adult and "
html += "pirate-stream sites dropped. Nothing hand-picked, so the sample means the same thing "
html += "every month.</p>\n"
html += "</section>\n</div>\n"
# report-card.js has to be loaded before the inline script below runs, so it goes
# here at the end of the body rather than in the head with a defer.
html += "<script src='report-card.js'></script>\n"
html += "<script>\nconst DATA = " + json.dumps(table) + ";\n"
html += "const SCAN_DATE = " + json.dumps(scan_date) + ";\n"
html += "const CDN_RATES = " + json.dumps(cdn_rates) + ";\n"
html += """
// report-card.js holds starCell(), showSite() and the rest - the same code the
// main dashboard uses. All this page has to do is hand it the rows and draw
// the table.
setReportCard(DATA, SCAN_DATE, CDN_RATES);

function draw() {
  var q = document.getElementById('search').value.toLowerCase();
  var out = '';
  for (var i = 0; i < DATA.length; i++) {
    var r = DATA[i];
    if (q && r.site.toLowerCase().indexOf(q) === -1) continue;
    var kex = r.kex.indexOf('MLKEM') !== -1 ? "<span class='kex-pqc'>" + r.kex + "</span>" : r.kex;
    var src = r.source ? r.source : 'none';
    out += "<tr onclick='showSite(" + i + ")'><td>" + r.site + "</td><td>" + r.sector + "</td><td>" + r.country +
           "</td><td>" + r.tls + "</td><td>" + kex + "</td><td>" + r.cdn +
           "</td><td><span class='pill pill-" + src + "'>" + src + "</span></td><td>" + starCell(r) + "</td></tr>";
  }
  document.getElementById('rows').innerHTML = out;
}
draw();
</script>
</body>
</html>"""
open("canada-topvisited.html", "w").write(html)
print("wrote canada-topvisited.html")
print("  " + str(total) + " sites, " + str(tls13) + " on TLS 1.3, " + str(pqc_pct) + "% quantum-safe")
