# The live scan endpoint behind the "Scan a site" tab.
#
# The dashboard can only show sites that were in data/sites.csv when the last
# scan ran. This takes a domain over HTTP, runs the same handshake, and hands
# back the same fields, plus the site's history and how it compares to the rest
# of the corpus.
#
# Thin on purpose: scan.py does the handshake and the CDN, readiness_score.py
# does the stars, cdn_attribution.py does provider-vs-own-effort. What's left
# for this file is taking the request, stopping anyone hammering it, and
# reading the old scans off disk.
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
# the API can never drift from what the nightly scan measures. if scan.py
# learns a new CDN rule tomorrow, this gets it for free.
HERE = os.path.dirname(os.path.abspath(__file__))
DASHBOARD = os.path.dirname(HERE)
sys.path.insert(0, DASHBOARD)

import scan
import readiness_score
import cdn_attribution

DATA_DIR = os.path.join(DASHBOARD, "data")

app = FastAPI(title="PQC Monitor scan API")

# The dashboard is served from GitHub Pages and this runs somewhere else, so the
# browser has to be told it's allowed to call us. This used to be a wildcard.
# A wildcard is not a security hole here (the endpoint is public, GET only, no
# cookies, so there is no session for another page to ride on), but it does
# invite any site on the web to embed our scanner in theirs and spend our rate
# limit. Naming the origins we actually serve costs nothing and stops that.
#
# Note what this is not: CORS is a browser rule. curl ignores it entirely. The
# rate limit below is what protects the service; this only decides which pages a
# browser will hand the answer to.
ALLOWED_ORIGINS = [
    "https://ekindeveci1907.github.io",   # the published dashboard
    "http://localhost:8000",              # python3 -m http.server, for development
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# This endpoint is public and opens a connection to whatever string it's handed,
# which is the shape of request people abuse. So: it has to look like a hostname,
# and it has to resolve to a public address. Without the second rule someone
# could point us at 169.254.169.254 or 10.0.0.x and read things inside whatever
# machine this is deployed on.

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


def tcp_reachable(domain):
    # Called only after a handshake came back empty, to say why. openssl prints
    # nothing useful either way, so ask the simplest question that separates the
    # cases: can we open a TCP connection to port 443 at all?
    #   ok            -> something answered, so TLS itself is what failed
    #   timed out     -> nothing answered in time
    #   refused       -> the host answered, but not on 443
    # returns one of "ok", "timeout", "refused", "unreachable"
    s = socket.socket()
    s.settimeout(8)
    try:
        s.connect((domain, 443))
        return "ok"
    except socket.timeout:
        return "timeout"
    except ConnectionRefusedError:
        return "refused"
    except Exception:
        return "unreachable"
    finally:
        s.close()


def resolves_publicly(domain):
    # returns (ok, reason). every address the name resolves to has to be public -
    # one private answer among several is enough to refuse, because we don't get
    # to choose which one the handshake below ends up using.
    try:
        infos = socket.getaddrinfo(domain, 443, proto=socket.IPPROTO_TCP)
    except Exception:
        return False, "that domain didn't resolve"
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            return False, "that address is on a private network"
    return True, ""


# Rate limit and cache, both plain dictionaries in memory. They empty out when
# the process restarts, which is fine. the cache is a courtesy and the limit is
# to stop someone looping over a wordlist, not to be airtight.
#
# Both used to grow forever. Nothing ever removed a cache entry once its hour was
# up, or an address once its window had passed, so a long-running process on a
# 512 MB instance would keep one row per domain ever scanned and one per address
# ever seen. Neither is large, but "grows without limit" is the wrong shape for
# something anyone can call, so both are swept below.

WINDOW = 300          # seconds
MAX_IN_WINDOW = 12    # scans per address per window
CACHE_TTL = 3600      # a domain's TLS config doesn't change minute to minute
MAX_CACHE = 500       # hard ceiling, in case the sweep can't keep up

recent = {}
cache = {}


def client_address(request):
    # Render terminates TLS in front of us, so request.client.host is Render's
    # proxy, the same value for every visitor. Left alone, the rate limit is one
    # shared bucket: twelve scans per five minutes for the whole internet, and
    # the thirteenth person is refused because of the first twelve.
    #
    # The proxy appends the address it saw to X-Forwarded-For, so the RIGHTMOST
    # entry is the one our proxy observed. Read that end, not the left one: a
    # caller can put anything they like at the front of the header, and picking
    # the leftmost entry would let them invent a new identity per request and
    # walk straight through the limit.
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        parts = forwarded.split(",")
        return parts[len(parts) - 1].strip()
    if request.client:
        return request.client.host
    return "unknown"


def sweep(now):
    # Drop what has expired from both dictionaries. Called once per request,
    # which is often enough: the only thing that adds entries is a request.
    for ip in list(recent.keys()):
        kept = []
        for t in recent[ip]:
            if now - t < WINDOW:
                kept.append(t)
        if kept:
            recent[ip] = kept
        else:
            del recent[ip]

    for domain in list(cache.keys()):
        if now - cache[domain][0] >= CACHE_TTL:
            del cache[domain]

    # A backstop for the case the sweep cannot keep up: drop the oldest entries
    # until the cache is back under the ceiling.
    while len(cache) > MAX_CACHE:
        oldest = None
        for domain in cache:
            if oldest is None or cache[domain][0] < cache[oldest][0]:
                oldest = domain
        del cache[oldest]


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
    #
    # The card stopped drawing this. One live measurement next to a row of old
    # dots was more clutter than it was worth. But it stays in the JSON, because
    # a site's history over time is the one thing this project has that a
    # one-shot scanner doesn't, and anyone calling the API directly wants it.
    # It does mean reading every scan file per uncached request; at eight files
    # that is fine, and if it stops being fine the answer is an index, not
    # dropping the field.
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
    # Canadian site. telling a German bank it's "ahead of 300 Canadian sites"
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
    # A scanned domain we don't already track is a candidate for the next full
    # scan. Nothing reads this automatically, so it never moves the published
    # numbers. Written down twice because the deployed container's disk is wiped
    # on every restart. locally the CSV is the copy that lasts, deployed it's
    # the log line. Domain and measurement only, never who asked.
    print("new domain scanned: " + domain + "  " + tls + "  " + kex + "  " + cdn)

    path = os.path.join(DATA_DIR, "community-scans.csv")
    is_new = not os.path.exists(path)
    f = open(path, "a", newline="")
    w = csv.writer(f)
    if is_new:
        w.writerow(["scanned_at", "site", "tls_version", "key_exchange", "cert", "cdn"])
    w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), domain, tls, kex, cert, cdn])
    f.close()


