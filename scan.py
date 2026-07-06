import subprocess
import csv
import datetime
import sys

OPENSSL = "/opt/homebrew/opt/openssl@3.5/bin/openssl"
# optional: pass an input file and output file; otherwise scan the whole site list
IN_FILE = sys.argv[1] if len(sys.argv) > 1 else "data/sites.csv"
OUT_FILE = sys.argv[2] if len(sys.argv) > 2 else "data/scan-" + datetime.date.today().isoformat() + ".csv"

HEADER_RULES = [
    ("cf-ray", "", "Cloudflare"),
    ("server", "cloudflare", "Cloudflare"),
    ("x-amz-cf-id", "", "Amazon CloudFront"),
    ("x-amz-cf-pop", "", "Amazon CloudFront"),
    ("via", "cloudfront", "Amazon CloudFront"),
    ("x-served-by", "", "Fastly"),
    ("server", "varnish", "Fastly"),
    ("server", "akamai", "Akamai"),
    ("x-akamai-transformed", "", "Akamai"),
    ("x-azure-ref", "", "Azure Front Door"),
    ("x-msedge-ref", "", "Azure Front Door"),
    ("x-sucuri-id", "", "Sucuri"),
    ("x-iinfo", "", "Imperva (Incapsula)"),
]

CNAME_RULES = [
    (".cloudfront.net", "Amazon CloudFront"),
    (".elb.amazonaws.com", "Amazon (AWS origin)"),
    (".cloudflare.net", "Cloudflare"),
    (".cloudflare.com", "Cloudflare"),
    (".fastly.net", "Fastly"),
    (".fastlylb.net", "Fastly"),
    (".akamaiedge.net", "Akamai"),
    (".akamai.net", "Akamai"),
    (".edgekey.net", "Akamai"),
    (".edgesuite.net", "Akamai"),
    (".akamaized.net", "Akamai"),
    (".azurefd.net", "Azure Front Door"),
    (".azureedge.net", "Azure CDN"),
    (".trafficmanager.net", "Azure Traffic Manager"),
    (".incapdns.net", "Imperva (Incapsula)"),
    (".sucuri.net", "Sucuri"),
    (".b-cdn.net", "BunnyCDN"),
    (".cdn77.org", "CDN77"),
    (".gcdn.co", "Gcore"),
    (".edgio.net", "Edgio"),
    (".llnwd.net", "Edgio"),
    (".azurewebsites.net", "Microsoft (Azure)"),
    (".cloudapp.net", "Microsoft (Azure)"),
]

AS_RULES = [
    ("CLOUDFLARE", "Cloudflare"), ("AKAMAI", "Akamai"), ("FASTLY", "Fastly"),
    ("INCAPSULA", "Imperva (Incapsula)"), ("SUCURI", "Sucuri"), ("CDN77", "CDN77"),
    ("CDNVIDEO", "CDNvideo"), ("EPISERVER", "Optimizely"), ("OPTIMIZELY", "Optimizely"),
    ("DOSARREST", "DOSarrest"), ("LINK11", "Link11"), ("EDGIO", "Edgio"), ("LLNW", "Edgio"),
    ("GCORE", "Gcore"), ("KEYCDN", "KeyCDN"), ("STACKPATH", "StackPath"), ("BUNNY", "BunnyCDN"),
    ("ZEN-ECN", "Zenlayer"), ("ZENLAYER", "Zenlayer"), ("RADWARE", "Radware"), ("F5 ", "F5"),
    ("AMAZON", "Amazon (AWS)"), ("GOOGLE", "Google"), ("MICROSOFT", "Microsoft (Azure)"),
    ("AZURE", "Microsoft (Azure)"), ("ORACLE", "Oracle Cloud"), ("ALIBABA", "Alibaba Cloud"),
    ("TENCENT", "Tencent Cloud"), ("HWCLOUDS", "Huawei Cloud"), ("HUAWEI", "Huawei Cloud"),
    ("SAMSUNGSDS", "Samsung SDS"), ("NHN-", "Naver Cloud"), ("IDCF", "IDC Frontier"),
    ("OVH", "OVH"), ("HETZNER", "Hetzner"), ("LEASEWEB", "Leaseweb"), ("IWEB", "Leaseweb"),
    ("AUTOMATTIC", "Automattic"), ("SQUARESPACE", "Squarespace"), ("WIX", "Wix"), ("WEEBLY", "Weebly"),
    ("GANDI", "Gandi"), ("DHOSTING", "Rackspace"), ("RACKSPACE", "Rackspace"), ("CPANEL", "cPanel hosting"),
    ("ONECOM", "One.com"), ("NETWORK-SOLUTIONS", "Network Solutions"), ("SINGLEHOP", "Internap"),
    ("ZOHO", "Zoho"), ("DROPBOX", "Dropbox"), ("OPENTEXT", "OpenText"), ("SEDO", "Sedo (parking)"),
    ("PROXAD", "Free (hosting)"), ("NUDAY", "Nuday"),
]


