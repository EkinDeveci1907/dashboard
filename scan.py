# The scanner behind the monitor.
# One TLS connection per site with openssl s_client, then read off the protocol
# version, the negotiated key-exchange group (this is where X25519MLKEM768 shows up)
# and the cert signature type. After that work out which CDN/network serves it.
# Writes one CSV per run into data/; aggregate.py turns those into the dashboard json.
import subprocess
import csv
import datetime
import sys
import os
import shutil

# We need a recent openssl. macOS ships LibreSSL, and even plain openssl 3.0 doesn't
# know the ML-KEM groups, so the homebrew openssl@3.5 build is the one that can see
# X25519MLKEM768. Rather than hard-code my own path, look in a few likely places so
# this also runs on someone else's machine. To use your own, set the OPENSSL env var.
# Quick sanity check on whichever it finds:  openssl list -tls-groups
def find_openssl():
    candidates = [
        os.environ.get("OPENSSL"),                     # let the user point at their own
        "/opt/homebrew/opt/openssl@3.5/bin/openssl",   # homebrew, Apple Silicon
        "/usr/local/opt/openssl@3.5/bin/openssl",      # homebrew, Intel Macs
        shutil.which("openssl"),                        # whatever openssl is on the PATH
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return "openssl"   # last resort; if it's too old, scans just won't show PQC

OPENSSL = find_openssl()

# usage: python3 scan.py [sites.csv] [out.csv]. no args = scan the whole list.
IN_FILE = sys.argv[1] if len(sys.argv) > 1 else "data/sites.csv"
OUT_FILE = sys.argv[2] if len(sys.argv) > 2 else "data/scan-" + datetime.date.today().isoformat() + ".csv"

# Three lookup tables for figuring out which CDN / network serves a site. We check
# them in order (headers, then DNS CNAME, then the network owner). Each entry is a
# hint to look for and the clean provider name to report if we find it.
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
    # run a command-line tool (openssl, curl, dig, whois) and hand back whatever it
    # printed. if it errors out or takes too long, just return an empty string.
    try:
        p = subprocess.run(cmd, input="", capture_output=True, text=True, timeout=timeout)
        return p.stdout + p.stderr
    except Exception:
        return ""


def get_tls(site):
    # -brief keeps the output short. we scrape three lines out of it.
    out = run([OPENSSL, "s_client", "-connect", site + ":443", "-servername", site, "-brief"])
    tls = ""
    kex = ""
    cert = ""
    for line in out.splitlines():
        if "Protocol version:" in line:
            tls = line.split(":", 1)[1].strip()
        # on TLS 1.3 the group is printed here (e.g. X25519MLKEM768)
        if "Negotiated TLS1.3 group:" in line:
            kex = line.split(":", 1)[1].strip()
        # on TLS 1.2 there's no "group" line, the temp key line has the curve instead
        if "Peer Temp Key:" in line:
            kex = line.split(":", 1)[1].strip()
        if "Signature type:" in line:
            cert = line.split(":", 1)[1].strip()
    return tls, kex, cert


def get_ip(site):
    # ask DNS for the site's addresses and return the first real IP we see
    for line in run(["dig", "+short", site]).splitlines():
        line = line.strip()
        if line and line[0].isdigit():
            return line
    return ""


def detect_cdn(site, ip):
    # three signals, most reliable first: response headers, then the CNAME chain,
    # then the announcing AS as a last resort. AS alone is fuzzy (can't tell a real
    # CloudFront site from something just parked on AWS) so it only decides ties.
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
    # read the list of sites to scan, and open the output CSV for writing
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

        # do the TLS handshake: protocol version, key-exchange group, cert signature
        tls, kex, cert = get_tls(site)

        # if the site didn't answer, still write the row (blank crypto) so the miss is visible
        if tls == "" or kex == "" or cert == "":
            writer.writerow([site, sector, country, tls, kex, cert, ""])
            out.flush()
            print(str(count) + "/" + str(total) + "  " + site + "  no answer, left blank")
            continue

        # otherwise also work out the CDN, then write the full row
        cdn = detect_cdn(site, get_ip(site))
        writer.writerow([site, sector, country, tls, kex, cert, cdn])
        out.flush()
        print(str(count) + "/" + str(total) + "  " + site + "  " + tls + "  " + cdn)

    out.close()
    print("done, wrote " + OUT_FILE)
    print("now run: python3 aggregate.py")


def scan_one(site):
    # scan a single site and print the result instead of writing a CSV.
    # handy for checking any domain, even one that isn't in data/sites.csv.
    tls, kex, cert = get_tls(site)
    if tls == "" or kex == "" or cert == "":
        print(site + ": no answer (the server did not finish a TLS handshake we could read)")
        return
    cdn = detect_cdn(site, get_ip(site))
    pqc = "   <- post-quantum" if "MLKEM" in kex else ""
    print("site:          " + site)
    print("TLS version:   " + tls)
    print("key exchange:  " + kex + pqc)
    print("certificate:   " + cert)
    print("CDN / network: " + cdn)


def check_tools():
    # print whether the tools a scan needs are installed, and whether openssl is new
    # enough to see the post-quantum group. run this first if a scan looks off:
    #   python3 scan.py --check
    print("Checking the tools a scan needs:")
    print("")

    # openssl: find_openssl() already picked one. say which, then test whether it
    # knows the X25519MLKEM768 group, since that's what proves it can see PQC.
    groups = run([OPENSSL, "list", "-tls-groups"])
    openssl_sees_pqc = "MLKEM" in groups.upper()
    print("  openssl  " + OPENSSL)
    if openssl_sees_pqc:
        print("           knows X25519MLKEM768: yes  (post-quantum will show up)")
    else:
        print("           knows X25519MLKEM768: no   (too old, scans will miss PQC)")

    # curl, dig and whois: the CDN step uses these. just check they're on the PATH.
    missing = []
    for tool in ["curl", "dig", "whois"]:
        if shutil.which(tool):
            print("  " + tool.ljust(8) + " found")
        else:
            print("  " + tool.ljust(8) + " missing")
            missing.append(tool)

    # plain-language summary of what will and won't work
    print("")
    if openssl_sees_pqc and not missing:
        print("All good. A full scan will work, post-quantum detection included.")
    else:
        if not openssl_sees_pqc:
            print("- openssl can't see the PQC group. Install a newer one, then re-check:")
            print("    brew install openssl@3.5      (macOS)")
        if missing:
            print("- missing " + ", ".join(missing) + ": scans still run, but CDN")
            print("  detection will be limited until these are installed.")


if __name__ == "__main__":
    # python3 scan.py --check      check the tools are ready, then stop
    # python3 scan.py example.com  scan just that one domain and print it
    # python3 scan.py              scan the whole list (data/sites.csv)
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        check_tools()
    elif len(sys.argv) > 1 and not sys.argv[1].endswith(".csv"):
        scan_one(sys.argv[1].strip())
    else:
        main()
