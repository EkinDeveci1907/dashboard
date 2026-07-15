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


# the rows for the table, best score first
table = []
for r in sites:
    table.append({"site": r["site"], "category": r["sector"],
                  "tls": r["tls_version"], "kex": r["key_exchange"],
                  "source": r["pqc_source"], "score": r["readiness_score"]})
table.sort(key=by_score, reverse=True)

# ---- build the page ----
style = """
  body { font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
         color: #1f2937; margin: 0; padding: 32px 40px; background: #ffffff; }
  h1 { font-size: 26px; margin: 0 0 4px; }
  .sub { color: #64748b; margin: 0 0 24px; font-size: 14px; }
  .cards { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 20px; }
  .card { border: 1px solid #e5e7eb; border-radius: 10px; padding: 16px 20px; min-width: 150px; }
  .card .big { font-size: 34px; font-weight: 700; color: #4f46e5; }
  .card .big.green { color: #16a34a; }
  .card .lbl { font-size: 12px; color: #64748b; margin-top: 2px; }
  .note { background: #f1f5f9; border-radius: 8px; padding: 12px 16px; font-size: 13px;
          color: #334155; margin-bottom: 20px; max-width: 900px; }
  input { padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 8px; width: 260px;
          font-size: 14px; margin-bottom: 12px; }
  table { border-collapse: collapse; width: 100%; font-size: 13px; }
  th, td { text-align: left; padding: 7px 10px; border-bottom: 1px solid #eef2f7; }
  th { color: #64748b; font-weight: 600; }
  .pqc { color: #4f46e5; font-weight: 600; }
  .pill { font-size: 11px; padding: 2px 8px; border-radius: 10px; }
  .pill.provider { background: #e0e7ff; color: #3730a3; }
  .pill.own { background: #dcfce7; color: #166534; }
  .pill.none { background: #f1f5f9; color: #94a3b8; }
"""

cards = ""
cards += "<div class='card'><div class='big'>" + str(total) + "</div><div class='lbl'>sites Canadians visit most</div></div>"
cards += "<div class='card'><div class='big green'>" + str(pqc_pct) + "%</div><div class='lbl'>quantum-safe (post-quantum key exchange)</div></div>"
cards += "<div class='card'><div class='big'>" + str(avg_score) + "</div><div class='lbl'>average readiness score / 100</div></div>"
cards += "<div class='card'><div class='big'>" + str(via) + " / " + str(own) + "</div><div class='lbl'>PQC via CDN&nbsp;/&nbsp;own effort</div></div>"

note = ("This is the &ldquo;how Canadians connect to the web&rdquo; view: the sites people in Canada "
        "actually visit most - the global names plus the Canadian staples, with adult sites left out. "
        "Of the ones that PQC, most get it from their CDN rather than their own servers.")

html = "<!doctype html>\n<html>\n<head>\n<meta charset='utf-8'>\n"
html += "<title>Most visited by Canadians - post-quantum readiness</title>\n"
html += "<style>" + style + "</style>\n</head>\n<body>\n"
html += "<h1>Most visited by Canadians</h1>\n"
html += "<p class='sub'>Post-quantum readiness of the sites Canadians connect to most &middot; scanned " + scan_date + "</p>\n"
html += "<div class='cards'>" + cards + "</div>\n"
html += "<p class='note'>" + note + "</p>\n"
html += "<input id='q' placeholder='search a site...' oninput='draw()'>\n"
html += "<table><thead><tr><th>Site</th><th>Category</th><th>TLS</th><th>Key exchange</th><th>PQC from</th><th>Score</th></tr></thead>\n"
html += "<tbody id='rows'></tbody></table>\n"
html += "<script>\nconst DATA = " + json.dumps(table) + ";\n"
html += """
function draw() {
  const q = document.getElementById('q').value.toLowerCase();
  let html = '';
  for (const r of DATA) {
    if (q && !r.site.toLowerCase().includes(q)) continue;
    const kex = r.kex.includes('MLKEM') ? "<span class='pqc'>" + r.kex + "</span>" : r.kex;
    const src = r.source ? r.source : 'none';
    html += "<tr><td>" + r.site + "</td><td>" + r.category + "</td><td>" + r.tls +
            "</td><td>" + kex + "</td><td><span class='pill " + src + "'>" + src +
            "</span></td><td>" + r.score + "</td></tr>";
  }
  document.getElementById('rows').innerHTML = html;
}
draw();
</script>
</body>
</html>"""

open("canada-topvisited.html", "w").write(html)
print("wrote canada-topvisited.html")
print("  " + str(total) + " sites, " + str(pqc_pct) + "% quantum-safe, avg score " + str(avg_score))
