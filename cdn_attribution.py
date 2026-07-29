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


def brand_owns(site, word):
    # Does this domain really belong to the brand, or do the letters just happen
    # to appear in it? "loblaws.ca" contains "aws" and "metoffice.gov.uk"
    # contains "office" - neither is Amazon's or Microsoft's site, and counting
    # them as own effort would pad the one number this project is built on.
    # A brand word has to be a whole piece of the domain, or start one:
    # googleapis and primevideo count, loblaws does not.
    if "." in word:
        return site == word or site.endswith("." + word)
    for label in site.split("."):
        if label == word or label.startswith(word):
            return True
    return False


# the short value that goes in the pqc_source column and the site table.
# aggregate.py and enrich.py both read it from here so there's one copy.
PQC_SOURCE = {
    "PQC via provider": "provider",
    "PQC own effort": "own",
    "No PQC": "none",
    "unreachable": "",
}


def attribution_for(row):
    # returns one of: "PQC via provider", "PQC own effort", "No PQC", "unreachable"
    #
    # A row only counts if the scan filled in everything. scan.py leaves the cdn
    # blank whenever any of the crypto fields came back empty - it skips the CDN
    # step entirely for those - so a half-filled row would look self-hosted here
    # and get called "own effort" when nobody ever checked who serves it. Same
    # test aggregate.py uses.
    for field in ["tls_version", "key_exchange", "cert", "cdn"]:
        if row.get(field, "").strip() == "":
            return "unreachable"

    site = row["site"].strip().lower()
    cdn = row.get("cdn", "").strip()
    kex = row.get("key_exchange", "").upper()
    pqc = "MLKEM" in kex        # the post-quantum group shows up as X25519MLKEM768

    # self-hosted means the org runs its own TLS. and if the site belongs to the
    # CDN company itself, that also counts as their own infra.
    own_infra = (cdn == "Self-hosted")
    for word in OWN_BRANDS.get(cdn, []):
        if brand_owns(site, word):
            own_infra = True
            break

    if not pqc:
        return "No PQC"
    if own_infra:
        return "PQC own effort"
    return "PQC via provider"


# how many sites we need to see on a provider before quoting a percentage for it.
# three out of three is not "100% ready", it's three sites.
MIN_SITES_FOR_RATE = 5


def provider_counts(rows):
    # provider name -> {n, pqc} over the sites we actually reached. Self-hosted
    # is not a provider so it stays out. main() and provider_pqc_rates() below
    # both count off this, so the csv and the dashboard can't disagree.
    counts = {}
    for row in rows:
        attribution = attribution_for(row)
        cdn = row.get("cdn", "").strip()
        if attribution == "unreachable" or cdn == "" or cdn == "Self-hosted":
            continue
        if cdn not in counts:
            counts[cdn] = {"n": 0, "pqc": 0}
        counts[cdn]["n"] = counts[cdn]["n"] + 1
        if attribution != "No PQC":
            counts[cdn]["pqc"] = counts[cdn]["pqc"] + 1
    return counts


def provider_pqc_rates(rows):
    # the rates the report card quotes back at you. Same counts as the csv, but
    # only for providers we've seen enough of to be worth a number.
    counts = provider_counts(rows)
    rates = {}
    for cdn in counts:
        if counts[cdn]["n"] >= MIN_SITES_FOR_RATE:
            rates[cdn] = round(100 * counts[cdn]["pqc"] / counts[cdn]["n"])
    return rates


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

    # how ready each CDN/provider looks across the sites we saw. the csv keeps
    # every provider, however few sites we saw it on - sites_observed is right
    # there to judge it by. the dashboard is the one that needs a cutoff.
    providers = provider_counts(rows)

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

    if reachable == 0:
        print("nothing in " + IN_FILE + " answered, so there is nothing to attribute")
        return

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
