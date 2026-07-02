# PQC Deployment Monitor

A public dashboard that tracks how fast post-quantum cryptography is reaching real
websites. Each site gets one TLS handshake, and we record the TLS version, the key
exchange group (looking for the post-quantum hybrid X25519MLKEM768), the certificate
signature type, and the CDN or network that serves it.

NSERC Summer 2026 research project, E. Deveci, Dalhousie University.

## Files

- scan.py is the scanner. For every site in data/sites.csv it does an openssl
  handshake and figures out the CDN, then writes data/scan-(date).csv.
- aggregate.py reads every scan CSV in data/ and writes one small stats-(date).json
  per scan, plus scans.json with the list of dates. The page loads these instead of
  counting hundreds of CSV rows itself.
- index.html, style.css and app.js are the dashboard. One scrolling page with
  summary cards, charts (Chart.js from a CDN) and a searchable site table.
- data/ holds sites.csv (the site list) and one scan CSV per date.

## How the CDN detection works

Three signals, checked in order. First the HTTP response headers, since the edge
usually names itself (cf-ray, x-amz-cf-id and so on). Then the DNS CNAME chain
(names like .cloudfront.net or .edgekey.net). The announcing AS from Team Cymru is
only a fallback, because the AS alone cannot tell Amazon CloudFront apart from a
plain server that happens to be hosted on AWS. If the AS is just some company's own
network, the site is counted as self-hosted.

## Notes

PQC certificate signatures are tracked too, but the count stays at 0 for now. No
public certificate authority issues them yet, so that number becoming nonzero is
one of the things this monitor is waiting to catch.

Scan CSV columns: site, sector, country, tls_version, key_exchange, cert, cdn,
scanned_at. The scans from June 2026 are from before the scanned_at column was
added, so they have seven columns instead of eight. aggregate.py handles both.
