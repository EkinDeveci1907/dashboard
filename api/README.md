# The scan service

The dashboard is static, so it can only show sites that were in `data/sites.csv`
when the last scan ran. This is the small service behind the **Scan a site** tab
that handles anything else: you give it a domain, it runs the same handshake
`scan.py` runs, and it hands back the same fields the site table shows, plus the
history and the comparison the corpus makes possible.

It imports `scan.py`, `readiness_score.py` and `cdn_attribution.py` from the
dashboard folder instead of reimplementing any of it, so a live scan and a row in
the published dataset can't disagree.

## Running it locally

You need an openssl that knows the post-quantum group. `scan.py --check` will
tell you whether the one it finds does:

    cd ..
    python3 scan.py --check

Then:

    cd api
    pip install -r requirements.txt
    uvicorn app:app --reload --port 8000

and open `check.html` from the dashboard folder. `check.js` points at
`http://127.0.0.1:8000` by default.

    curl "localhost:8000/api/health"
    curl "localhost:8000/api/scan?domain=cloudflare.com"

## Deploying

    docker build -f api/Dockerfile -t pqc-scan .        # from the dashboard folder
    docker run -p 8000:8000 pqc-scan

It runs on **Render**, from `render.yaml` in the dashboard folder: Render builds
`api/Dockerfile` with the repo root as the context, because the service imports
`scan.py` and friends from the folder above it. The free instance sleeps after
about fifteen minutes of no traffic and takes a moment to wake, which is why the
first scan of the day is slow. `check.js` calls `/api/health` on page load, so
the machine is usually awake by the time anyone has typed a domain in.

because the free plan does not need a credit card. I left the file in, since the
Dockerfile is the same either way, so `fly launch --no-deploy && fly deploy` still
works if the Render side ever goes away.

Whichever host it is, the URL goes in `API` at the top of `check.js`, and it has
to be https or the browser blocks the call from the GitHub Pages site as mixed
content.

## Endpoints

**`GET /api/health`** - whether the service is up, which openssl it found, and
whether that openssl can see `X25519MLKEM768`. The page calls this on load so it
can warn you instead of reporting every site as classical.

**`GET /api/scan?domain=rbc.com`** - the scan. Returns the measurement (`tls`,
`kex`, `cert`, `cdn`, `source`, `stars`, `handshake_ms`), the site's
`history` across every scan on disk, and a `context` block with how many Canadian
sites are ahead of it and how its sector is doing.

Errors come back as `{"error": "..."}` with a real status code: 400 for a domain
that isn't one, 429 over the rate limit, 502 when the site doesn't complete a
handshake we can read.

## Things worth knowing before this is public

- **It only connects to public addresses.** A public endpoint that opens a
  connection to whatever string it is handed is the standard shape of an SSRF
  bug, so `resolves_publicly()` refuses anything resolving to a private, loopback
  or link-local address. Don't remove it.
- **The CDN check follows redirects, so it is bounded.** `detect_cdn()` runs
  `curl -sIL`, and the `-L` earns its place because plenty of sites answer the
  apex with a 301 and the CDN headers are on the hop after it. But the check
  above only ever vetted the name that was typed, and nothing looks at where a
  redirect points, so an unbounded `-L` walks straight past it onto wherever the
  target says to go. It is capped at two hops now, https only, on the first
  request and on the redirects. Re-checking every hop against the public-address
  rule would be better, and is the same piece of work as pinning the address.
- **That check and the handshake look the name up separately.** `resolves_publicly()`
  does its own `getaddrinfo`, then `openssl`, `dig`, `curl` and `whois` each resolve
  the domain again on their own. Somebody running their own DNS with a short TTL
  could answer with a public address for the check and a private one a moment later,
  which is the gap the check is meant to close. Closing it properly means pinning
  the address that was checked and connecting to that one, rather than passing the
  name down to four separate tools. I have left it as it is and written it down
  instead: the endpoint only ever reports back what a TLS handshake returns, so what
  an attacker wins here is knowing whether some internal port speaks TLS. Worth
  fixing, not worth pretending isn't there.
- **Rate limit and cache are in memory.** 12 scans per address per 5 minutes,
  results cached for an hour. Both reset when the process restarts, which is fine
  for what they are for. On more than one machine they would need Redis or
  similar. Three details worth knowing. The limit is counted before the cache is
  read, so a cached domain still costs a request instead of being free to ask for
  forever. Both dictionaries are swept on every request, so an expired cache entry
  or a lapsed address is dropped rather than kept until restart, and the cache has
  a hard ceiling of 500 entries as a backstop. And the address the limit counts is
  read from the right-hand end of `X-Forwarded-For`, not from `request.client.host`
  See below.
- **Behind Render, `request.client.host` is Render.** It is the proxy's address,
  identical for every visitor, so counting it made the rate limit a single shared
  bucket: twelve scans per five minutes for the whole internet. `client_address()`
  reads `X-Forwarded-For` instead and takes the **rightmost** entry, which is the
  address our own proxy observed. The leftmost entry is whatever the caller chose
  to send, so reading that end would let anyone mint a fresh identity per request
  and walk through the limit.
- **New domains are noted, not published.** Anything scanned that isn't already
  in the corpus is appended to `data/community-scans.csv` and printed to the
  log. Nothing reads either automatically, so nobody can push rows into the
  published dataset by scanning a domain.
- **The CSV does not survive on the deployed host.** Render's disk is wiped on
  restart and redeploy, and the free plan has no persistent disk. Locally the
  CSV is the useful copy; deployed, the log line is. Search the service logs
  for `new domain scanned`. If keeping the list properly starts to matter,
  that's a paid disk or a small database, not a bigger file.
- **No IP addresses are stored.** The rate limiter keeps them in memory and
  nothing writes them out.
- **CORS names the origins that actually call this.** The published dashboard on
  GitHub Pages, plus localhost for development. A wildcard would not be a data
  problem (GET only, no cookies, nothing worth taking) but it would let any page
  on the web embed the scanner and spend the rate limit. And CORS is a browser
  rule, not a lock: `curl` ignores it. The rate limit is what protects the
  service.
