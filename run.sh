#!/usr/bin/env bash
# run.sh, set up and open the PQC monitor dashboard on your own machine.
#
# What this does: it rebuilds the summary files from the scan data that is
# already committed in this repo, then serves the page so you can open it in a
# browser. Anyone who clones the repo can run this and get the exact same
# numbers we published, which is the whole point of keeping the code and data
# public. No scanning needed just to see and check the numbers.
#
# You only need python3 for this. To collect a fresh scan instead, see the
# README (that part also needs openssl, curl, dig and whois).

set -e
cd "$(dirname "$0")"

echo "Rebuilding the summary files from the committed scan data..."
python3 aggregate.py
python3 toplist_report.py

echo ""
echo "Numbers rebuilt. Starting a local web server."
echo "Open this address in your browser:  http://localhost:8080"
echo "Press Ctrl+C here when you are done."
echo ""
# 8080, not 8000: the scan service uses 8000 when you run it locally, and the
# two cannot share a port. See api/README.md if you want the Scan tab working
# on your own machine as well.
python3 -m http.server 8080
