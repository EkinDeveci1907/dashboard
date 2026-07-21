# Builds a small standalone page just for the most-visited-by-Canadians list:
# how post-quantum-ready the sites Canadians actually connect to are. It reads
# the enriched toplist scan (the one with pqc_source and readiness_score) and
# bakes the numbers straight into canada-topvisited.html, so you open it by just
# double-clicking - no server, nothing else to run.
#
# usage: python3 toplist_report.py [data/toplist-YYYY-MM-DD-enriched.csv]
#        no argument = the newest toplist-*-enriched.csv in data/

import csv
import sys
import glob
import json
import os

from readiness_score import stars_site

if len(sys.argv) > 1:
    in_file = sys.argv[1]
else:
    in_file = sorted(glob.glob("data/toplist-*-enriched.csv"))[-1]

scan_date = os.path.basename(in_file).replace("toplist-", "").replace("-enriched.csv", "")

# keep the sites that actually answered
sites = []
for row in csv.DictReader(open(in_file)):
    if row["tls_version"].strip() != "":
        sites.append(row)

# the headline counts
total = len(sites)
pqc = 0
via = 0
own = 0
score_sum = 0
for r in sites:
    if "MLKEM" in r["key_exchange"].upper():
        pqc = pqc + 1
    if r["pqc_source"] == "provider":
        via = via + 1
    if r["pqc_source"] == "own":
        own = own + 1
    if r["readiness_score"] != "":
        score_sum = score_sum + int(r["readiness_score"])

pqc_pct = round(100 * pqc / total)
avg_score = round(score_sum / total)


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

# ---- build the page (reuses the dashboard's style.css so it matches exactly) ----
cards = ""
cards += "<div class='box'><div class='num'>" + str(total) + "</div><div class='label'>sites Canadians visit most</div></div>"
cards += "<div class='box'><div class='num'>" + str(pqc_pct) + "%</div><div class='label'>quantum-safe (PQC key exchange)</div></div>"
cards += "<div class='box'><div class='num'>" + str(avg_score) + "</div><div class='label'>avg readiness score / 100</div></div>"
cards += "<div class='box'><div class='num'>" + str(via) + " / " + str(own) + "</div><div class='label'>PQC via CDN / own effort</div></div>"

headline = ("<strong>" + str(pqc_pct) + "%</strong> of the " + str(total) +
            " sites Canadians visit most negotiate post-quantum key exchange (X25519MLKEM768).")

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
html += "<p class='scope'>The sites Canadians actually connect to most, from Similarweb's published Top Websites in Canada ranking (adult sites excluded). Scanned " + scan_date + ".</p>\n"
html += "<section class='summary'>" + cards + "</section>\n"
html += "<section class='card'>\n<h2>Site directory</h2>\n"
html += "<p class='hint'>Every site in the list, most quantum-ready first. Sites showing the post-quantum group are highlighted.</p>\n"
html += "<p class='hint'>Readiness is one star per migration step done: <span class='stars'>&#9733;</span> TLS 1.3"
html += " &nbsp;&middot;&nbsp; <span class='stars'>&#9733;&#9733;</span> + post-quantum key exchange"
html += " &nbsp;&middot;&nbsp; <span class='stars'>&#9733;&#9733;&#9733;</span> + post-quantum certificate signature"
html += " (no public CA issues these yet, so today's best is two). Hover the stars for the breakdown.</p>\n"
html += "<div class='filters'><input id='search' placeholder='Search a site, e.g. netflix.com' oninput='draw()'></div>\n"
html += "<div class='table-scroll'><table><thead><tr>"
html += "<th>Site</th><th>Sector</th><th>Country</th><th>TLS</th><th>Key exchange</th><th>CDN</th><th>PQC from</th><th>Readiness</th>"
html += "</tr></thead><tbody id='rows'></tbody></table></div>\n</section>\n"
html += "<section class='card'><h2>About this view</h2>\n"
html += "<p>This page answers a simple question: of the websites Canadians actually visit most, how many already protect the connection against a future quantum computer? It is the same scan as the main monitor, run over a most-visited-by-Canadians list instead of the Canadian-institutions list. Most sites that pass do so because of their CDN, not their own servers - the <strong>PQC from</strong> column shows which.</p>\n"
html += "<p><strong>Where the list comes from:</strong> the site list follows Similarweb's published "
html += "<a href='https://www.similarweb.com/top-websites/canada/'>Top Websites in Canada</a> ranking, "
html += "which orders sites by Canadian traffic and is refreshed monthly. Adult sites are excluded "
html += "(they sit in the ranking but aren't relevant to a readiness report); everything else is kept "
html += "as ranked, so the sample is a published, repeatable definition of &quot;most visited by "
html += "Canadians&quot; rather than a hand-picked list. <code>data/sites-ca-toplist.csv</code> is that "
html += "list in scan order.</p>\n"
# the sourced list arrived Jul 20; a scan older than that is still the previous
# hand-picked list, so say so rather than let the page quietly mislabel it
if scan_date < "2026-07-20":
    html += "<p class='hint'>This table still shows the " + scan_date + " scan of the previous, "
    html += "hand-picked list. The first scan of the sourced Similarweb list replaces it on the "
    html += "next scan day.</p>\n"
html += "</section>\n</div>\n"
html += "<script>\nconst DATA = " + json.dumps(table) + ";\n"
html += """
// same star cell as the main dashboard: filled stars for the steps done,
// pale ones for the rest, and the breakdown on hover
function starCell(r) {
  var stars = r.stars || 0;
  var shown = '';
  for (var i = 0; i < 3; i++) {
    shown += i < stars ? "\\u2605" : "<span class='star-off'>\\u2605</span>";
  }
  var parts = [];
  parts.push((r.tls.indexOf('1.3') !== -1 ? '\\u2713' : '\\u2717') + ' TLS 1.3');
  parts.push((r.kex.indexOf('MLKEM') !== -1 ? '\\u2713' : '\\u2717') + ' PQC key exchange');
  parts.push((stars === 3 ? '\\u2713' : '\\u2717') + ' PQC signature');
  var title = parts.join('  \\u00b7  ') + '  (score ' + r.score + '/100)';
  return "<span class='stars' title='" + title + "'>" + shown + "</span>";
}

function draw() {
  var q = document.getElementById('search').value.toLowerCase();
  var out = '';
  for (var i = 0; i < DATA.length; i++) {
    var r = DATA[i];
    if (q && r.site.toLowerCase().indexOf(q) === -1) continue;
    var kex = r.kex.indexOf('MLKEM') !== -1 ? "<span class='kex-pqc'>" + r.kex + "</span>" : r.kex;
    var src = r.source ? r.source : 'none';
    out += "<tr><td>" + r.site + "</td><td>" + r.sector + "</td><td>" + r.country +
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
print("  " + str(total) + " sites, " + str(pqc_pct) + "% quantum-safe, avg score " + str(avg_score))
