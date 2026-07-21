# A 0-100 "quantum readiness" score for each site we scan.
#
# The prof's idea from the Jul 9 meeting was: since we already take good
# measurements, turn them into a single score so sites can be ranked and
# compared over time. This is a first version of that, built only from what
# the scan already records - TLS version, key-exchange group, cert signature.
# No new data, and nothing fancy: three parts that add up to 100.
#
# How the points are reasoned:
#   - You cannot do post-quantum key exchange without TLS 1.3, so TLS 1.3 is
#     the foundation and earns points on its own. TLS 1.2 gets a little (it's
#     still safe today) but it's a dead end for PQC.
#   - The part that actually matters right now is a post-quantum (ML-KEM) key
#     exchange - that's what stops "harvest now, decrypt later". Biggest chunk.
#   - Post-quantum signatures (ML-DSA / SLH-DSA) are the second half of the
#     migration. Basically no public site has them yet, so these points are
#     headroom: what a fully migrated site will score later.
#
# So a normal PQC site today lands at 75 ("quantum-ready"), with 25 points of
# room still to earn once certificate authorities start issuing PQC certs.
#
# usage: python3 readiness_score.py [data/scan-YYYY-MM-DD.csv]
#        no argument = the 2026-07-08 scan

import csv
import sys
import os

IN_FILE = "data/scan-2026-07-08.csv"
if len(sys.argv) > 1:
    IN_FILE = sys.argv[1]

date = os.path.basename(IN_FILE).replace("scan-", "").replace(".csv", "")

# The 100 points, split out as plain numbers so they're easy to argue about
# with the prof and easy to change in one place.
TLS_1_3_POINTS   = 20   # TLS 1.3 present - the floor you need before any PQC
TLS_1_2_POINTS   = 5    # still on TLS 1.2 - safe today, but a dead end for PQC
PQC_KEX_POINTS   = 55   # post-quantum key exchange (ML-KEM) - the urgent part
MODERN_KEX_POINTS = 15  # no PQC yet, but a modern curve (X25519 / P-256), ready to flip
PQC_SIG_POINTS   = 25   # post-quantum certificate signature - the second half


def tls_points(tls_version):
    if "1.3" in tls_version:
        return TLS_1_3_POINTS
    if "1.2" in tls_version:
        return TLS_1_2_POINTS
    return 0


def kex_points(key_exchange):
    text = key_exchange.upper()
    if "MLKEM" in text:
        return PQC_KEX_POINTS
    # a modern classical curve isn't post-quantum, but the site is one config
    # change away from it, so give partial credit
    if "X25519" in text or "SECP256" in text or "PRIME256" in text:
        return MODERN_KEX_POINTS
    return 0


def sig_points(cert):
    text = cert.upper()
    if "MLDSA" in text or "DILITHIUM" in text or "SLHDSA" in text or "SPHINCS" in text:
        return PQC_SIG_POINTS
    return 0


def band_for(score):
    # a plain-language label to go with the number
    if score >= 75:
        return "Quantum-ready"
    if score >= 35:
        return "Modern, not quantum-safe"
    return "Legacy"


def stars_for(tls, kex, sig):
    # The Jul 16 meeting call: each of the three parts is pass/fail at the
    # depth we measure, so present them as stars instead of points ("if it's
    # 0 or 20, then it's a star"). One star per part fully earned:
    #   TLS 1.3 - PQC key exchange - PQC signature.
    # Partial points (TLS 1.2 = 5, modern curve = 15) don't earn the star -
    # a star means done, not almost. The 0-100 stays underneath for sorting
    # and for when signatures arrive; the stars are what people read.
    stars = 0
    if tls == TLS_1_3_POINTS:
        stars = stars + 1
    if kex == PQC_KEX_POINTS:
        stars = stars + 1
    if sig == PQC_SIG_POINTS:
        stars = stars + 1
    return stars


def score_site(row):
    # add up the three parts and return the total, the band, and the breakdown
    tls = tls_points(row["tls_version"])
    kex = kex_points(row["key_exchange"])
    sig = sig_points(row["cert"])
    total = tls + kex + sig
    return total, band_for(total), tls, kex, sig


