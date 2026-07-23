// Front-end for the monitor. Loads the precomputed stats-<date>.json for the chosen
// scan, fills the summary cards, draws the charts (Chart.js) and the world map
// (jsvectormap), and wires up the search/filter on the site table. No build step,
// just plain JS loaded with defer.

let allSites = [];
let shownSites = [];
let currentScanDate = "";
let tlsChart = null;
let kexChart = null;
let cdnChart = null;
let worldMap = null;

const INDIGO = "#4f46e5";
const GREEN = "#16a34a";
const GREY = "#cbd5e1";

// map our country labels to the two letter codes the world map uses
const COUNTRY_CODE = {
  CANADA: "CA", USA: "US", UK: "GB", CHINA: "CN", RUSSIA: "RU", GERMANY: "DE",
  FRANCE: "FR", JAPAN: "JP", BRAZIL: "BR", SPAIN: "ES", AUSTRALIA: "AU", INDIA: "IN",
  SWITZERLAND: "CH", KOREA: "KR", ITALY: "IT", POLAND: "PL", SINGAPORE: "SG",
  BELGIUM: "BE", NETHERLANDS: "NL", ARGENTINA: "AR", TURKEY: "TR", INDONESIA: "ID",
  CZECHIA: "CZ", QATAR: "QA", TAIWAN: "TW", SWEDEN: "SE", IRELAND: "IE",
  SLOVENIA: "SI", MEXICO: "MX", NORWAY: "NO", "NEW ZEALAND": "NZ", KAZAKHSTAN: "KZ", ISRAEL: "IL",
  HONGKONG: "HK"
};

// on page load: get the list of scan dates, fill the dropdown, and show the newest one
async function loadScanDates() {
  let response = await fetch("scans.json");
  let dates = await response.json();

  let picker = document.getElementById("datePicker");
  for (let i = 0; i < dates.length; i++) {
    picker.innerHTML += "<option>" + dates[i] + "</option>";
  }
  picker.value = dates[dates.length - 1];   // the newest scan is last in the list
  showScan(picker.value);

  // when you pick a different date, redraw everything for that scan
  picker.onchange = function () {
    showScan(picker.value);
  };
}
loadScanDates();

// Load one scan's summary json and redraw the whole page from it. Each step below
// is its own small function, so you can read this like a table of contents.
async function showScan(date) {
  let response = await fetch("stats-" + date + ".json");
  let data = await response.json();

  currentScanDate = date;
  updateSummaryCards(data);
  drawTlsChart(data);
  drawKexChart(data);
  drawCdnChart(data);
  drawSectorBars(data.sectors);

  document.getElementById("canada-compare").textContent = data.pqc_kex_pct + "%";

  setupFilters(data);

  // draw the map last so a map hiccup never blocks the table or the charts above
  drawWorldMap(data.countries);
}

// the four big numbers at the top, plus the one-line headline
function updateSummaryCards(data) {
  let tls13 = data.tls["TLSv1.3"] || 0;
  document.getElementById("s-total").textContent = data.total;
  document.getElementById("s-tls").textContent = Math.round(100 * tls13 / data.total) + "%";
  document.getElementById("s-pqc").textContent = data.pqc_kex_pct + "%";
  document.getElementById("s-sig").textContent = data.pqc_signatures;

  document.getElementById("headline").innerHTML =
    "<strong>" + data.pqc_kex_pct + "%</strong> of " + data.total +
    " Canadian sites negotiate post-quantum key exchange (X25519MLKEM768).";
}

// TLS version doughnut (green for 1.3, grey for older)
function drawTlsChart(data) {
  let tlsLabels = Object.keys(data.tls);
  let tlsColors = [];
  for (let i = 0; i < tlsLabels.length; i++) {
    if (tlsLabels[i] === "TLSv1.3") {
      tlsColors.push(GREEN);
    } else {
      tlsColors.push(GREY);
    }
  }
  if (tlsChart) tlsChart.destroy();
  tlsChart = new Chart(document.getElementById("tlsChart"), {
    type: "doughnut",
    data: {
      labels: tlsLabels,
      datasets: [{ data: Object.values(data.tls), backgroundColor: tlsColors }]
    },
    // maintainAspectRatio off so the doughnut fills its fixed-height box
    // instead of growing to a giant square. static chart, plain legend below.
    options: { events: [], maintainAspectRatio: false, plugins: { legend: { display: false } } }
  });

  // plain caption under the chart, so the labels don't look like clickable buttons
  let tlsLegend = "";
  for (let i = 0; i < tlsLabels.length; i++) {
    tlsLegend += "<span class='legend-item'><span class='dot' style='background:" + tlsColors[i] + "'></span>" + tlsLabels[i] + "</span>";
  }
  document.getElementById("tlsLegend").innerHTML = tlsLegend;
}

