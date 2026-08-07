# PQC Deployment Monitor

A public dashboard tracking how fast post-quantum cryptography is reaching real
websites. It makes one TLS handshake to each of a few thousand domains across
about twenty countries, Canada being the focus, and records four things: the TLS
version, the key-exchange group, the certificate signature type, and the network
or CDN serving the domain.

**Live: https://ekindeveci1907.github.io/dashboard/**

In the 2026-08-05 scan, 333 of the 746 responding Canadian domains negotiate the
hybrid post-quantum key exchange. **325 of those 333 terminate at a CDN edge and
8 on the organisation's own infrastructure.** Adoption in Canada is mostly a
question of which provider a domain sits behind, not of what the organisation
decided. Whether a site asked its provider for post-quantum or the provider
enabled it for every customer at once is not something one handshake can tell
you, so the monitor records where the connection ends and never who deserves the
credit.

NSERC summer 2026 research project, by Ekin Deveci, supervised by Prof. Samer
Lahoud, Faculty of Computer Science, Dalhousie University.

## How a scan works

One TLS handshake per domain, the same one a browser makes:

    openssl s_client -connect example.com:443 -servername example.com -brief

Three lines are read off it: the protocol version; the negotiated key-exchange
group, printed on `Negotiated TLS1.3 group:` under TLS 1.3, or read off
`Peer Temp Key:` under TLS 1.2 where there is no group line; and the
certificate's `Signature type:`.

A domain counts as PQC-enabled when that group is the hybrid `X25519MLKEM768`,
classical X25519 run alongside ML-KEM, the key encapsulation NIST standardised
in FIPS 203. A domain that does not answer still gets a row, with those fields
blank, so the miss stays visible. Then the provider is worked out. No login, no
crawling.

## What's in here

    scan.py             one handshake per domain, plus the provider detection
    enrich.py           adds the pqc_source, readiness_score and stars columns
    aggregate.py        turns the scans into the stats-<date>.json the page reads
    merge.py            folds a small re-scan into a previous full scan
    cdn_attribution.py  provider-vs-own-infrastructure analysis
    readiness_score.py  the 0-100 score and the 0-3 stars behind it
    toplist_report.py   builds the most-visited-by-Canadians page
    index.html app.js style.css    the dashboard
    report-card.js      the per-domain card, shared by two tabs
    check.html check.js the live scan tab
    api/                the scan service behind that tab (see api/README.md)
    data/               the domain lists and one file per scan date

**The dashboard** is one scrolling page: summary cards, charts, a hover world
map, and a searchable table. The CDN chart is stacked, each provider's bar split
into the domains negotiating PQC and the ones not, so it also reads as that
provider's readiness. Clicking a row opens that domain's report card: three
migration steps, a tick or a cross against each, and the measured value beside
it. The card reports the handshake and stops there. It used to suggest a next
step; that was removed because a per-domain recommendation is guesswork more
often than not. The chart and map libraries come from a public CDN, so there is
nothing to build, and if that CDN is unreachable the page still draws the cards,
the sector bars and the table.

**The live tab** contacts whatever domain you type. The handshake happens in
`api/app.py`, which imports `scan.py` rather than reimplementing it, so a live
result and a published row cannot disagree about what they measured. You do not
need to run that service yourself: the page looks for a local copy on port 8000
and falls back to the deployed one. That is why `run.sh` serves the dashboard on
8080, so the two cannot collide.

**The scores.** `readiness_score.py` produces a 0-100 number and 0-3 stars, one
star per migration step fully done. The pages show the stars; the number stays in
the CSVs as a sort key, because each step is pass/fail and a total invites an
argument about the weights.

**The domain lists.** `data/sites.csv` is the institutional list, each row with a
sector and a country. `data/sites-ca-toplist.csv` is separate: Semrush's Most
Visited Websites in Canada ranking, in rank order, adult and pirate-stream
domains dropped. Using a published ranking means "most visited by Canadians" has
a source rather than my judgement behind it. The two lists are kept apart so
global domains are not counted twice on the world map, and where they name the
same domain they agree on its country. Their sector vocabularies differ on
purpose: one sorts institutions by what they are, the other by what people go
there for.

