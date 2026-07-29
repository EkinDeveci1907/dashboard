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

`fly.toml` is set up for fly.io, which is where this is meant to live - the
machine sleeps when nobody is scanning:

    fly launch --no-deploy
    fly deploy

Then change `API` at the top of `check.js` to the deployed URL. It has to be
https, or the browser blocks the call from the GitHub Pages site as mixed
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
- **Rate limit and cache are in memory.** 12 scans per address per 5 minutes,
  results cached for an hour. Both reset when the process restarts, which is fine
  for what they are for. On more than one machine they would need Redis or
  similar.
- **New domains are noted, not published.** Anything scanned that isn't already
  in the corpus is appended to `data/community-scans.csv` and printed to the
  log. Nothing reads either automatically, so nobody can push rows into the
  published dataset by scanning a domain.
- **The CSV does not survive on the deployed host.** Render's disk is wiped on
  restart and redeploy, and the free plan has no persistent disk. Locally the
  CSV is the useful copy; deployed, the log line is - search the service logs
  for `new domain scanned`. If keeping the list properly starts to matter,
  that's a paid disk or a small database, not a bigger file.
- **No IP addresses are stored.** The rate limiter keeps them in memory and
  nothing writes them out.