// key-exchange bar (indigo for the PQC group, grey for the classical ones)
function drawKexChart(data) {
  let kexLabels = Object.keys(data.kex_families);
  let kexColors = [];
  for (let i = 0; i < kexLabels.length; i++) {
    if (kexLabels[i].includes("MLKEM")) {
      kexColors.push(INDIGO);
    } else {
      kexColors.push(GREY);
    }
  }
  if (kexChart) kexChart.destroy();
  kexChart = new Chart(document.getElementById("kexChart"), {
    type: "bar",
    data: {
      labels: kexLabels,
      datasets: [{ data: Object.values(data.kex_families), backgroundColor: kexColors }]
    },
    // fill the fixed-height box so it lines up with the TLS chart beside it
    options: { maintainAspectRatio: false, plugins: { legend: { display: false } } }
  });
}

// CDN bar: show the 8 most common, and roll the rest into one "Other" bar.
// Each bar is stacked into the sites already negotiating PQC and the sites not,
// so the same chart also reads as each CDN's PQC readiness - Cloudflare's bar
// comes out nearly all indigo, Akamai's (all the big banks) nearly all grey.
function drawCdnChart(data) {
  let names = Object.keys(data.cdn_families);
  names.sort(function (a, b) { return data.cdn_families[b] - data.cdn_families[a]; });

  let pqcByCdn = data.cdn_pqc || {};   // a summary from before this split just shows all-grey bars

  let cdnLabels = [];
  let pqcValues = [];
  let restValues = [];
  let otherTotal = 0;
  let otherPqc = 0;
  for (let i = 0; i < names.length; i++) {
    let total = data.cdn_families[names[i]];
    let pqc = pqcByCdn[names[i]] || 0;
    if (i < 8) {
      cdnLabels.push(names[i]);
      pqcValues.push(pqc);
      restValues.push(total - pqc);
    } else {
      otherTotal += total;
      otherPqc += pqc;
    }
  }
  if (otherTotal > 0) {
    cdnLabels.push("Other");
    pqcValues.push(otherPqc);
    restValues.push(otherTotal - otherPqc);
  }
  if (cdnChart) cdnChart.destroy();
  cdnChart = new Chart(document.getElementById("cdnChart"), {
    type: "bar",
    data: {
      labels: cdnLabels,
      datasets: [
        { label: "negotiates PQC", data: pqcValues, backgroundColor: INDIGO },
        { label: "no PQC", data: restValues, backgroundColor: GREY }
      ]
    },
    options: {
      indexAxis: "y",
      scales: { x: { stacked: true }, y: { stacked: true, ticks: { autoSkip: false } } }
    }
  });
}

// fill the three dropdown filters and show the Canadian rows first
function setupFilters(data) {
  allSites = data.sites;

  // country dropdown, defaulting to Canada since that's the focus
  let countryNames = [];
  for (let i = 0; i < data.sites.length; i++) {
    if (countryNames.indexOf(data.sites[i].country) === -1) {
      countryNames.push(data.sites[i].country);
    }
  }
  fillFilter("countryFilter", countryNames, "All countries");
  document.getElementById("countryFilter").value = "CANADA";

  // sector dropdown
  fillFilter("sectorFilter", Object.keys(data.sectors), "All sectors");

  // key-exchange dropdown
  let kexes = [];
  for (let i = 0; i < data.sites.length; i++) {
    if (kexes.indexOf(data.sites[i].kex) === -1) {
      kexes.push(data.sites[i].kex);
    }
  }
  fillFilter("kexFilter", kexes, "All key exchanges");

  applyFilters();
}

