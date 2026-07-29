// The per-site report card, shared by both pages.
//
// The main dashboard (index.html + app.js) and the most-visited page that
// toplist_report.py generates show the same eight columns and open the same card
// when you click a row, so the code for it lives here once instead of being
// written out twice.
//
// A page hands us its rows before drawing the table:
//     setReportCard(rows, "2026-07-22", cdnRates)
// after that, a row's onclick just calls showSite(i) with its index.

let reportRows = [];
let reportDate = "";
let cdnPqcRate = {};
let sectorPqc = {};

// cdnRates is provider name -> what percent of that provider's sites already
// negotiate PQC, measured in the same scan. aggregate.py works it out and puts
// it in the stats json; toplist_report.py bakes the same numbers into its page.
// It used to be a table typed in by hand, which went stale every scan.
function setReportCard(rows, scanDate, cdnRates, options) {
  reportRows = rows;
  reportDate = scanDate;
  cdnPqcRate = cdnRates || {};
  options = options || {};
  sectorPqc = options.sectorPqc || {};
}

// The readiness cell: one star per migration step fully done (TLS 1.3, PQC key
// exchange, PQC signature). Filled stars first, empty ones after, and the hover
// title spells out which step is done and which is not. A typical quantum-safe
// site today shows 2 of 3 - the signature star is still open for everyone,
// because no public CA issues PQC certificates yet.
function starCell(s) {
  let stars = s.stars || 0;
  let shown = "";
  for (let i = 0; i < 3; i++) {
    if (i < stars) {
      shown += "★";
    } else {
      shown += "<span class='star-off'>★</span>";
    }
  }
  let parts = [];
  parts.push((s.tls.indexOf("1.3") !== -1 ? "✓" : "✗") + " TLS 1.3");
  parts.push((s.kex.indexOf("MLKEM") !== -1 ? "✓" : "✗") + " PQC key exchange");
  parts.push((stars === 3 ? "✓" : "✗") + " PQC signature");
  let title = parts.join("  ·  ");
  return "<span class='stars' title='" + title + "'>" + shown + "</span>";
}

// One plain sentence on what a site's next step is, worked out from the same
// measurements the row already shows. The idea comes from pqc-monitor, which
// attaches a recommendation to every finding - ours is per site instead.
// Knowing the provider's own PQC rate is what lets this tell "your CDN is
// ready, flip it on" apart from "your CDN is the blocker".
function adviceFor(s) {
  if (s.stars >= 2) {
    return "Quantum-safe today: the connection negotiates a post-quantum key exchange. " +
           "The third star (a post-quantum certificate) is not available from any public CA yet, so there is nothing more this site can do.";
  }
  if (s.stars === 1) {
    let rate = cdnPqcRate[s.cdn];
    if (rate !== undefined && rate >= 50) {
      return "TLS 1.3 is done, and its provider (" + s.cdn + ") already negotiates PQC on about " + rate +
             "% of the sites we scan - this site is likely one configuration change away from its second star.";
    }
    if (rate !== undefined) {
      return "TLS 1.3 is done, but its provider (" + s.cdn + ") has PQC on only about " + rate +
             "% of the sites we scan - this site is mostly waiting on " + s.cdn + " to move.";
    }
    // self-hosted, or a provider we see too few sites on to quote a rate for
    return "TLS 1.3 is done. The next step is negotiating ML-KEM, which needs a recent TLS stack " +
           "(OpenSSL 3.5+ or equivalent) on whatever terminates TLS for this site.";
  }
  // no stars: TLS 1.2, so the key exchange is not even reachable yet. Still worth
  // saying where the provider stands, because that decides whether the second
  // star follows on its own once TLS 1.3 is on or turns into another wait.
  let first = "First step: enable TLS 1.3. The post-quantum key exchange cannot be negotiated on TLS 1.2, " +
              "so this site is two steps behind.";
  let rate = cdnPqcRate[s.cdn];
  if (rate !== undefined && rate >= 50) {
    return first + " Its provider (" + s.cdn + ") already negotiates PQC on about " + rate +
           "% of the sites we scan, so the second star should follow once TLS 1.3 is on.";
  }
  if (rate !== undefined) {
    return first + " After that it would still be waiting on " + s.cdn +
           ", which has PQC on only about " + rate + "% of the sites we scan.";
  }
  return first;
}

// How this site sits against others doing the same job. The sector shares are
// Canadian, so only say it for a Canadian site - quoting a Canadian rate at a
// German bank would be wrong.
function sectorLineFor(s) {
  if (s.country !== "CANADA") return "";
  let bucket = sectorPqc[s.sector];
  if (!bucket || bucket.total < 5) return "";
  // the count rather than the percentage: "60% of the 60 media sites" reads like
  // a typo, and the raw fraction says how big the sample is at the same time
  let line = bucket.pqc + " of the " + bucket.total + " Canadian " + s.sector +
             " sites we scan negotiate it. ";
  if (s.kex.indexOf("MLKEM") !== -1) {
    return line + "This one is among them.";
  }
  return line + "This one is not.";
}

// one line of the report card's checklist: a tick or a cross, the step name,
// and the detail we actually saw (the TLS version, the key-exchange group, etc.)
function checkRow(done, label, detail) {
  let mark = done ? "<span class='rc-yes'>✓</span>" : "<span class='rc-no'>✗</span>";
  return "<div class='rc-check'>" + mark + "<span class='rc-step'>" + label + "</span>" +
         "<span class='rc-detail'>" + detail + "</span></div>";
}

// open the report card for one site: its stars up top, a three-line
// checklist of what we actually measured, and the next step. Meant to be
// readable on its own - you can screenshot it and hand it to someone.
function showSite(i) {
  let s = reportRows[i];
  if (!s) return;

  let hasTls13 = s.tls.indexOf("1.3") !== -1;
  let hasPqcKex = s.kex.indexOf("MLKEM") !== -1;
  let hasPqcSig = s.stars === 3;   // no site has this yet, but keep it honest

  // the signature row shows what the certificate is actually signed with today,
  // which is the thing that has to change for the third star
  let sigDetail = s.cert + " - classical, no public CA issues post-quantum yet";

  let card = "";
  card += "<div class='rc-head'>";
  card += "<div><div class='rc-site'>" + s.site + "</div>";
  // only the sector wants capitalising - the rest is already how it should read
  card += "<div class='rc-sub'><span class='rc-sector'>" + s.sector + "</span> · " +
          s.country + " · served by " + s.cdn + " · scanned " + reportDate + "</div></div>";
  card += "<div class='rc-scorebox'>" + starCell(s) + "</div>";
  card += "<span class='site-detail-close' onclick='hideSite()'>&times;</span>";
  card += "</div>";

  card += "<div class='rc-checks'>";
  card += checkRow(hasTls13, "TLS 1.3", s.tls);
  card += checkRow(hasPqcKex, "Post-quantum key exchange", s.kex);
  card += checkRow(hasPqcSig, "Post-quantum certificate signature", sigDetail);
  card += "</div>";

  let sectorLine = sectorLineFor(s);
  if (sectorLine !== "") {
    card += "<p class='rc-peer'>" + sectorLine + "</p>";
  }

  card += "<p class='rc-next'><strong>Next step:</strong> " + adviceFor(s) + "</p>";

  let box = document.getElementById("siteDetail");
  box.style.display = "block";
  box.innerHTML = card;
}

function hideSite() {
  document.getElementById("siteDetail").style.display = "none";
}
