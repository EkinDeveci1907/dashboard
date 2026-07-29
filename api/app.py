# The live scan endpoint behind the "Scan a site" tab.
#
# Everything the dashboard shows so far comes out of a scan we ran earlier, so
# a site nobody thought to put in data/sites.csv simply isn't there. This lets
# anyone hand us a domain and get the same measurement back in a few seconds.
#
# It is deliberately thin. scan.py already knows how to do the handshake and
# work out the CDN, readiness_score.py already knows how to turn that into
# stars, and cdn_attribution.py already knows whether the PQC came from the
# provider or the site itself. This file does the parts those three can't:
# take an HTTP request, keep somebody from hammering it, and put the answer in
# context using the scans we already have on disk.
#
# The context is the whole point. scan.cyberzero.io and zerotrustpqc.com will
# both tell you rbc.com has no post-quantum key exchange. Neither can tell you
# where that puts it against the other 90 sites Canadians actually visit, or
# that it has looked exactly the same in every scan since June. We can.
#
# run it locally:   uvicorn app:app --reload --port 8000
# then:             curl "localhost:8000/api/scan?domain=cloudflare.com"

import csv
import glob
import ipaddress
import os
import re
import socket
import sys
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# the scanner lives one directory up. importing it rather than copying it means
# the API can never drift from what the nightly scan measures - if scan.py
# learns a new CDN rule tomorrow, this gets it for free.
HERE = os.path.dirname(os.path.abspath(__file__))
DASHBOARD = os.path.dirname(HERE)
sys.path.insert(0, DASHBOARD)

import scan
import readiness_score
import cdn_attribution

DATA_DIR = os.path.join(DASHBOARD, "data")

app = FastAPI(title="PQC Monitor scan API")

# the dashboard is served from GitHub Pages and this runs somewhere else, so the
# browser needs to be told it's allowed to call us. GET only, no cookies, so a
# wildcard origin is fine here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------------
# who we're willing to connect to
# ----------------------------------------------------------------------------
#
# This endpoint is public and it makes an outbound connection to whatever
# string it's given, which is exactly the shape of request people abuse. Two
# rules: it has to look like a hostname, and it has to resolve to an address on
# the public internet. Without the second one, someone could point us at
# 169.254.169.254 or 10.0.0.x and use us to read things inside whatever machine
# this is deployed on.

HOSTNAME = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$")


def clean_domain(raw):
    # people paste all sorts of things into a search box. take the hostname out
    # of "https://rbc.com/personal-banking?x=1" and hand back "rbc.com".
    d = (raw or "").strip().lower()
    d = d.replace("https://", "").replace("http://", "")
    d = d.split("/")[0].split("?")[0].split("#")[0]
    if "@" in d:              # someone typed an email address
        return ""
    if ":" in d:              # a port, or an IPv6 literal. neither is a site.
        d = d.split(":")[0]
    if d.endswith("."):
        d = d[:-1]
    if len(d) > 253 or not HOSTNAME.match(d):
        return ""
    return d


def resolves_publicly(domain):
    # returns (ok, reason). we only care that at least one address is public.
    try:
        infos = socket.getaddrinfo(domain, 443, proto=socket.IPPROTO_TCP)
    except Exception:
        return False, "that domain didn't resolve"
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            return False, "that address is on a private network"
    return True, ""


# ----------------------------------------------------------------------------
# rate limit and cache
# ----------------------------------------------------------------------------
#
# Both are plain dictionaries held in memory. If the process restarts they're
# empty again, which is fine - the cache is a courtesy and the limit is there to
# stop someone looping over a wordlist, not to be airtight.

WINDOW = 300          # seconds
MAX_IN_WINDOW = 12    # scans per IP per window
CACHE_TTL = 3600      # a site's TLS config doesn't change minute to minute

recent = {}
cache = {}


def over_limit(ip):
    now = time.time()
    hits = recent.get(ip, [])
    kept = []
    for t in hits:
        if now - t < WINDOW:
            kept.append(t)
    recent[ip] = kept
    if len(kept) >= MAX_IN_WINDOW:
        return True
    kept.append(now)
    return False


# ----------------------------------------------------------------------------
# the scans we already have, for context
# ----------------------------------------------------------------------------

def latest_enriched():
    # the newest data/scan-YYYY-MM-DD-enriched.csv, as (date, rows). enrich.py
    # writes these, so the site table on the dashboard and the numbers here come
    # from exactly the same file.
    files = sorted(glob.glob(os.path.join(DATA_DIR, "scan-*-enriched.csv")))
    if not files:
        return "", []
    newest = files[-1]
    date = os.path.basename(newest).replace("scan-", "").replace("-enriched.csv", "")
    return date, list(csv.DictReader(open(newest)))


def history_for(domain):
    # every scan we've run, in date order, with what this domain's key exchange
    # looked like at the time. Sites we never scanned come back empty, which is
    # the normal case for a domain somebody just typed in.
    out = []
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "scan-*.csv"))):
        name = os.path.basename(path)
        if name.endswith("-enriched.csv"):
            continue          # same scan, don't count it twice
        date = name.replace("scan-", "").replace(".csv", "")
        for row in csv.DictReader(open(path)):
            if row.get("site", "").strip().lower() != domain:
                continue
            kex = row.get("key_exchange", "")
            out.append({"date": date, "pqc": "MLKEM" in kex.upper(), "kex": kex})
            break
    return out