def stars_site(row):
    # the star rating for one scan row, 0 to 3
    total, band, tls, kex, sig = score_site(row)
    return stars_for(tls, kex, sig)


def main():
    rows = list(csv.DictReader(open(IN_FILE)))
    print("input: " + IN_FILE + " (" + str(len(rows)) + " rows)")
    print("")

    # score every site that actually answered (blank rows are sites that didn't)
    scored = []
    for row in rows:
        if row["tls_version"].strip() == "" or row["key_exchange"].strip() == "":
            continue
        total, band, tls, kex, sig = score_site(row)
        scored.append({"site": row["site"], "sector": row.get("sector", ""),
                       "country": row.get("country", ""),
                       "tls_version": row["tls_version"], "key_exchange": row["key_exchange"],
                       "cert": row["cert"], "cdn": row.get("cdn", ""),
                       "tls_pts": tls, "kex_pts": kex, "sig_pts": sig,
                       "score": total, "band": band,
                       "stars": stars_for(tls, kex, sig)})

    # write the per-site scores
    out1 = "data/readiness-" + date + ".csv"
    out = open(out1, "w", newline="")
    writer = csv.DictWriter(out, fieldnames=["site", "sector", "country", "tls_version",
                                             "key_exchange", "cert", "cdn",
                                             "tls_pts", "kex_pts", "sig_pts", "score", "band",
                                             "stars"])
    writer.writeheader()
    for r in scored:
        writer.writerow(r)
    out.close()

    # average score per country, plus how many sites fall in each band
    countries = {}
    for r in scored:
        name = r["country"]
        if name not in countries:
            countries[name] = {"n": 0, "sum": 0, "ready": 0, "modern": 0, "legacy": 0}
        countries[name]["n"] = countries[name]["n"] + 1
        countries[name]["sum"] = countries[name]["sum"] + r["score"]
        if r["band"] == "Quantum-ready":
            countries[name]["ready"] = countries[name]["ready"] + 1
        elif r["band"] == "Modern, not quantum-safe":
            countries[name]["modern"] = countries[name]["modern"] + 1
        else:
            countries[name]["legacy"] = countries[name]["legacy"] + 1

    # order the countries by average score, highest first
    order = []
    for name in countries:
        avg = countries[name]["sum"] / countries[name]["n"]
        order.append((avg, name))
    order.sort(reverse=True)

    out2 = "data/readiness-by-country-" + date + ".csv"
    out = open(out2, "w", newline="")
    writer = csv.writer(out)
    writer.writerow(["country", "sites", "avg_score",
                     "quantum_ready", "modern", "legacy"])
    for avg, name in order:
        c = countries[name]
        writer.writerow([name, c["n"], round(avg, 1), c["ready"], c["modern"], c["legacy"]])
    out.close()

    # summary for the terminal
    total_sites = len(scored)
    avg_all = 0
    for r in scored:
        avg_all = avg_all + r["score"]
    avg_all = round(avg_all / total_sites, 1)
    print("scored " + str(total_sites) + " sites | average score " + str(avg_all) + "/100")

    for name in ["CANADA", "USA"]:
        if name in countries:
            c = countries[name]
            avg = round(c["sum"] / c["n"], 1)
            print(name + ": avg " + str(avg) + " | ready " + str(c["ready"]) +
                  ", modern " + str(c["modern"]) + ", legacy " + str(c["legacy"]))

    # a few worked examples so the score is easy to sanity-check
    print("")
    print("examples:")
    for want in ["cloudflare.com", "rbc.com", "canada.ca", "google.com"]:
        for r in scored:
            if r["site"] == want:
                print("  " + r["site"].ljust(16) + " " + str(r["stars"]) + "/3 stars, score " +
                      str(r["score"]) + " (" + r["band"] + ")  = tls " + str(r["tls_pts"]) +
                      " + kex " + str(r["kex_pts"]) + " + sig " + str(r["sig_pts"]))
                break

    print("")
    print("wrote " + out1)
    print("wrote " + out2)


if __name__ == "__main__":
    main()
