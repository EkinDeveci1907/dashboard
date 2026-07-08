# Turns the raw scan CSVs into the small JSON files the web page reads.
# For every data/scan-<date>.csv it writes one stats-<date>.json, and it writes
# scans.json listing all the dates. Doing the counting here means the browser just
# loads a ready-made summary instead of adding up hundreds of rows every time.

import csv
import json
import glob
import os


def has_pqc_key_exchange(kex):
    # the post-quantum group we're looking for shows up as X25519MLKEM768
    return "MLKEM" in kex.upper()


def has_pqc_signature(cert):
    # no public CA issues these yet, so in practice this stays False for now
    return "MLDSA" in cert.upper() or "DILITHIUM" in cert.upper()


def clean_cdn_name(raw):
    # the scanner already writes a clean name like "Cloudflare" or "Self-hosted",
    # so we just trim spaces and label the blank ones (sites that didn't answer).
    raw = raw.strip()
    if raw == "":
        return "Unknown"
    return raw


def key_exchange_group(kex):
    # bucket the key exchange into a few families for the chart
    text = kex.upper()
    if "MLKEM" in text:
        return "X25519MLKEM768 (PQC)"
    if "X25519" in text:
        return "X25519 (classical)"
    if "SECP256" in text or "PRIME256V1" in text:
        return "secp256r1"
    return "other"


def summarise_one_scan(csv_path, date):
    # 1. Read the rows, keeping only the ones where every field is filled in
    #    (a site that didn't answer is written with blanks, and we skip those).
    scanned = []
    for row in csv.DictReader(open(csv_path)):
        if row["site"] and row["tls_version"] and row["key_exchange"] and row["cert"] and row["cdn"]:
            scanned.append(row)

    # 2. Count PQC for every country, so we can compare Canada to the rest of the world.
    countries = {}
    for row in scanned:
        country = row["country"]
        if country == "":
            country = "OTHER"
        if country not in countries:
            countries[country] = {"total": 0, "pqc": 0, "pct": 0}
        countries[country]["total"] = countries[country]["total"] + 1
        if has_pqc_key_exchange(row["key_exchange"]):
            countries[country]["pqc"] = countries[country]["pqc"] + 1
    # turn each country's counts into a percentage
    for country in countries:
        countries[country]["pct"] = round(100 * countries[country]["pqc"] / countries[country]["total"])

    # 3. The headline numbers are Canada only, so pull out just the Canadian rows.
    canada = []
    for row in scanned:
        if row["country"] == "CANADA":
            canada.append(row)

    # tallies we build up as we walk the Canadian rows
    tls_counts = {}
    kex_counts = {}
    cdn_counts = {}
    sectors = {}
    pqc_count = 0
    signature_count = 0

    for row in canada:
        # count TLS versions (1.2 vs 1.3)
        tls = row["tls_version"]
        if tls not in tls_counts:
            tls_counts[tls] = 0
        tls_counts[tls] = tls_counts[tls] + 1

        # count key-exchange families (the PQC one vs the classical ones)
        family = key_exchange_group(row["key_exchange"])
        if family not in kex_counts:
            kex_counts[family] = 0
        kex_counts[family] = kex_counts[family] + 1

        # count which CDN / network serves the site
        cdn = clean_cdn_name(row["cdn"])
        if cdn not in cdn_counts:
            cdn_counts[cdn] = 0
        cdn_counts[cdn] = cdn_counts[cdn] + 1

        # set up this sector's PQC tally the first time we see it
        sector = row["sector"]
        if sector == "":
            sector = "other"
        if sector not in sectors:
            sectors[sector] = {"total": 0, "pqc": 0}
        sectors[sector]["total"] = sectors[sector]["total"] + 1

        # add to the PQC totals (overall and for this sector)
        if has_pqc_key_exchange(row["key_exchange"]):
            pqc_count = pqc_count + 1
            sectors[sector]["pqc"] = sectors[sector]["pqc"] + 1
        if has_pqc_signature(row["cert"]):
            signature_count = signature_count + 1

    # 4. The site table lists every site we scanned, not just Canada.
    sites = []
    for row in scanned:
        sites.append({"site": row["site"], "sector": row["sector"], "country": row["country"],
                      "tls": row["tls_version"], "kex": row["key_exchange"],
                      "cert": row["cert"], "cdn": clean_cdn_name(row["cdn"])})

    # overall Canadian PQC percentage (guard against dividing by zero)
    if len(canada) > 0:
        pqc_pct = round(100 * pqc_count / len(canada))
    else:
        pqc_pct = 0

    return {
        "scan_date": date,
        "country_focus": "CANADA",
        "total": len(canada),
        "total_all": len(scanned),
        "tls": tls_counts,
        "pqc_kex_pct": pqc_pct,
        "pqc_signatures": signature_count,
        "kex_families": kex_counts,
        "cdn_families": cdn_counts,
        "sectors": sectors,
        "countries": countries,
        "sites": sites,
    }


# Run the summary for every scan CSV we have, oldest date first.
dates = []
for path in sorted(glob.glob("data/scan-*.csv")):
    date = os.path.basename(path).replace("scan-", "").replace(".csv", "")
    stats = summarise_one_scan(path, date)
    json.dump(stats, open("stats-" + date + ".json", "w"), indent=2)
    dates.append(date)
    print("made stats-" + date + ".json")

json.dump(dates, open("scans.json", "w"), indent=2)
print("scans.json now lists " + str(len(dates)) + " scans")
