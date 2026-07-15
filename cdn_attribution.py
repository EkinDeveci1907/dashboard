# For every scanned site: is its PQC coming from the CDN in front of it, or is
# it the org's own doing? The cdn column scan.py fills in already tells us who
# terminates TLS ("Self-hosted", "Cloudflare", "Amazon CloudFront", ...), so if
# a site does ML-KEM and sits behind a CDN, the CDN's edge config is what
# enabled it. If it does ML-KEM while self-hosted, that's the org's own effort.
#   "PQC via provider" - a CDN/cloud terminates TLS, ML-KEM comes from them
#   "PQC own effort"   - self-hosted (or the provider's own site) and still PQC
#   "No PQC"           - classical key exchange only
# No new scan needed, this just re-reads an existing scan CSV.
#
# attribution_for(row) is also imported by enrich.py, so the rule lives here once.
#
# usage: python3 cdn_attribution.py [data/scan-YYYY-MM-DD.csv]
#        no argument = the 2026-07-08 scan (2714 sites)

import csv
import sys
import os

# One catch: if the site itself belongs to the company running the CDN, the PQC
# is their own effort, not outsourced. google.com on Google and cloudflare.com
# on Cloudflare are the companies eating their own cooking; twitch.tv on Amazon
# is Amazon's own site too. Keyed by the cdn label, values are name fragments.
OWN_BRANDS = {
    "Google":            ["google", "youtube", "gmail", "blogger", "blogspot",
                          "gstatic", "android", "goo.gl", "youtu.be", "doubleclick"],
    "Amazon CloudFront": ["amazon", "aws", "primevideo", "audible", "twitch", "imdb"],
    "Amazon (AWS)":      ["amazon", "aws", "primevideo", "audible", "twitch", "imdb"],
    "Microsoft (Azure)": ["microsoft", "bing", "live.com", "office", "outlook",
                          "azure", "msn", "linkedin", "github", "skype", "xbox", "windows"],
    "Azure Front Door":  ["microsoft", "bing", "live.com", "office", "outlook",
                          "azure", "msn", "linkedin", "github", "skype", "xbox", "windows"],
    "Cloudflare":        ["cloudflare"],
    "Fastly":            ["fastly"],
    "Akamai":            ["akamai", "linode"],
    "Automattic":        ["wordpress", "automattic", "tumblr", "woocommerce"],
    "Alibaba Cloud":     ["alibaba", "aliyun", "taobao", "tmall", "alipay", "aliexpress"],
    "Tencent Cloud":     ["tencent", "qq.com", "wechat", "weixin"],
    "Oracle Cloud":      ["oracle"],
    "Naver Cloud":       ["naver"],
    "Dropbox":           ["dropbox"],
    "Wix":               ["wix"],
    "Squarespace":       ["squarespace"],
}


def attribution_for(row):
    # returns one of: "PQC via provider", "PQC own effort", "No PQC", "unreachable"
    if row.get("tls_version", "").strip() == "":
        return "unreachable"

    site = row["site"].strip().lower()
    cdn = row.get("cdn", "").strip()
    kex = row.get("key_exchange", "").upper()
    pqc = "MLKEM" in kex        # the post-quantum group shows up as X25519MLKEM768

    # self-hosted means the org runs its own TLS. and if the site belongs to the
    # CDN company itself, that also counts as their own infra.
    own_infra = (cdn == "Self-hosted" or cdn == "")
    for word in OWN_BRANDS.get(cdn, []):
        if word in site:
            own_infra = True
            break

    if not pqc:
        return "No PQC"
    if own_infra:
        return "PQC own effort"
    return "PQC via provider"


