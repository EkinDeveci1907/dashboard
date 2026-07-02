let allSites = [];
let tlsChart = null;
let kexChart = null;
let cdnChart = null;

const INDIGO = "#4f46e5";
const GREEN = "#16a34a";
const GREY = "#cbd5e1";

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
        " public sites negotiate post-quantum key exchange (X25519MLKEM768).";

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
        options: { events: [] }   // static chart: no hover, clicking, or legend toggling
      });

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

      allSites = data.sites;
      fillFilter("sectorFilter", Object.keys(data.sectors), "All sectors");
      let kexes = [];
      for (let i = 0; i < data.sites.length; i++) {
        if (kexes.indexOf(data.sites[i].kex) === -1) {
          kexes.push(data.sites[i].kex);
        }
      }
      fillFilter("kexFilter", kexes, "All key exchanges");
      drawTable(allSites);
    });
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
  let sector = document.getElementById("sectorFilter").value;
  let kex = document.getElementById("kexFilter").value;
  let show12 = document.getElementById("tls12").checked;
  let show13 = document.getElementById("tls13").checked;

  let matches = [];
  for (let i = 0; i < allSites.length; i++) {
    let s = allSites[i];
    if (!s.site.toLowerCase().includes(term)) continue;
    if (sector && s.sector !== sector) continue;
    if (kex && s.kex !== kex) continue;
    if (s.tls.indexOf("1.2") !== -1 && !show12) continue;
    if (s.tls.indexOf("1.3") !== -1 && !show13) continue;
    matches.push(s);
  }
  drawTable(matches);
}

document.getElementById("search").oninput = applyFilters;
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
