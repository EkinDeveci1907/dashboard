import csv
import json
import glob
import os

CDN_RULES = [
    ("CLOUDFLARE", "Cloudflare"), ("AKAMAI", "Akamai"), ("FASTLY", "Fastly"),
    ("INCAPSULA", "Imperva (Incapsula)"), ("SUCURI", "Sucuri"), ("CDN77", "CDN77"),
    ("CDNVIDEO", "CDNvideo"), ("EPISERVER", "Optimizely"), ("OPTIMIZELY", "Optimizely"),
    ("DOSARREST", "DOSarrest"), ("LINK11", "Link11"), ("EDGIO", "Edgio"),
    ("LLNW", "Edgio"), ("LIMELIGHT", "Edgio"), ("GCORE", "Gcore"), ("G-CORE", "Gcore"),
    ("KEYCDN", "KeyCDN"), ("STACKPATH", "StackPath"), ("BUNNY", "BunnyCDN"),
    ("ZEN-ECN", "Zenlayer"), ("ZENLAYER", "Zenlayer"), ("RADWARE", "Radware"), ("F5 ", "F5"),
    ("AMAZON", "Amazon (AWS)"), ("GOOGLE", "Google"), ("MICROSOFT", "Microsoft (Azure)"),
    ("AZURE", "Microsoft (Azure)"), ("ORACLE", "Oracle Cloud"), ("ALIBABA", "Alibaba Cloud"),
    ("TENCENT", "Tencent Cloud"), ("HWCLOUDS", "Huawei Cloud"), ("HUAWEI", "Huawei Cloud"),
    ("SAMSUNGSDS", "Samsung SDS"), ("NHN-", "Naver Cloud"), ("IDCF", "IDC Frontier"),
    ("OVH", "OVH"), ("HETZNER", "Hetzner"), ("LEASEWEB", "Leaseweb"), ("IWEB", "Leaseweb"),
    ("AUTOMATTIC", "Automattic"), ("SQUARESPACE", "Squarespace"), ("WIX", "Wix"),
    ("WEEBLY", "Weebly"), ("GANDI", "Gandi"), ("DHOSTING", "Rackspace"), ("RACKSPACE", "Rackspace"),
    ("CPANEL", "cPanel hosting"), ("ONECOM", "One.com"), ("NETWORK-SOLUTIONS", "Network Solutions"),
    ("SINGLEHOP", "Internap"), ("ZOHO", "Zoho"), ("DROPBOX", "Dropbox"), ("OPENTEXT", "OpenText"),
    ("SEDO", "Sedo (parking)"), ("PROXAD", "Free (hosting)"), ("NUDAY", "Nuday"),
]


def is_pqc(kex):
    return "MLKEM" in kex.upper()


def is_pqc_sig(cert):
    return "MLDSA" in cert.upper() or "DILITHIUM" in cert.upper()


def cdn_name(raw):
    raw = raw.strip()
    if raw == "":
        return "Unknown"
    if " - " not in raw:
        return raw
    up = raw.upper()
    for word, name in CDN_RULES:
        if word in up:
            return name
    return "Self-hosted"


def kex_group(kex):
    up = kex.upper()
    if "MLKEM" in up:
        return "X25519MLKEM768 (PQC)"
    if "X25519" in up:
        return "X25519 (classical)"
    if "SECP256" in up or "PRIME256V1" in up:
        return "secp256r1"
    return "other"


def aggregate(csv_path, date):
    rows = []
    for r in csv.DictReader(open(csv_path)):
        if r["site"] and r["tls_version"] and r["key_exchange"] and r["cert"] and r["cdn"]:
            rows.append(r)

    tls_counts = {}
    kex_counts = {}
    cdn_counts = {}
    sectors = {}
    sites = []
    pqc_count = 0
    sig_count = 0

    for r in rows:
        tls = r["tls_version"]
        if tls not in tls_counts:
            tls_counts[tls] = 0
        tls_counts[tls] = tls_counts[tls] + 1

        family = kex_group(r["key_exchange"])
        if family not in kex_counts:
            kex_counts[family] = 0
        kex_counts[family] = kex_counts[family] + 1

        cdn = cdn_name(r["cdn"])
        if cdn not in cdn_counts:
            cdn_counts[cdn] = 0
        cdn_counts[cdn] = cdn_counts[cdn] + 1

        sector = r["sector"]
        if sector == "":
            sector = "other"
        if sector not in sectors:
            sectors[sector] = {"total": 0, "pqc": 0}
        sectors[sector]["total"] = sectors[sector]["total"] + 1

        if is_pqc(r["key_exchange"]):
            pqc_count = pqc_count + 1
            sectors[sector]["pqc"] = sectors[sector]["pqc"] + 1
        if is_pqc_sig(r["cert"]):
            sig_count = sig_count + 1

        sites.append({"site": r["site"], "sector": r["sector"], "country": r["country"],
                      "tls": r["tls_version"], "kex": r["key_exchange"],
                      "cert": r["cert"], "cdn": cdn})

    if len(rows) > 0:
        pqc_pct = round(100 * pqc_count / len(rows))
    else:
        pqc_pct = 0

    return {
        "scan_date": date,
        "total": len(rows),
        "tls": tls_counts,
        "pqc_kex_pct": pqc_pct,
        "pqc_signatures": sig_count,
        "kex_families": kex_counts,
        "cdn_families": cdn_counts,
        "sectors": sectors,
        "sites": sites,
    }


dates = []
for path in sorted(glob.glob("data/scan-*.csv")):
    date = os.path.basename(path).replace("scan-", "").replace(".csv", "")
    stats = aggregate(path, date)
    json.dump(stats, open("stats-" + date + ".json", "w"), indent=2)
    dates.append(date)
    print("made stats-" + date + ".json")

json.dump(dates, open("scans.json", "w"), indent=2)
print("scans.json now lists " + str(len(dates)) + " scans")
