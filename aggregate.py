# Turns the raw scan CSVs into the small JSON files the web page reads.
# For every data/scan-<date>.csv it writes one stats-<date>.json, and it writes
# scans.json listing all the dates. Doing the counting here means the browser just
# loads a ready-made summary instead of adding up hundreds of rows every time.

import csv
import json
import glob
import os

from cdn_attribution import attribution_for, provider_pqc_rates, PQC_SOURCE
from readiness_score import score_site, stars_for, has_pqc_signature


def has_pqc_key_exchange(kex):
    # the post-quantum group we're looking for shows up as X25519MLKEM768
    return "MLKEM" in kex.upper()


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


def stars_last_time(csv_path):
    # star rating per site from the scan before this one, so the report card can
    # say whether a site moved. Worked out here rather than in the browser - the
    # page would otherwise have to download a second whole scan to answer it.
    if csv_path == "":
        return {}
    was = {}
    for row in csv.DictReader(open(csv_path)):
        if row["site"] and row["tls_version"] and row["key_exchange"] and row["cert"] and row["cdn"]:
            score, band, tls_pts, kex_pts, sig_pts = score_site(row)
            was[row["site"]] = stars_for(tls_pts, kex_pts, sig_pts)
    return was


def summarise_one_scan(csv_path, date, previous_path="", previous_date=""):
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
    cdn_pqc_counts = {}
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

        # count which CDN / network serves the site, and how many of that CDN's
        # sites already negotiate PQC - the CDN chart stacks one on the other,
        # which is what shows a CDN's PQC readiness (Cloudflare full, Akamai empty)
        cdn = clean_cdn_name(row["cdn"])
        if cdn not in cdn_counts:
            cdn_counts[cdn] = 0
            cdn_pqc_counts[cdn] = 0
        cdn_counts[cdn] = cdn_counts[cdn] + 1
        if has_pqc_key_exchange(row["key_exchange"]):
            cdn_pqc_counts[cdn] = cdn_pqc_counts[cdn] + 1

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

    # 4. The site table lists every site we scanned, not just Canada. Each row
    #    also gets where its PQC comes from, its 0-100 readiness score, and the
    #    star rating (0-3) the page shows instead of raw points - all worked
    #    out with the same rules as cdn_attribution.py and readiness_score.py.
    was = stars_last_time(previous_path)
    sites = []
    for row in scanned:
        attribution = attribution_for(row)
        score, band, tls_pts, kex_pts, sig_pts = score_site(row)
        site = {"site": row["site"], "sector": row["sector"], "country": row["country"],
                "tls": row["tls_version"], "kex": row["key_exchange"],
                "cert": row["cert"], "cdn": clean_cdn_name(row["cdn"]),
                "pqc_source": PQC_SOURCE.get(attribution, ""),
                "score": score,
                "stars": stars_for(tls_pts, kex_pts, sig_pts)}
        # what this site did in the scan before, for the report card. missing
        # means it wasn't in that scan (or didn't answer it), which is not the
        # same as "no change", so leave it out rather than guess.
        if row["site"] in was:
            site["was"] = was[row["site"]]
        sites.append(site)

    # overall Canadian PQC percentage (guard against dividing by zero)
    if len(canada) > 0:
        pqc_pct = round(100 * pqc_count / len(canada))
    else:
        pqc_pct = 0

    # 5. How much of each provider's fleet already does PQC. The report card
    #    quotes this back at you, and it used to be a list typed in by hand that
    #    went stale every scan, so work it out here instead.
    cdn_rates = provider_pqc_rates(scanned)

    return {
        "scan_date": date,
        "previous_scan": previous_date,
        "country_focus": "CANADA",
        "total": len(canada),
        "total_all": len(scanned),
        "tls": tls_counts,
        "pqc_kex_pct": pqc_pct,
        "pqc_signatures": signature_count,
        "kex_families": kex_counts,
        "cdn_families": cdn_counts,
        "cdn_pqc": cdn_pqc_counts,
        "cdn_rates": cdn_rates,
        "sectors": sectors,
        "countries": countries,
        "sites": sites,
    }


# Run the summary for every scan CSV we have, oldest date first.
# The "-enriched" copies (scan.py output plus the three extra columns) are skipped
# here - they hold the same sites, and we don't want them as separate dates.
scans = []
for path in sorted(glob.glob("data/scan-*.csv")):
    if "-enriched" not in path:
        scans.append(path)

dates = []
previous_path = ""
previous_date = ""
for path in scans:
    date = os.path.basename(path).replace("scan-", "").replace(".csv", "")
    stats = summarise_one_scan(path, date, previous_path, previous_date)
    json.dump(stats, open("stats-" + date + ".json", "w"), indent=2)
    dates.append(date)
    previous_path = path
    previous_date = date
    print("made stats-" + date + ".json")

json.dump(dates, open("scans.json", "w"), indent=2)
print("scans.json now lists " + str(len(dates)) + " scans")