@app.get("/")
def root():
    # there's no site here, only the two endpoints, but "/" is the first thing
    # anyone opens, so say that rather than leaving them on a bare 404.
    return {
        "service": "PQC Monitor scan API",
        "endpoints": ["/api/health", "/api/scan?domain=example.com"],
        "dashboard": "https://ekindeveci1907.github.io/dashboard/check.html",
    }


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
    # the annotations here are the only ones in the project, and they are not
    # decoration: FastAPI reads them to know that domain is a query parameter and
    # that request is the request object. Take them off and the route breaks.
    ip = client_address(request)
    sweep(time.time())

    d = clean_domain(domain)
    if d == "":
        return JSONResponse({"error": "that doesn't look like a domain name"}, status_code=400)

    # Count the request before looking in the cache. The other way round a
    # cached domain is free to ask for as often as you like, and the limit only
    # ever sees the requests that were going to be cheap anyway.
    if over_limit(ip):
        return JSONResponse(
            {"error": "too many scans from this address, give it a few minutes"},
            status_code=429,
        )

    hit = cache.get(d)
    if hit and time.time() - hit[0] < CACHE_TTL:
        result = dict(hit[1])
        result["cached"] = True
        return result

    ok, why = resolves_publicly(d)
    if not ok:
        return JSONResponse({"error": why}, status_code=400)

    started = time.time()
    tls, kex, cert = scan.get_tls(d)
    if tls == "" or kex == "":
        reach = tcp_reachable(d)
        if reach == "timeout":
            why = "connection timed out: nothing answered on port 443 within 8 seconds"
        elif reach == "refused":
            why = "connection refused: the host answered but nothing is listening on port 443"
        elif reach == "unreachable":
            why = "scan failed: could not open a connection to port 443"
        else:
            why = "TLS handshake failed: the connection opened but no handshake we could read completed"
        return JSONResponse({"error": why}, status_code=502)
    cdn = scan.detect_cdn(d, scan.get_ip(d))
    took = int((time.time() - started) * 1000)

    # score it with the same functions the published dataset uses. Only the three
    # part-scores are wanted here. stars_for() turns them into one star per
    # migration step done. score_site() also hands back the old 0-100 total and
    # its band, but the dashboard stopped showing those when the score became
    # stars, so they stop here rather than going out in the JSON.
    row = {"site": d, "tls_version": tls, "key_exchange": kex, "cert": cert, "cdn": cdn}
    total, band, tls_pts, kex_pts, sig_pts = readiness_score.score_site(row)
    stars = readiness_score.stars_for(tls_pts, kex_pts, sig_pts)
    attribution = cdn_attribution.attribution_for(row)
    source = cdn_attribution.PQC_SOURCE.get(attribution, "")

    # a domain we already track keeps its sector and country; a new one is
    # unknown on both, and saying so is better than inventing a label.
    old = known_row(d)
    sector = ""
    country = ""
    if old:
        sector = old.get("sector", "")
        country = old.get("country", "")

    result = {
        "site": d,
        "tls": tls,
        "kex": kex,
        "cert": cert,
        "cdn": cdn,
        "sector": sector,
        "country": country,
        "source": source,
        "stars": stars,
        "handshake_ms": took,
        "scanned_at": time.strftime("%H:%M UTC", time.gmtime()),
        "in_corpus": old is not None,
        "history": history_for(d),
        "context": context_for(d, stars, sector, country),
        "cached": False,
    }

    cache[d] = (time.time(), result)
    if old is None:
        remember(d, tls, kex, cert, cdn)
    return result
