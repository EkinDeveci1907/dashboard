// The "Scan a domain" tab. The page is static like the rest of the dashboard, so
// api/app.py does the handshake and hands back JSON; this asks it for a domain
// and draws the answer.
//
// report-card.js draws the card, same as the other two tabs, so a live scan and
// a stored row look identical.

// Which scanner to talk to. Published, it is always the deployed one, and it has
// to be https or the browser blocks the call as mixed content. Locally there are
// two possibilities, so the page tries them in order rather than making you edit
// this file: your own copy of the service if you happen to be running it, and
// the deployed one if you are not. That second case is the common one. Someone
// who clones the repo and runs ./run.sh to look at the dashboard gets a working
// Scan tab without having to start a Python service first.
const LOCAL = (location.hostname === "localhost" || location.hostname === "127.0.0.1");
const DEPLOYED_API = "https://pqc-monitor-scan.onrender.com";
const LOCAL_API = "http://127.0.0.1:8000";

let API = LOCAL ? LOCAL_API : DEPLOYED_API;

function setStatus(text) {
  document.getElementById("status").textContent = text;
}

function clearResult() {
  document.getElementById("siteDetail").style.display = "none";
}

// When the handshake happened, and whether it came out of the cache. Worth
// saying plainly, because the card shows a millisecond figure either way and on
// a cached result that number is from the earlier moment, not from now.
function measuredLine(r) {
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
    setStatus("Could not reach the scanner. It is a separate service. On the published " +
              "site it may be waking up, so try again in a moment. Running locally, " +
              "start it with  cd api && uvicorn app:app --port 8000");
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

  // Settle which scanner we are talking to before anything else asks it for a
  // scan. Running locally, a failure here is not fatal: it means you are not
  // running your own copy, so fall back to the deployed one and carry on.
  //
  // This has to happen before the ?domain= shortcut below, so that a shared
  // link opened on localhost still reaches the deployed service instead of
  // reporting the scanner unreachable.
  let health = await healthOf(API);
  if (!health && LOCAL) {
    API = DEPLOYED_API;
    health = await healthOf(API);
  }

  // if the page was opened with ?domain=, run it straight away so shared links work
  let asked = new URLSearchParams(window.location.search).get("domain");
  if (asked) {
    document.getElementById("domain").value = asked;
    runScan(asked);
    return;
  }

  // Nothing asked for yet, so say up front whether a scan would even work,
  // rather than letting someone type a domain and wait on a dead service.
  if (!health) {
    setStatus("The scanner service is not responding, so live scans will not work right now.");
    return;
  }
  if (!health.sees_mlkem) {
    setStatus("Warning: the scanner's openssl is too old to see the post-quantum group, " +
              "so every domain will come back classical.");
  }
}

// Ask a scanner whether it is up. Returns its answer, or null if it is not
// there, which is the only thing the caller needs to tell the two apart.
async function healthOf(base) {
  try {
    return await (await fetch(base + "/api/health")).json();
  } catch (e) {
    return null;
  }
}

start();
