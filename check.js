// The "Scan a site" tab. The page is static like the rest of the dashboard, so
// api/app.py does the handshake and hands back JSON; this asks it for a domain
// and draws the answer.
//
// report-card.js draws the card, same as the other two tabs, so a live scan and
// a stored row look identical.

// Picking the scanner by hostname means the same file works locally and once
// published, instead of being edited before every push. The deployed one has to
// be https or the browser blocks the call as mixed content.
const LOCAL = (location.hostname === "localhost" || location.hostname === "127.0.0.1");
const API = LOCAL ? "http://127.0.0.1:8000" : "https://pqc-monitor-scan.onrender.com";

function setStatus(text) {
  document.getElementById("status").textContent = text;
}

function clearResult() {
  document.getElementById("siteDetail").style.display = "none";
}

// Whether this was a fresh handshake or a cached answer. Worth saying plainly:
// the card shows a handshake time either way, and on a cached result that number
// is from when it was measured, not from now.
function measuredLine(r) {
  // the timing itself is on the card now. this line only has to say when the
  // handshake happened, because on a cached result the card's millisecond
  // figure is from that earlier moment and not from now.
  let at = r.scanned_at ? " at " + r.scanned_at : "";
  if (r.cached) {
    return "Returned from the cache. Scan completed" + at + ".";
  }
  return "Scan completed" + at + ".";
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
    setStatus("Could not reach the scanner. It runs as a separate service, see api/README.md.");
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
    stars: r.stars,
    handshake_ms: r.handshake_ms
  };
  setReportCard([row], today);
  showSite(0);

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