def run(cmd, timeout=15):
    try:
        p = subprocess.run(cmd, input="", capture_output=True, text=True, timeout=timeout)
        return p.stdout + p.stderr
    except Exception:
        return ""


def get_tls(site):
    out = run([OPENSSL, "s_client", "-connect", site + ":443", "-servername", site, "-brief"])
    tls = ""
    kex = ""
    cert = ""
    for line in out.splitlines():
        if "Protocol version:" in line:
            tls = line.split(":", 1)[1].strip()
        if "Negotiated TLS1.3 group:" in line:
            kex = line.split(":", 1)[1].strip()
        if "Peer Temp Key:" in line:
            kex = line.split(":", 1)[1].strip()
        if "Signature type:" in line:
            cert = line.split(":", 1)[1].strip()
    return tls, kex, cert


def get_ip(site):
    for line in run(["dig", "+short", site]).splitlines():
        line = line.strip()
        if line and line[0].isdigit():
            return line
    return ""


def detect_cdn(site, ip):
    headers = run(["curl", "-sIL", "https://" + site]).lower()
    for line in headers.splitlines():
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        name = name.strip()
        for rule_name, needle, label in HEADER_RULES:
            if name == rule_name and (needle == "" or needle in value):
                return label

    cname = ""
    for line in run(["dig", "+short", site]).splitlines():
        line = line.strip().lower()
        if line and not line[0].isdigit():
            cname = cname + " " + line
    for needle, label in CNAME_RULES:
        if needle in cname:
            return label

    if ip:
        for line in run(["whois", "-h", "whois.cymru.com", " -v " + ip]).splitlines():
            parts = []
            for piece in line.split("|"):
                parts.append(piece.strip())
            if len(parts) >= 7 and parts[0].isdigit():
                asname = parts[6].upper()
                for word, label in AS_RULES:
                    if word in asname:
                        return label
                return "Self-hosted"

    return "Unknown"


def main():
    sites = list(csv.DictReader(open(IN_FILE)))
    total = len(sites)
    out = open(OUT_FILE, "w", newline="")
    writer = csv.writer(out)
    writer.writerow(["site", "sector", "country", "tls_version", "key_exchange", "cert", "cdn"])

    count = 0
    for row in sites:
        count = count + 1
        site = row["site"].strip()
        sector = row.get("sector", "").strip()
        country = row.get("country", "").strip()

        tls, kex, cert = get_tls(site)

        if tls == "" or kex == "" or cert == "":
            writer.writerow([site, sector, country, tls, kex, cert, ""])
            out.flush()
            print(str(count) + "/" + str(total) + "  " + site + "  no answer, left blank")
            continue

        cdn = detect_cdn(site, get_ip(site))
        writer.writerow([site, sector, country, tls, kex, cert, cdn])
        out.flush()
        print(str(count) + "/" + str(total) + "  " + site + "  " + tls + "  " + cdn)

    out.close()
    print("done, wrote " + OUT_FILE)
    print("now run: python3 aggregate.py")


if __name__ == "__main__":
    main()