## Running it yourself

You need python3, plus openssl, curl, dig and whois.

OpenSSL is the one to watch. macOS ships a version that does not know the ML-KEM
groups, so it cannot see `X25519MLKEM768` no matter what the server offers, and
every domain comes back classical. Install a recent one (`brew install
openssl@3.5`). Nothing needs editing: the scanner prefers the Homebrew build,
falls back to whatever is on `PATH`, and takes an `OPENSSL` environment variable
over both.

Check the machine first:

    python3 scan.py --check

Then a full run of everything, 20 to 40 minutes:

    ./scan.sh

Or by hand, for the main list:

    python3 scan.py
    python3 enrich.py
    python3 aggregate.py

The most-visited list is the same scanner pointed at the other file:

    python3 scan.py data/sites-ca-toplist.csv data/toplist-2026-08-05.csv
    python3 enrich.py data/toplist-2026-08-05.csv
    python3 toplist_report.py

A single domain, printed and not written anywhere, handy for spot-checks:

    python3 scan.py cloudflare.com

## Reproducing the numbers

Every figure comes from the scan CSVs in `data/`, which are committed, so the
whole dashboard can be rebuilt without scanning anything:

    ./run.sh

That recomputes every summary and serves the site at http://localhost:8080.
Only python3 is needed. Running `aggregate.py` on the same scan files always
gives byte-identical summaries, so if a number comes out different it is the data
that differs, not the method. Opening `index.html` straight off disk will not
work, because the page fetches its own data; that is what the little server is
for.

## How the provider detection works

Three signals, checked in order.

**Response headers** first, since the edge usually names itself. `cf-ray` is
Cloudflare, `x-served-by` is Fastly. **Then the DNS CNAME**, like
`cloudfront.net` or `fastly.net`. **Then the network announcing the IP address**,
looked up through Team Cymru.

That third one is much weaker than the other two and is only consulted when the
first two find nothing. A header and a CNAME are a vendor identifying itself; an
AS name is a routing-registry entry, so it says who owns the address block rather
than who served the request. A domain parked on EC2 and one genuinely on
CloudFront both come back as Amazon. When the announcing network is the
organisation's own, the domain is recorded as self-hosted rather than as a CDN.

[`cdn-sources.md`](cdn-sources.md) is where every keyword in those three tables
came from, with the vendor page behind each one.

## The scan file columns

`site, sector, country, tls_version, key_exchange, cert, cdn`. A domain that did
not answer still gets a row with the crypto fields blank, and `aggregate.py`
leaves those rows out of every percentage while still counting them as attempted.

## About the PQC signatures number

Post-quantum certificate signatures are tracked too, and the count sits at zero.
No public certificate authority issues them yet, so watching it rise above zero
is one of the things this monitor is waiting for. Post-quantum key exchange is
the part already rolling out, and that is what the headline percentage follows.

## Security of the public scan endpoint

The live tab opens a connection to whatever string it is handed, which is the
shape of request people abuse, so what it will and will not do is worth stating.
It accepts only names that look like a hostname and resolve to a public address,
so it cannot be aimed at anything private or internal. It makes one TLS handshake
and nothing else: it never fetches the page, follows a link or logs in. The
provider check follows at most two redirects and only over https. Each address is
limited to a number of scans per five-minute window, results are cached for an
hour, and the addresses behind that limit are held in memory and never written
down. GET only, no cookies, no login, and nothing typed there changes the
published numbers. `api/README.md` has the details, including the gaps.

## What one scan does not catch

One handshake, to one hostname, at one moment. A domain can answer differently at
its apex than at its www host, or from another network, or on another day, so a
row is a snapshot and not a verdict. The provider call can miss on unusual
setups, since the weakest of its three signals is the announcing network. Nothing
here says anything about the origin server behind a CDN, internal services,
stored data, certificate-management processes, or overall cryptographic agility.
And the sample is a defined list of domains, not the Canadian web. Better to
state that plainly than to pretend one handshake settles it.
