let allSites = [];
let tlsChart = null;
let kexChart = null;
let cdnChart = null;
let countryChart = null;
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

fetch("scans.json")
  .then(function (response) { return response.json(); })
  .then(function (dates) {
    let picker = document.getElementById("datePicker");
    for (let i = 0; i < dates.length; i++) {
      picker.innerHTML += "<option>" + dates[i] + "</option>";
    }
    picker.value = dates[dates.length - 1];
    showScan(picker.value);

    picker.onchange = function () {
      showScan(picker.value);
    };
  });

function showScan(date) {
  fetch("stats-" + date + ".json")
    .then(function (response) { return response.json(); })
    .then(function (data) {

      let tls13 = data.tls["TLSv1.3"] || 0;
      document.getElementById("s-total").textContent = data.total;
      document.getElementById("s-tls").textContent = Math.round(100 * tls13 / data.total) + "%";
      document.getElementById("s-pqc").textContent = data.pqc_kex_pct + "%";
      document.getElementById("s-sig").textContent = data.pqc_signatures;

      document.getElementById("headline").innerHTML =
        "<strong>" + data.pqc_kex_pct + "%</strong> of " + data.total +
        " Canadian sites negotiate post-quantum key exchange (X25519MLKEM768).";

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
        options: { events: [], plugins: { legend: { display: false } } }   // static chart, plain legend shown below
      });

      // plain caption under the chart, so the labels don't look like clickable buttons
      let tlsLegend = "";
      for (let i = 0; i < tlsLabels.length; i++) {
        tlsLegend += "<span class='legend-item'><span class='dot' style='background:" + tlsColors[i] + "'></span>" + tlsLabels[i] + "</span>";
      }
      document.getElementById("tlsLegend").innerHTML = tlsLegend;

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
        options: { plugins: { legend: { display: false } } }
      });

      let names = Object.keys(data.cdn_families);
      names.sort(function (a, b) { return data.cdn_families[b] - data.cdn_families[a]; });
      let cdnLabels = [];
      let cdnValues = [];
      let otherTotal = 0;
      for (let i = 0; i < names.length; i++) {
        if (i < 8) {
          cdnLabels.push(names[i]);
          cdnValues.push(data.cdn_families[names[i]]);
        } else {
          otherTotal += data.cdn_families[names[i]];
        }
      }
      if (otherTotal > 0) {
        cdnLabels.push("Other");
        cdnValues.push(otherTotal);
      }
      if (cdnChart) cdnChart.destroy();
      cdnChart = new Chart(document.getElementById("cdnChart"), {
        type: "bar",
        data: { labels: cdnLabels, datasets: [{ data: cdnValues, backgroundColor: INDIGO }] },
        options: { indexAxis: "y", plugins: { legend: { display: false } } }
      });

      drawSectorBars(data.sectors);

      document.getElementById("canada-compare").textContent = data.pqc_kex_pct + "%";
      drawCountryChart(data.countries);

      allSites = data.sites;

      // country filter, default to Canada since that is the focus
      let countryNames = [];
      for (let i = 0; i < data.sites.length; i++) {
        if (countryNames.indexOf(data.sites[i].country) === -1) {
          countryNames.push(data.sites[i].country);
        }
      }
      fillFilter("countryFilter", countryNames, "All countries");
      document.getElementById("countryFilter").value = "CANADA";

      fillFilter("sectorFilter", Object.keys(data.sectors), "All sectors");
      let kexes = [];
      for (let i = 0; i < data.sites.length; i++) {
        if (kexes.indexOf(data.sites[i].kex) === -1) {
          kexes.push(data.sites[i].kex);
        }
      }
      fillFilter("kexFilter", kexes, "All key exchanges");
      applyFilters();

      // draw the map last so a map hiccup never blocks the table or the charts above
      drawWorldMap(data.countries);
    });
}

function drawCountryChart(countries) {
  // tiny samples swing wildly, so only chart countries with a real number of sites
  let MIN_SITES = 10;
  let names = [];
  for (let name in countries) {
    if (countries[name].total >= MIN_SITES) {
      names.push(name);
    }
  }
  names.sort(function (a, b) { return countries[b].pct - countries[a].pct; });

  let labels = [];
  let values = [];
  let colors = [];
  for (let i = 0; i < names.length; i++) {
    labels.push(names[i]);
    values.push(countries[names[i]].pct);
    if (names[i] === "CANADA") {
      colors.push(GREEN);
    } else {
      colors.push(GREY);
    }
  }

  if (countryChart) countryChart.destroy();
  countryChart = new Chart(document.getElementById("countryChart"), {
    type: "bar",
    data: { labels: labels, datasets: [{ data: values, backgroundColor: colors }] },
    options: {
      indexAxis: "y",
      plugins: { legend: { display: false } },
      scales: { x: { max: 100, ticks: { callback: function (v) { return v + "%"; } } } }
    }
  });
}

function drawWorldMap(countries) {
  // percent for each country we scanned, shown in the hover tooltip
  let pcts = {};
  let scanned = [];
  for (let name in countries) {
    let code = COUNTRY_CODE[name];
    if (code) {
      pcts[code] = countries[name].pct;
      scanned.push(code);
    }
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
      regionStyle: {
        initial: { fill: "#e5e7eb" },   // countries we did not scan
        selected: { fill: "#4f46e5" }   // countries that are in our data
      },
      onRegionTooltipShow: function (event, tooltip, code) {
        let pct = pcts[code];
        let extra = (pct === undefined) ? "no sites scanned" : pct + "% PQC";
        tooltip.text(tooltip.text() + " - " + extra, true);
      }
    });
  } catch (e) {
    box.innerHTML = "<p class='hint'>Map could not load.</p>";
    return;
  }

  // shade in the countries we scanned; the hover percentages work either way
  try {
    worldMap.setSelectedRegions(scanned);
  } catch (e) {
    // older map versions may not support this, that is fine
  }
}

function drawTable(sites) {
  let rows = "";
  for (let i = 0; i < sites.length; i++) {
    let s = sites[i];
    rows += "<tr>" +
      "<td>" + s.site + "</td>" +
      "<td>" + s.sector + "</td>" +
      "<td>" + s.country + "</td>" +
      "<td>" + s.tls + "</td>" +
      "<td>" + s.kex + "</td>" +
      "<td>" + s.cert + "</td>" +
      "<td>" + s.cdn + "</td>" +
    "</tr>";
  }
  document.getElementById("tableBody").innerHTML = rows;
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