def main():
    IN_FILE = "data/scan-2026-07-08.csv"
    if len(sys.argv) > 1:
        IN_FILE = sys.argv[1]

    # tag the outputs with the scan date, e.g. attribution-2026-07-08.csv
    date = os.path.basename(IN_FILE).replace("scan-", "").replace(".csv", "")

    rows = list(csv.DictReader(open(IN_FILE)))
    print("input: " + IN_FILE + " (" + str(len(rows)) + " rows)")
    print("")

    # work out the attribution for every site
    results = []
    for row in rows:
        attribution = attribution_for(row)
        results.append({"site": row["site"], "sector": row.get("sector", ""),
                        "country": row.get("country", ""),
                        "tls_version": row.get("tls_version", ""),
                        "key_exchange": row.get("key_exchange", ""),
                        "cdn": row.get("cdn", "").strip(), "attribution": attribution})

    # write the per-site attributions
    out1 = "data/attribution-" + date + ".csv"
    out = open(out1, "w", newline="")
    writer = csv.DictWriter(out, fieldnames=["site", "sector", "country", "tls_version",
                                             "key_exchange", "cdn", "attribution"])
    writer.writeheader()
    for r in results:
        writer.writerow(r)
    out.close()

    # roll up per country: via provider / own effort / no PQC (this is the stacked bar)
    countries = {}
    for r in results:
        if r["attribution"] == "unreachable":
            continue
        name = r["country"]
        if name not in countries:
            countries[name] = {"n": 0, "via": 0, "own": 0, "no": 0}
        countries[name]["n"] = countries[name]["n"] + 1
        if r["attribution"] == "PQC via provider":
            countries[name]["via"] = countries[name]["via"] + 1
        elif r["attribution"] == "PQC own effort":
            countries[name]["own"] = countries[name]["own"] + 1
        else:
            countries[name]["no"] = countries[name]["no"] + 1

    # sort countries by total PQC share, highest first
    order = []
    for name in countries:
        c = countries[name]
        pqc_share = (c["via"] + c["own"]) / c["n"]
        order.append((pqc_share, name))
    order.sort(reverse=True)

    out2 = "data/stacked-bar-" + date + ".csv"
    out = open(out2, "w", newline="")
    writer = csv.writer(out)
    writer.writerow(["country", "sites_scanned", "pqc_total_pct",
                     "pqc_via_provider_pct", "pqc_own_effort_pct", "no_pqc_pct",
                     "pqc_via_provider_n", "pqc_own_effort_n", "no_pqc_n"])
    for share, name in order:
        c = countries[name]
        writer.writerow([name, c["n"],
                         round(100 * (c["via"] + c["own"]) / c["n"], 1),
                         round(100 * c["via"] / c["n"], 1),
                         round(100 * c["own"] / c["n"], 1),
                         round(100 * c["no"] / c["n"], 1),
                         c["via"], c["own"], c["no"]])
    out.close()

    # how ready each CDN/provider looks across the sites we saw
    providers = {}
    for r in results:
        if r["cdn"] == "" or r["cdn"] == "Self-hosted" or r["attribution"] == "unreachable":
            continue
        name = r["cdn"]
        if name not in providers:
            providers[name] = {"n": 0, "pqc": 0}
        providers[name]["n"] = providers[name]["n"] + 1
        if r["attribution"] == "PQC via provider" or r["attribution"] == "PQC own effort":
            providers[name]["pqc"] = providers[name]["pqc"] + 1

    # biggest providers first
    provider_order = []
    for name in providers:
        provider_order.append((providers[name]["n"], name))
    provider_order.sort(reverse=True)

    out3 = "data/cdn-readiness-" + date + ".csv"
    out = open(out3, "w", newline="")
    writer = csv.writer(out)
    writer.writerow(["provider", "sites_observed", "sites_with_pqc", "pqc_pct_observed"])
    for n, name in provider_order:
        p = providers[name]
        writer.writerow([name, p["n"], p["pqc"], round(100 * p["pqc"] / p["n"], 1)])
    out.close()

    # print a quick summary
    reachable = 0
    n_pqc = 0
    n_via = 0
    n_own = 0
    for r in results:
        if r["attribution"] == "unreachable":
            continue
        reachable = reachable + 1
        if r["attribution"] == "PQC via provider":
            n_pqc = n_pqc + 1
            n_via = n_via + 1
        if r["attribution"] == "PQC own effort":
            n_pqc = n_pqc + 1
            n_own = n_own + 1

    print("reachable: " + str(reachable) + " | PQC: " + str(n_pqc) +
          " (" + str(round(100 * n_pqc / reachable, 1)) + "%)")
    print("  via provider: " + str(n_via) + " | own effort: " + str(n_own))
    for name in ["CANADA", "USA"]:
        if name in countries:
            c = countries[name]
            print(name + " - " + str(c["n"]) + " sites | PQC " +
                  str(round(100 * (c["via"] + c["own"]) / c["n"], 1)) + "% = " +
                  str(round(100 * c["via"] / c["n"], 1)) + "% provider + " +
                  str(round(100 * c["own"] / c["n"], 1)) + "% own")
    print("")
    print("wrote " + out1)
    print("wrote " + out2)
    print("wrote " + out3)


if __name__ == "__main__":
    main()
