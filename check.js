// The "Scan a site" tab. The page is static like the rest of the dashboard, so
// api/app.py does the handshake and hands back JSON; this asks it for a domain
// and draws the answer.
//
// report-card.js draws the card, same as the other two tabs, so a live scan and
// a stored row look identical. What this file adds is the three things only a
// live scan has: the handshake time, the earlier scans, and the comparison.

// Picking the scanner by hostname means the same file works locally and once
// published, instead of being edited before every push. The deployed one has to
// be https or the browser blocks the call as mixed content.
const LOCAL = (location.hostname === "localhost" || location.hostname === "127.0.0.1");
const API = LOCAL ? "http://127.0.0.1:8000" : "https://pqc-monitor-scan.onrender.com";

let cdnRates = {};

// The corpus numbers the report card needs (each provider's PQC rate, used to
// tell "your CDN is ready, flip it on" apart from "your CDN is the blocker").
// aggregate.py already puts them in the stats json, so read them from there
// rather than keeping a second copy that goes stale.
async function loadCdnRates() {
  try {
    let scans = await (await fetch("scans.json", {cache: "no-store"})).json();
    let latest = scans[scans.length - 1];
    let stats = await (await fetch("stats-" + latest + ".json", {cache: "no-store"})).json();
    cdnRates = stats.cdn_rates || {};
  } catch (e) {
    // not fatal. without the rates the card still draws, it just gives the
    // generic next step instead of naming the provider's rate.
    cdnRates = {};
  }
}

function setStatus(text) {
  document.getElementById("status").textContent = text;
}

function clearResult() {
  document.getElementById("siteDetail").style.display = "none";
  document.getElementById("live").innerHTML = "";
}

// Whether this was a fresh handshake or a cached answer. Worth saying plainly:
// the card shows a handshake time either way, and on a cached result that number
// is from when it was measured, not from now.
function measuredLine(r) {
  // the timing itself is on the card now. this line only has to say whether the
  // handshake happened just now or came back out of the cache, because the
  // number means different things in those two cases.
  if (r.cached) {
    return "Measured within the last hour, returned from the cache.";
  }
  return "Measured just now.";
}

// What the site looked like in the scans we already had. This is the part no
// other checker can do - they see one moment, we have the series. Two months of
// "no change" is a finding, not an absence of one.
function historyBlock(r) {
  let h = r.history || [];
  if (h.length === 0) {
    return "<p class='rc-peer'>We had not scanned this site before, so there is no history yet. " +
           "It has been added to the queue for the next full scan.</p>";
  }

  let dots = "";
  for (let i = 0; i < h.length; i++) {
    let cls = h[i].pqc ? "hist-on" : "hist-off";
    let label = h[i].date + ": " + (h[i].pqc ? "post-quantum" : "classical");
    dots += "<span class='hist-dot " + cls + "' title='" + label + "'></span>";
  }

  // did it ever change? comparing first to last is enough for a sentence - the
  // dots above are there for anyone who wants the detail.
  let first = h[0];
  let last = h[h.length - 1];
  let sentence = "";
  if (first.pqc === last.pqc && !first.pqc) {
    sentence = "Classical in every scan since " + first.date + ". Nothing has changed.";
  } else if (first.pqc === last.pqc && first.pqc) {
    sentence = "Post-quantum in every scan since " + first.date + ".";
  } else if (last.pqc) {
    sentence = "Turned post-quantum on between " + first.date + " and " + last.date + ".";
  } else {
    sentence = "Was post-quantum in " + first.date + " and is not now, which is worth a second look.";
  }

  return "<div class='hist'><span class='hist-label'>Earlier scans</span>" + dots +
         "<span class='hist-note'>" + sentence + "</span></div>";
}

// Where it sits against everything else we track. Only says the Canadian lines
// for a Canadian site - the population is Canadian, so quoting it at a US site
// would be a number without a meaning.
function contextBlock(r) {
  let c = r.context || {};
  if (!c.canada_total) return "";

  let lines = [];
  if (c.ahead !== undefined) {
    lines.push("<strong>" + c.ahead + "</strong> of the " + c.canada_total +
               " Canadian sites we track are further along than this one, and " +
               c.same + " are at the same point.");
  }
  if (c.sector_total) {
    lines.push(c.sector_pqc + " of the " + c.sector_total + " Canadian " + c.sector +
               " sites we scan negotiate post-quantum key exchange.");
  }
  lines.push("Across the Canadian sites in the " + c.scan_date + " scan, " +
             c.canada_pqc_pct + "% do.");

  return "<p class='rc-peer'>" + lines.join(" ") + "</p>";
}

async function runScan(domain) {
  clearResult();
  setStatus("Contacting " + domain + "...");

  let r;
  try {
    let response = await fetch(API + "/api/scan?domain=" + encodeURIComponent(domain));
    r = await response.json();
    if (r.error) {
      setStatus(r.error);
      return;
    }
  } catch (e) {
    // the usual cause is the scanner not being up, so say that rather than
    // showing the browser's own network error, which tells the reader nothing.
    setStatus("Could not reach the scanner. It runs as a separate service - see api/README.md.");
    return;
  }

  setStatus(measuredLine(r));

  // hand the live result to the shared card renderer as a one-row table. The
  // date we pass is today, not the corpus scan date, because this row was
  // measured now and the card prints that date on its face.
  let today = new Date().toISOString().slice(0, 10);
  let row = {
    site: r.site,
    sector: r.sector || "unknown",
    country: r.country || "unknown",
    tls: r.tls,
    kex: r.kex,
    cert: r.cert,
    cdn: r.cdn,
    source: r.source,
    stars: r.stars,
    handshake_ms: r.handshake_ms
  };
  setReportCard([row], today, cdnRates);
  showSite(0);

  document.getElementById("live").innerHTML = historyBlock(r) + contextBlock(r);

  // make the result linkable. check.html?domain=rbc.com reproduces this page,
  // which is what makes a single site's card something you can send to someone.
  history.replaceState(null, "", "check.html?domain=" + encodeURIComponent(r.site));
}

function submit() {
  let value = document.getElementById("domain").value.trim();
  if (value === "") {
    setStatus("Type a domain first.");
    return;
  }
  runScan(value);
}

async function start() {
  await loadCdnRates();

  document.getElementById("go").onclick = submit;
  document.getElementById("domain").addEventListener("keydown", function (e) {
    if (e.key === "Enter") submit();
  });

  // if the page was opened with ?domain=, run it straight away so shared links work
  let asked = new URLSearchParams(window.location.search).get("domain");
  if (asked) {
    document.getElementById("domain").value = asked;
    runScan(asked);
    return;
  }

  // otherwise check the scanner is actually up, so someone typing a domain into
  // a dead service gets told before they wait on it rather than after.
  try {
    let health = await (await fetch(API + "/api/health")).json();
    if (!health.sees_mlkem) {
      setStatus("Warning: the scanner's openssl is too old to see the post-quantum group, " +
                "so every site will come back classical.");
    }
  } catch (e) {
    setStatus("The scanner service is not responding, so live scans will not work right now.");
  }
}

start();
