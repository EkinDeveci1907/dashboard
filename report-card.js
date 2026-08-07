// The per-site report card, shared by both pages.
//
// The main dashboard (index.html + app.js) and the most-visited page that
// toplist_report.py generates show the same eight columns and open the same card
// when you click a row, so the code for it lives here once instead of being
// written out twice.
//
// A page hands us its rows before drawing the table:
//     setReportCard(rows, "2026-07-22", {sectorPqc: sectors})
// after that, a row's onclick just calls showSite(i) with its index.

let reportRows = [];
let reportDate = "";
let sectorPqc = {};

// options.sectorPqc is sector name -> {total, pqc} for the Canadian sites in
// this scan. It is the only extra the card needs; everything else on the card
// comes off the row itself.
function setReportCard(rows, scanDate, options) {
  reportRows = rows;
  reportDate = scanDate;
  options = options || {};
  sectorPqc = options.sectorPqc || {};
}

// Everything below is built as a string and handed to innerHTML, and on the
// live tab half of it is whatever the server we just contacted said it was.
// Escape once, here, so a value cannot stop being a value.
function esc(v) {
  if (v === undefined || v === null) return "";
  return String(v)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// The readiness cell: one star per migration step fully done (TLS 1.3, PQC key
// exchange, PQC signature). Filled stars first, empty ones after, and the hover
// title spells out which step is done and which is not. A typical PQC-enabled
// site today shows 2 of 3. the signature star is still open for everyone,
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

// The pill in the "PQC endpoint" column, shared by both tables so the wording
// lives in one place. It says where the connection terminates and nothing else.
// "own infrastructure" covers two cases: a domain with no CDN in front of it,
// and a company serving from a CDN it owns, like google.ca on Google. Both are
// the organisation's own machines, which is what the column is asking.
function sourceLabel(src) {
  if (src === "provider") return "CDN edge";
  if (src === "own") return "own infrastructure";
  return "no PQC";
}

// How this site sits against others doing the same job. The sector shares are
// Canadian, so only say it for a Canadian site. quoting a Canadian rate at a
// German bank would be wrong.
function sectorLineFor(s) {
  if (s.country !== "CANADA") return "";
  let bucket = sectorPqc[s.sector];
  if (!bucket || bucket.total < 5) return "";
  // the count rather than the percentage: "60% of the 60 media domains" reads like
  // a typo, and the raw fraction says how big the sample is at the same time
  let line = bucket.pqc + " of the " + bucket.total + " Canadian " + esc(s.sector) +
             " domains the monitor scans negotiate it. ";
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
         "<span class='rc-detail'>" + esc(detail) + "</span></div>";
}

// open the report card for one site: its stars up top and a three-line
// checklist of what was actually measured. No advice and no next step: the card
// reports the handshake and stops there. Meant to be readable on its own, so you
// can screenshot it and hand it to someone.
function showSite(i) {
  let s = reportRows[i];
  if (!s) return;

  let hasTls13 = s.tls.indexOf("1.3") !== -1;
  let hasPqcKex = s.kex.indexOf("MLKEM") !== -1;
  let hasPqcSig = s.stars === 3;   // no site has this yet, but keep it honest

  // the signature row shows what the certificate is actually signed with today,
  // which is the thing that has to change for the third star. Don't hard-code the
  // "classical" half of that sentence: the row would keep saying it under a tick
  // the day a CA finally issues a post-quantum certificate.
  let sigDetail = s.cert;
  if (!hasPqcSig) {
    sigDetail = s.cert + " - classical, no public CA issues post-quantum yet";
  }
  // checkRow() escapes the detail, so sigDetail stays raw until then

  let card = "";
  // The line under the domain name, built from the parts that are actually known.
  // A domain in the corpus has a sector and a country; one a visitor typed for the
  // first time has neither, and printing "unknown · unknown" is worse than leaving
  // them out. Every row knows its provider. The last part is the handshake time on
  // a live scan and the scan date on a stored row.
  let parts = [];
  if (s.sector && s.sector !== "unknown") {
    // only the sector wants capitalising. the rest already reads how it should
    parts.push("<span class='rc-sector'>" + esc(s.sector) + "</span>");
  }
  if (s.country && s.country !== "unknown") {
    parts.push(esc(s.country));
  }
  if (s.cdn) {
    parts.push("served by " + esc(s.cdn));
  }
  if (s.handshake_ms !== undefined) {
    parts.push("handshake " + esc(s.handshake_ms) + " ms");
  } else {
    parts.push("scanned " + esc(reportDate));
  }
  let sub = parts.join(" · ");

  card += "<div class='rc-head'>";
  card += "<div><div class='rc-site'>" + esc(s.site) + "</div>";
  card += "<div class='rc-sub'>" + sub + "</div></div>";
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

  let box = document.getElementById("siteDetail");
  box.style.display = "block";
  box.innerHTML = card;
}

function hideSite() {
  document.getElementById("siteDetail").style.display = "none";
}