function drawWorldMap(countries) {
  // Build two lookups keyed by the map's two-letter country code:
  //   shadeByCode - just the PQC percent, which decides how dark a country is drawn
  //   infoByCode  - the full {pqc, total, pct}, used to fill in the hover tooltip
  let shadeByCode = {};
  let infoByCode = {};
  let highestPct = 0;
  let lowestPct = 100;
  for (let name in countries) {
    let code = COUNTRY_CODE[name];
    if (!code) continue;                 // skip any country the map doesn't have
    let c = countries[name];
    shadeByCode[code] = c.pct;
    infoByCode[code] = c;
    if (c.pct > highestPct) highestPct = c.pct;
    if (c.pct < lowestPct) lowestPct = c.pct;
  }

  // the map library needs a clean element, so remove any map we drew before
  let box = document.getElementById("worldMap");
  if (worldMap) {
    worldMap.destroy();
    worldMap = null;
  }
  box.innerHTML = "";
  if (typeof jsVectorMap === "undefined") return;

  try {
    worldMap = new jsVectorMap({
      selector: "#worldMap",
      map: "world",
      zoomOnScroll: false,
      showTooltip: true,                 // turn on the little box that appears on hover
      regionStyle: {
        initial: { fill: "#e5e7eb" }   // countries we did not scan
      },
      // shade each scanned country by its PQC share, light to dark
      visualizeData: {
        scale: ["#c7d2fe", "#312e81"],
        values: shadeByCode
      },
      // on hover, show how many of that country's sites use PQC, e.g. "204 / 535 sites use PQC (38%)"
      onRegionTooltipShow: function (event, tooltip, code) {
        let c = infoByCode[code];
        let extra;
        if (c) {
          extra = c.pqc + " / " + c.total + " sites use PQC (" + c.pct + "%)";
        } else {
          extra = "no sites scanned";
        }
        tooltip.text(tooltip.text() + " — " + extra, true);
      }
    });
  } catch (e) {
    box.innerHTML = "<p class='hint'>Map could not load.</p>";
    return;
  }

  // label the ends of the colour scale with the real lowest and highest numbers
  // (the library stretches its shading between the lowest and highest value we give it)
  document.getElementById("mapScaleLow").textContent = lowestPct + "%";
  document.getElementById("mapScaleHigh").textContent = highestPct + "%";
  document.getElementById("mapLegend").style.display = "flex";
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

// How much of each big provider's fleet already negotiates PQC, from our own
// scan (the numbers in data/cdn-readiness-2026-07-08.csv, rounded). This is
// what lets the advice line tell "your CDN is ready, flip it on" apart from
// "your CDN is the blocker".
const CDN_PQC_RATE = {
  "Imperva (Incapsula)": 91, "Cloudflare": 80, "Amazon CloudFront": 69,
  "Fastly": 58, "Google": 52, "Akamai": 4, "Azure Front Door": 4,
  "Microsoft (Azure)": 2, "OVH": 0, "Alibaba Cloud": 0
};

// One plain sentence on what a site's next step is, worked out from the same
// measurements the row already shows. The idea comes from pqc-monitor, which
// attaches a recommendation to every finding - ours is per site instead.
function adviceFor(s) {
  if (s.stars >= 2) {
    let note = "Quantum-safe today: the connection negotiates a post-quantum key exchange. " +
               "The third star (a post-quantum certificate) is not available from any public CA yet, so there is nothing more this site can do.";
    return note;
  }
  if (s.stars === 1) {
    let rate = CDN_PQC_RATE[s.cdn];
    if (rate !== undefined && rate >= 50) {
      return "TLS 1.3 is done, and its provider (" + s.cdn + ") already negotiates PQC on about " + rate +
             "% of the sites we scan - this site is likely one configuration change away from its second star.";
    }
    if (rate !== undefined) {
      return "TLS 1.3 is done, but its provider (" + s.cdn + ") has PQC on only about " + rate +
             "% of the sites we scan - this site is mostly waiting on " + s.cdn + " to move.";
    }
    return "TLS 1.3 is done. The next step is negotiating ML-KEM, which needs a recent TLS stack " +
           "on its own servers (OpenSSL 3.5+ or equivalent).";
  }
  return "First step: enable TLS 1.3. The post-quantum key exchange cannot be negotiated on TLS 1.2, " +
         "so this site is two steps behind.";
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
  let s = shownSites[i];
  if (!s) return;

  let hasTls13 = s.tls.indexOf("1.3") !== -1;
  let hasPqcKex = s.kex.indexOf("MLKEM") !== -1;
  let hasPqcSig = s.stars === 3;   // no site has this yet, but keep it honest

  let card = "";
  card += "<div class='rc-head'>";
  card += "<div><div class='rc-site'>" + s.site + "</div>";
  card += "<div class='rc-sub'>" + s.sector + " · " + s.country + " · scanned " + currentScanDate + "</div></div>";
  card += "<div class='rc-scorebox'>" + starCell(s) + "</div>";
  card += "<span class='site-detail-close' onclick='hideSite()'>&times;</span>";
  card += "</div>";

  card += "<div class='rc-checks'>";
  card += checkRow(hasTls13, "TLS 1.3", s.tls);
  card += checkRow(hasPqcKex, "Post-quantum key exchange", s.kex);
  card += checkRow(hasPqcSig, "Post-quantum certificate signature", "no public CA issues these yet");
  card += "</div>";

  card += "<p class='rc-next'><strong>Next step:</strong> " + adviceFor(s) + "</p>";

  let box = document.getElementById("siteDetail");
  box.style.display = "block";
  box.innerHTML = card;
}

function hideSite() {
  document.getElementById("siteDetail").style.display = "none";
}

function drawTable(sites) {
  shownSites = sites;
  let rows = "";
  for (let i = 0; i < sites.length; i++) {
    let s = sites[i];
    // the post-quantum group is the whole point, so highlight it when it's there
    let kexCell = s.kex;
    if (s.kex.indexOf("MLKEM") !== -1) {
      kexCell = "<span class='kex-pqc'>" + s.kex + "</span>";
    }
    // where the PQC comes from (provider / own / none), shown as a small pill
    let src = s.pqc_source ? s.pqc_source : "none";
    rows += "<tr onclick='showSite(" + i + ")'>" +
      "<td>" + s.site + "</td>" +
      "<td>" + s.sector + "</td>" +
      "<td>" + s.country + "</td>" +
      "<td>" + s.tls + "</td>" +
      "<td>" + kexCell + "</td>" +
      "<td>" + s.cdn + "</td>" +
      "<td><span class='pill pill-" + src + "'>" + src + "</span></td>" +
      "<td>" + starCell(s) + "</td>" +
    "</tr>";
  }
  document.getElementById("tableBody").innerHTML = rows;
  document.getElementById("tableCount").textContent =
    sites.length + " of " + allSites.length + " sites shown";
}

function drawSectorBars(sectors) {
  let names = Object.keys(sectors);
  names.sort(function (a, b) {
    return (sectors[b].pqc / sectors[b].total) - (sectors[a].pqc / sectors[a].total);
  });
  let html = "";
  for (let i = 0; i < names.length; i++) {
    let s = sectors[names[i]];
    let pct = Math.round(100 * s.pqc / s.total);
    html += "<div class='sector-row'>" +
              "<div class='sector-name'>" + names[i] + "</div>" +
              "<div class='sector-track'><div class='sector-fill' style='width:" + pct + "%'></div></div>" +
              "<div class='sector-pct'>" + pct + "%</div>" +
            "</div>";
  }
  document.getElementById("sectorBars").innerHTML = html;
}

function applyFilters() {
  let term = document.getElementById("search").value.toLowerCase();
  let country = document.getElementById("countryFilter").value;
  let sector = document.getElementById("sectorFilter").value;
  let kex = document.getElementById("kexFilter").value;
  let show12 = document.getElementById("tls12").checked;
  let show13 = document.getElementById("tls13").checked;

  let matches = [];
  for (let i = 0; i < allSites.length; i++) {
    let s = allSites[i];
    if (!s.site.toLowerCase().includes(term)) continue;
    if (country && s.country !== country) continue;
    if (sector && s.sector !== sector) continue;
    if (kex && s.kex !== kex) continue;
    if (s.tls.indexOf("1.2") !== -1 && !show12) continue;
    if (s.tls.indexOf("1.3") !== -1 && !show13) continue;
    matches.push(s);
  }
  drawTable(matches);
}

document.getElementById("search").oninput = applyFilters;
document.getElementById("countryFilter").onchange = applyFilters;
document.getElementById("sectorFilter").onchange = applyFilters;
document.getElementById("kexFilter").onchange = applyFilters;
document.getElementById("tls12").onchange = applyFilters;
document.getElementById("tls13").onchange = applyFilters;

function fillFilter(id, values, allLabel) {
  values.sort();
  let menu = document.getElementById(id);
  menu.innerHTML = "<option value=''>" + allLabel + "</option>";
  for (let i = 0; i < values.length; i++) {
    menu.innerHTML += "<option>" + values[i] + "</option>";
  }
}

// the countdown numbers on the roadmap card, worked out from today's date so
// the card never goes stale (deadlines from the GC PQC migration roadmap)
let thisYear = new Date().getFullYear();
document.getElementById("y2031").textContent = (2031 - thisYear) + " years away";
document.getElementById("y2035").textContent = (2035 - thisYear) + " years away";
