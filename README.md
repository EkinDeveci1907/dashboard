# PQC Deployment Monitor

A small public dashboard that tracks how quickly post-quantum cryptography (PQC) is showing up on real websites. It scans a few thousand sites across about twenty countries, with Canada as the main focus, and the map lines Canada up against the rest. For each site it makes one TLS handshake and records four things: the TLS version, the key exchange group (the one I care about is the hybrid X25519MLKEM768), the certificate signature type, and the CDN or network serving the site.

As of now a bit over 40 percent of the Canadian sites I track already negotiate the hybrid key exchange, and almost every time it is a CDN like Cloudflare turning it on at the edge rather than the origin server itself. That shift is what this monitor is here to watch.

NSERC summer 2026 research project, by Ekin Deveci, supervised by Prof. Samer Lahoud, Dalhousie University.

## How a scan works

Each scan is one TLS handshake per site, the same one your browser makes. The command behind it is:

    openssl s_client -connect example.com:443 -servername example.com -brief

Off that I read three lines: the protocol version, the negotiated key-exchange group (on TLS 1.3 it is printed on the `Negotiated TLS1.3 group:` line; on TLS 1.2 there is no group line so I read the curve off `Peer Temp Key:` instead), and the certificate's `Signature type:`. A site counts as post-quantum when the group it negotiates is the hybrid `X25519MLKEM768` — classical X25519 run together with ML-KEM, the key exchange NIST standardised as FIPS 203. If a site does not answer, its row is still written with those fields blank so the miss stays visible. Then the CDN is worked out (see below), and that is the whole scan — no login, no crawling.

## What's in here

scan.py is the scanner. For every site in data/sites.csv it makes one openssl handshake, works out the CDN, and writes a dated scan file into the data folder. You can also hand it a single domain to check just that one site.

aggregate.py reads all of those scan files and writes a small summary file for each date, plus a list of the dates. Doing the counting here is what lets the web page load a ready-made summary instead of adding up thousands of rows in the browser every time.

merge.py joins two scan files into one. I use it when I only re-scan the sites I added that week and want to fold them into the last full scan.

enrich.py adds three more columns to a scan: pqc_source (for a site that does PQC, did it come from its CDN or from the organization itself), readiness_score (a 0-100 quantum-readiness number) and stars (0-3, the rating the page shows - one star per migration step fully done: TLS 1.3, PQC key exchange, PQC signature). All are worked out from columns the scan already has, so it runs on any old scan too without re-scanning. It borrows the actual rules from cdn_attribution.py and readiness_score.py so there is only one definition of each. cdn_attribution.py and readiness_score.py are the deeper analyses behind those columns - the per-country stacked bar, the CDN readiness table, and the score breakdown. SCORE_DESIGN.md explains why the tables show stars while the 0-100 keeps running underneath.

index.html, style.css and app.js are the dashboard itself: one scrolling page with the summary cards, the charts, the hover world map, and a searchable table. The CDN chart is stacked: each provider's bar splits into the sites already negotiating PQC and the ones not, so it also reads as that provider's PQC readiness. Clicking any row in the site table opens a one-sentence "next step" for that site, worked out from what the scan already knows about it and its provider. The chart and map libraries load from a CDN, so there is nothing to build or install.

The data folder holds sites.csv (the list of sites, each with a sector and country) and one scan file per date. There is also sites-ca-toplist.csv, a separate list of the sites Canadians visit most. I used to hand-pick that list; now it is just Semrush's Most Visited Websites in Canada ranking (semrush.com/trending-websites/ca/all, refreshed monthly) in rank order, with the adult and pirate-stream sites dropped. That way, when someone asks what "most visited by Canadians" means, the answer is a source and not my judgement. The list is kept apart from sites.csv on purpose, so those global sites do not get counted twice on the world map.

## Running it yourself

You need python3 and the usual command line tools: openssl, curl, dig, and whois.

The openssl version is the one thing to watch. macOS ships an old one that does not know the ML-KEM groups, so it cannot see X25519MLKEM768 no matter what the server actually offers. The fix is a recent openssl from Homebrew (openssl@3.5). You do not have to edit anything to point at it: the scanner looks for the Homebrew build first, falls back to whatever openssl is on your PATH, and lets you override both with an OPENSSL environment variable.

Before your first scan, let it check the machine for you:

    python3 scan.py --check

That tells you whether openssl is new enough to see the post-quantum group, and whether curl, dig and whois are installed. Once it says everything looks good, run:

    python3 scan.py
    python3 enrich.py
    python3 aggregate.py

The first line scans every site in the list and writes today's scan file. enrich.py adds the pqc_source and readiness_score columns to it. The last line rebuilds the summary files the page reads.

To scan the most-visited-by-Canadians list instead, point the scanner at it and enrich that file by name:

    python3 scan.py data/sites-ca-toplist.csv data/toplist-2026-07-16.csv
    python3 enrich.py data/toplist-2026-07-16.csv

To check a single site without touching the list, just pass the domain:

    python3 scan.py cloudflare.com

That scans only that one site and prints its TLS version, key exchange (marked if it is post-quantum), certificate and CDN, without writing any files. It is handy for spot-checking any website, in the list or not.

To see the dashboard, start a small local server and open the address it prints:

    python3 -m http.server

Opening index.html straight off disk stops the page from loading its own data, so the little server is the easy way around that.

## Reproducing the numbers

Every figure on the dashboard is computed by aggregate.py from the scan files in the data folder, and those files are committed here, so you can regenerate the whole thing yourself and compare.

The quickest way, on any machine with python3:

    ./run.sh

That rebuilds every summary from the committed scan data and starts a local server, so you can open http://localhost:8000 and see the same dashboard, built on your own machine from the raw files. By hand it is just two lines:

    python3 aggregate.py
    python3 -m http.server

Running aggregate.py on the same scan files always gives byte-for-byte identical summaries, so if your numbers ever come out different, it is the data that differs and not the method. Collecting a fresh scan needs the extra tools above, but reproducing the published numbers only needs python3.

## How the CDN detection works

Three clues, checked from most reliable to least.

First the response headers, since the edge usually names itself (cf-ray means Cloudflare, for example). Then the DNS name the site points to, like cloudfront.net or fastly.net. And as a last resort the network that owns the IP address, looked up through Team Cymru. That last signal is fuzzy on its own, because it cannot tell a real CloudFront site from something merely parked on Amazon, so when the owning network is a company's own it gets counted as self-hosted rather than a CDN.

## The scan file columns

site, sector, country, tls_version, key_exchange, cert, cdn. When a site does not answer, the row is still written with the crypto fields left blank so the miss stays visible, and aggregate.py skips those blank rows when it adds up the numbers.

## About the "PQC signatures" number

I track post-quantum certificate signatures too, but for now that count sits at zero. No public certificate authority issues them yet, so watching it climb above zero is one of the things this monitor is waiting for. Post-quantum key exchange, the X25519MLKEM768 share, is the part already rolling out, and that is what the headline percentage follows.

## What one scan does not catch

It is one handshake to one hostname at one moment. A site can look different at its apex than at its www host, and a big site served from many edges can answer differently on another day, so a single row is a snapshot and not a verdict. The CDN guess can miss on unusual setups, since the weakest of its three signals is the owning network. And the sample is a defined list of sites, not the whole Canadian web. I would rather state these limits plainly than pretend one handshake settles everything.
