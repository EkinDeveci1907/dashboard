#!/usr/bin/env bash
# scan.sh - do a fresh scan of everything and refresh the dashboard, in one go,
# so there is nothing to paste line by line. Just run:
#
#     ./scan.sh
#
# It needs openssl@3.5, curl, dig and whois (see the README). The main scan is
# the slow part - give it 20 to 40 minutes. If any step fails it stops there
# instead of carrying on with half the data.
#
# The four steps:
#   1. scan the main site list (~2760 sites)
#   2. scan the most-visited-by-Canadians list
#   3. add the pqc_source and readiness_score columns to both scans
#   4. rebuild the summary files the dashboard reads

set -e
cd "$(dirname "$0")"
today=$(date +%Y-%m-%d)

echo "1/4  Scanning the main list (the long one, 20-40 min)..."
python3 scan.py

echo "2/4  Scanning the most-visited-by-Canadians list..."
python3 scan.py data/sites-ca-toplist.csv "data/toplist-$today.csv"

echo "3/4  Adding the pqc_source and readiness_score columns..."
python3 enrich.py
python3 enrich.py "data/toplist-$today.csv"

echo "4/4  Rebuilding the dashboard summary..."
python3 aggregate.py

echo ""
echo "All done. Run  ./run.sh  to open the dashboard in your browser."
