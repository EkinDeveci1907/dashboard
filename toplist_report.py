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
cards += "<div class='box'><div class='num'>" + str(tls13) + "</div><div class='label'>on TLS 1.3</div></div>"
cards += "<div class='box'><div class='num'>" + str(pqc_pct) + "%</div><div class='label'>quantum-safe (PQC key exchange)</div></div>"
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
html += "<p class='scope'>The sites Canadians actually connect to most, from Semrush's Most Visited Websites in Canada ranking (adult and pirate-stream sites excluded). Scanned " + scan_date + ".</p>\n"
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
html += "<script>\nconst DATA = " + json.dumps(table) + ";\n"
html += "const SCAN_DATE = " + json.dumps(scan_date) + ";\n"
html += """
// same star cell as the main page: filled stars for the steps done, pale ones
// for the rest, breakdown in the hover title
function starCell(r) {
  var stars = r.stars || 0;
  var shown = '';
  for (var i = 0; i < 3; i++) {
    shown += i < stars ? '★' : "<span class='star-off'>★</span>";
  }
  var parts = [];
  parts.push((r.tls.indexOf('1.3') !== -1 ? '✓' : '✗') + ' TLS 1.3');
  parts.push((r.kex.indexOf('MLKEM') !== -1 ? '✓' : '✗') + ' PQC key exchange');
  parts.push((stars === 3 ? '✓' : '✗') + ' PQC signature');
  var title = parts.join('  ·  ');
  return "<span class='stars' title='" + title + "'>" + shown + "</span>";
}

// how much of each big provider's fleet already does PQC, from our own scan (the
// same numbers the main page uses). Lets the next-step line tell "your CDN is
// ready, flip it on" apart from "your CDN is the blocker".
var CDN_PQC_RATE = {
  "Imperva (Incapsula)": 91, "Cloudflare": 80, "Amazon CloudFront": 69,
  "Fastly": 58, "Google": 52, "Akamai": 4, "Azure Front Door": 4,
  "Microsoft (Azure)": 2, "OVH": 0, "Alibaba Cloud": 0
};

// one plain sentence on what this site's next step is, from the same columns the
// row already shows
function adviceFor(r) {
  if (r.stars >= 2) {
    var note = "Quantum-safe today: the connection negotiates a post-quantum key exchange. " +
               "The third star (a post-quantum certificate) is not available from any public CA yet, so there is nothing more this site can do.";
    if (r.source === 'provider') {
      note += " Worth knowing: the PQC comes from its provider (" + r.cdn + "), not its own servers.";
    }
    return note;
  }
  if (r.stars === 1) {
    var rate = CDN_PQC_RATE[r.cdn];
    if (rate !== undefined && rate >= 50) {
      return "TLS 1.3 is done, and its provider (" + r.cdn + ") already negotiates PQC on about " + rate +
             "% of the sites we scan - this site is likely one configuration change away from its second star.";
    }
    if (rate !== undefined) {
      return "TLS 1.3 is done, but its provider (" + r.cdn + ") has PQC on only about " + rate +
             "% of the sites we scan - this site is mostly waiting on " + r.cdn + " to move.";
    }
    return "TLS 1.3 is done. The next step is negotiating ML-KEM, which needs a recent TLS stack " +
           "on its own servers (OpenSSL 3.5+ or equivalent).";
  }
  return "First step: enable TLS 1.3. The post-quantum key exchange cannot be negotiated on TLS 1.2, " +
         "so this site is two steps behind.";
}

// one line of the report card checklist: a tick or a cross, the step name, and
// the value we actually saw (the TLS version, the key-exchange group, etc.)
function checkRow(done, label, detail) {
  var mark = done ? "<span class='rc-yes'>✓</span>" : "<span class='rc-no'>✗</span>";
  return "<div class='rc-check'>" + mark + "<span class='rc-step'>" + label + "</span>" +
         "<span class='rc-detail'>" + detail + "</span></div>";
}

// open the report card for one site: its stars up top, the three-step checklist,
// and the next step. Same card as the main page, readable on its own so you can
// screenshot it.
function showSite(i) {
  var r = DATA[i];
  if (!r) return;

  var hasTls13 = r.tls.indexOf('1.3') !== -1;
  var hasPqcKex = r.kex.indexOf('MLKEM') !== -1;
  var hasPqcSig = r.stars === 3;   // no site has this yet, but keep it honest

  var card = "";
  card += "<div class='rc-head'>";
  card += "<div><div class='rc-site'>" + r.site + "</div>";
  card += "<div class='rc-sub'>" + r.sector + " · " + r.country + " · scanned " + SCAN_DATE + "</div></div>";
  card += "<div class='rc-scorebox'>" + starCell(r) + "</div>";
  card += "<span class='site-detail-close' onclick='hideSite()'>&times;</span>";
  card += "</div>";

  card += "<div class='rc-checks'>";
  card += checkRow(hasTls13, 'TLS 1.3', r.tls);
  card += checkRow(hasPqcKex, 'Post-quantum key exchange', r.kex);
  card += checkRow(hasPqcSig, 'Post-quantum certificate signature', 'no public CA issues these yet');
  card += "</div>";

  card += "<p class='rc-next'><strong>Next step:</strong> " + adviceFor(r) + "</p>";

  var box = document.getElementById('siteDetail');
  box.style.display = 'block';
  box.innerHTML = card;
}

function hideSite() {
  document.getElementById('siteDetail').style.display = 'none';
}

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