def context_for(domain, stars, sector, country):
    # where this site sits against the corpus.
    #
    # Two deliberate limits. The comparison population is Canadian sites only,
    # because that's what the monitor is about, so it's only quoted for a
    # Canadian site - telling a German bank it's "ahead of 300 Canadian sites"
    # would be a number, not a fact. And sites are compared by how many stars
    # they have rather than being given a rank: hundreds of sites share the same
    # two stars, so "ranked 41st" would be an ordering we invented.
    date, rows = latest_enriched()
    canada = []
    for r in rows:
        if r.get("country", "") == "CANADA" and r.get("tls_version", "").strip() != "":
            canada.append(r)

    ctx = {"scan_date": date, "canada_total": len(canada)}
    if len(canada) == 0:
        return ctx

    pqc = 0
    for r in canada:
        if "MLKEM" in r.get("key_exchange", "").upper():
            pqc = pqc + 1
    ctx["canada_pqc_pct"] = round(100 * pqc / len(canada))

    if country != "CANADA":
        return ctx

    ahead = 0
    same = 0
    for r in canada:
        s = int(r.get("stars", 0) or 0)
        if s > stars:
            ahead = ahead + 1
        elif s == stars:
            same = same + 1
    ctx["ahead"] = ahead
    ctx["same"] = same

    # and against the sites doing the same job. below five it's not a peer group,
    # it's a coincidence, so don't quote it.
    peers = []
    for r in canada:
        if r.get("sector", "") == sector:
            peers.append(r)
    if len(peers) >= 5:
        peer_pqc = 0
        for r in peers:
            if "MLKEM" in r.get("key_exchange", "").upper():
                peer_pqc = peer_pqc + 1
        ctx["sector"] = sector
        ctx["sector_total"] = len(peers)
        ctx["sector_pqc"] = peer_pqc

    return ctx


def known_row(domain):
    # if the domain is already in the corpus, hand back its row so we can reuse
    # the sector and country we already worked out instead of guessing.
    date, rows = latest_enriched()
    for r in rows:
        if r.get("site", "").strip().lower() == domain:
            return r
    return None


def remember(domain, tls, kex, cert, cdn):
    # anything somebody scans that we've never covered gets written down. It
    # isn't merged into the published dataset automatically - it's a queue to
    # look at before the next full scan - but it means the site list grows from
    # people using the thing rather than only from me adding rows by hand.
    path = os.path.join(DATA_DIR, "community-scans.csv")
    is_new = not os.path.exists(path)
    f = open(path, "a", newline="")
    w = csv.writer(f)
    if is_new:
        w.writerow(["scanned_at", "site", "tls_version", "key_exchange", "cert", "cdn"])
    w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), domain, tls, kex, cert, cdn])
    f.close()


# ----------------------------------------------------------------------------
# the endpoint
# ----------------------------------------------------------------------------

@app.get("/api/health")
def health():
    # the dashboard calls this on page load so it can say "scanner offline"
    # instead of leaving a spinner turning forever. Also worth reporting whether
    # openssl is new enough, because on an old one every site comes back
    # classical and the numbers look wrong rather than broken.
    groups = scan.run([scan.OPENSSL, "list", "-tls-groups"])
    return {
        "ok": True,
        "openssl": scan.OPENSSL,
        "sees_mlkem": "MLKEM" in groups.upper(),
    }


@app.get("/api/scan")
def scan_domain(request: Request, domain: str = ""):
    ip = request.client.host if request.client else "unknown"

    d = clean_domain(domain)
    if d == "":
        return JSONResponse({"error": "that doesn't look like a domain name"}, status_code=400)

    hit = cache.get(d)
    if hit and time.time() - hit[0] < CACHE_TTL:
        result = dict(hit[1])
        result["cached"] = True
        return result

    if over_limit(ip):
        return JSONResponse(
            {"error": "too many scans from this address, give it a few minutes"},
            status_code=429,
        )

    ok, why = resolves_publicly(d)
    if not ok:
        return JSONResponse({"error": why}, status_code=400)

    started = time.time()
    tls, kex, cert = scan.get_tls(d)
    if tls == "" or kex == "":
        return JSONResponse(
            {"error": "no answer - the server didn't finish a TLS handshake we could read"},
            status_code=502,
        )
    cdn = scan.detect_cdn(d, scan.get_ip(d))
    took = int((time.time() - started) * 1000)

    # score it with the same functions the published dataset uses
    row = {"site": d, "tls_version": tls, "key_exchange": kex, "cert": cert, "cdn": cdn}
    total, band, tls_pts, kex_pts, sig_pts = readiness_score.score_site(row)
    stars = readiness_score.stars_for(tls_pts, kex_pts, sig_pts)
    attribution = cdn_attribution.attribution_for(row)
    source = cdn_attribution.PQC_SOURCE.get(attribution, "")

    # a domain we already track keeps its sector and country; a new one is
    # unknown on both, and saying so is better than inventing a label.
    old = known_row(d)
    sector = old.get("sector", "") if old else ""
    country = old.get("country", "") if old else ""

    result = {
        "site": d,
        "tls": tls,
        "kex": kex,
        "cert": cert,
        "cdn": cdn,
        "sector": sector,
        "country": country,
        "source": source,
        "score": total,
        "band": band,
        "stars": stars,
        "handshake_ms": took,
        "in_corpus": old is not None,
        "history": history_for(d),
        "context": context_for(d, stars, sector, country),
        "cached": False,
    }

    cache[d] = (time.time(), result)
    if old is None:
        remember(d, tls, kex, cert, cdn)
    return result
