// Front-end for the monitor. Loads the precomputed stats-<date>.json for the chosen
// scan, fills the summary cards, draws the charts (Chart.js) and the world map
// (jsvectormap), and wires up the search/filter on the site table. No build step,
// just plain JS loaded with defer. The per-site report card lives in
// report-card.js, which the most-visited page uses too.

let allSites = [];
let currentScanDate = "";
let cdnRates = {};
let previousScanDate = "";
let sectorTotals = {};
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
  let options = "";
  for (let i = 0; i < dates.length; i++) {
    options += "<option>" + dates[i] + "</option>";
  }
  picker.innerHTML = options;
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
//
// Order matters. Everything we can draw ourselves goes first - the cards, the
// sector bars, the table - then the three Chart.js charts and the map, which
// need libraries fetched from a CDN. If that CDN is blocked or slow, the charts
// are the only thing missing instead of the whole page below the cards.
async function showScan(date) {
  let response = await fetch("stats-" + date + ".json");
  let data = await response.json();

  currentScanDate = date;
  cdnRates = data.cdn_rates || {};
  previousScanDate = data.previous_scan || "";
  sectorTotals = data.sectors;

  updateSummaryCards(data);
  drawSectorBars(data.sectors);
  document.getElementById("canada-compare").textContent = data.pqc_kex_pct + "%";
  showCanadaCaNote(data.sites);
  setupFilters(data);

  drawCharts(data);
  drawWorldMap(data.countries);
}

// The three charts, all of them Chart.js. If it didn't download, swap each
// canvas for a line saying so and carry on - the rest of the page is ours and
// doesn't need it. Picking another date runs this again, so check the canvas is
// still there before touching it.
function drawCharts(data) {
  if (typeof Chart === "undefined") {
    let ids = ["tlsChart", "kexChart", "cdnChart"];
    for (let i = 0; i < ids.length; i++) {
      let canvas = document.getElementById(ids[i]);
      if (!canvas) continue;
      canvas.insertAdjacentHTML("afterend", "<p class='hint'>Chart could not load.</p>");
      canvas.remove();
    }
    return;
  }
  drawTlsChart(data);
  drawKexChart(data);
  drawCdnChart(data);
}

// canada.ca on the government's own deadline card. Hard-coding "it has no stars"
// means the page starts lying the day they move, so read it off the scan. We
// scan the apex and the www host separately and they disagree - the apex is
// still TLS 1.2 while www is on 1.3 - so talk about the post-quantum key
// exchange, which neither of them does and which is the point of the sentence.
function showCanadaCaNote(sites) {
  let found = false;
  let anyPqc = false;
  for (let i = 0; i < sites.length; i++) {
    let s = sites[i];
    if (s.site === "canada.ca" || s.site === "www.canada.ca") {
      found = true;
      if (s.kex.indexOf("MLKEM") !== -1) anyPqc = true;
    }
  }
  let note = "";
  if (found && !anyPqc) {
    note = ", and canada.ca itself still does not negotiate a post-quantum key exchange";
  } else if (found) {
    note = ", and canada.ca itself now negotiates a post-quantum key exchange";
  }
  document.getElementById("canada-ca-note").textContent = note;
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
    // a 2:1 shape, worked out from the chart's own width. a doughnut left alone
    // draws itself square and enormous, and taking the height from the box around
    // it broke the day a browser had an older index.html cached. static chart,
    // plain legend below.
    options: { events: [], aspectRatio: 2, plugins: { legend: { display: false } } }
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
    // same 2:1 shape as the TLS chart, so the two line up side by side
    options: { aspectRatio: 2, plugins: { legend: { display: false } } }
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

function drawTable(sites) {
  // hand the rows to report-card.js so a click can find the site again, plus
  // what the card needs to put a site in context
  setReportCard(sites, currentScanDate, cdnRates,
                {previousDate: previousScanDate, sectorPqc: sectorTotals});
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
  let options = "<option value=''>" + allLabel + "</option>";
  for (let i = 0; i < values.length; i++) {
    options += "<option>" + values[i] + "</option>";
  }
  // build the whole list first and set it once, rather than appending to
  // innerHTML in the loop, which makes the browser re-parse the menu each time
  document.getElementById(id).innerHTML = options;
}

// the countdown on the roadmap card, worked out from today's date so it doesn't
// go stale (deadlines from the GC PQC migration roadmap). once a deadline is
// here it says so rather than counting down past zero.
function yearsAway(deadline) {
  let left = deadline - new Date().getFullYear();
  if (left > 1) return left + " years away";
  if (left === 1) return "next year";
  if (left === 0) return "this year";
  return "already passed";
}
document.getElementById("y2031").textContent = yearsAway(2031);
document.getElementById("y2035").textContent = yearsAway(2035);
