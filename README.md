# PQC Deployment Monitor

A small public dashboard that tracks how fast post-quantum cryptography (PQC) is showing up on real websites. Each site gets one TLS handshake, and I record the TLS version, the key exchange group (the one I really care about is the hybrid X25519MLKEM768), the certificate signature type, and the CDN or network that serves it. The main view is Canada, and the map compares Canada to the other countries in the list.

NSERC summer 2026 research project, by Ekin Deveci, supervised by Prof. Samer Lahoud, Dalhousie University.

## What's in here

scan.py is the scanner. For every site in data/sites.csv it does one openssl handshake, works out the CDN, and writes a dated scan file into the data folder.

aggregate.py reads all of those scan files and writes a small summary file for each date, plus a list of the dates. The web page loads those summaries instead of counting hundreds of rows in the browser every time.

merge.py joins two scan files into one. I use it when I only re-scan the sites I added that week and want to fold them into the last full scan.

index.html, style.css and app.js are the dashboard itself: one scrolling page with the summary cards, the charts, the hover world map, and a searchable table. The chart and map libraries load from the internet, so there is nothing to build or install.

The data folder holds sites.csv (the list of sites, with a sector and country for each) and one scan file per date.

## Running it yourself

You need python3 and the usual command line tools: openssl, curl, dig, and whois.

The openssl version matters. macOS ships an old one that does not know the ML-KEM groups, so it cannot see X25519MLKEM768 no matter what the server actually uses. I install a recent openssl with Homebrew (openssl@3.5) and point the OPENSSL line at the top of scan.py at it. To check yours is new enough, run:

    openssl list -tls1_3-kem

X25519MLKEM768 should show up in that list. Then run:

    python3 scan.py
    python3 aggregate.py

The first line scans every site and writes today's scan file. The second rebuilds the summary files the page reads. To see the dashboard, start a small local server and open the address it prints in your browser:

    python3 -m http.server

Opening index.html straight from your files can stop the page from loading its own data, so the little server is the easy way around that.

## Reproducing the numbers

The point of putting the code and the scan data in one public repo is that anyone can check the numbers for themselves. Every statistic on the dashboard is computed by aggregate.py from the scan files in the data folder, and those scan files are committed here. So you do not have to trust the numbers or re-run the scans, you can regenerate them yourself and compare.

The quickest way, on any machine with python3:

    ./run.sh

That rebuilds every summary file from the committed scan data and starts a local server, so you can open http://localhost:8000 and see the same dashboard computed on your own machine from the raw data. If you would rather do it by hand, it is just these two lines:

    python3 aggregate.py
    python3 -m http.server

Running aggregate.py again on the same scan files always produces byte-for-byte identical summary files, so if your numbers ever differ from ours, the data differs and not the method. Collecting a brand new scan (the section above) needs the extra command line tools, but reproducing the published numbers does not, only python3.

## How the CDN detection works

Three clues, checked from most reliable to least.

First, the response headers, since the edge usually names itself (for example cf-ray means Cloudflare). Second, the DNS name the site points to (like cloudfront.net or fastly.net). Third, as a last resort, the network that owns the address, looked up from Team Cymru. The network on its own is fuzzy: it cannot tell a real CloudFront site apart from something just parked on Amazon, so if the network is a company's own, the site is counted as self-hosted.

## The scan file columns

site, sector, country, tls_version, key_exchange, cert, cdn. If a site does not answer, the row is still written with the crypto fields left blank, so I can see the misses. aggregate.py skips those blank rows when it adds up the numbers.

## About the "PQC signatures" number

I track post-quantum certificate signatures too, but the count sits at 0 for now. No public certificate authority issues them yet, so that number going above zero is one of the things this monitor is waiting to catch. Post-quantum key exchange (the X25519MLKEM768 share) is the part that is already rolling out, and that is what the headline percentage tracks.
