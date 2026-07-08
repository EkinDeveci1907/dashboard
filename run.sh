#!/usr/bin/env bash
# run.sh - set up and open the PQC monitor dashboard on your own machine.
#
# What this does: it rebuilds the summary files from the scan data that is
# already committed in this repo, then serves the page so you can open it in a
# browser. Anyone who clones the repo can run this and get the exact same
# numbers we published - that is the whole point of keeping the code and data
# public. No scanning needed just to see and check the numbers.
#
# You only need python3 for this. To collect a fresh scan instead, see the
# README (that part also needs openssl, curl, dig and whois).

set -e
cd "$(dirname "$0")"

echo "Rebuilding the summary files from the committed scan data..."
python3 aggregate.py

echo ""
echo "Numbers rebuilt. Starting a local web server."
echo "Open this address in your browser:  http://localhost:8000"
echo "Press Ctrl+C here when you are done."
echo ""
python3 -m http.server 8000
