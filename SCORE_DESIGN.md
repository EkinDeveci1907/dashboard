# Readiness score — design note

The score turns the measurements the scanner already takes into one number
per site, so sites can be ranked and tracked over time. Nothing here needs a
new scan — it reads the TLS version, key-exchange group and cert signature
that `scan.py` already records.

## How the 100 points split

| Part | Points | Why |
|---|---|---|
| TLS 1.3 present | 20 | You can't negotiate a post-quantum group without TLS 1.3, so this is the floor. |
| (or TLS 1.2 only) | 5 | Safe today, but a dead end for PQC. |
| Post-quantum key exchange (ML-KEM) | 55 | The part that matters *now* — it's what stops harvest-now-decrypt-later. |
| (or a modern classical curve) | 15 | X25519 / P-256: not post-quantum, but one config change away. |
| Post-quantum signature (ML-DSA / SLH-DSA) | 25 | The second half of the migration. Almost nobody has it yet, so it's headroom. |

Three bands: **Quantum-ready (≥75)**, **Modern, not quantum-safe (35–74)**, **Legacy (<35)**.

## Why the tables show stars, not points

Each of the three parts is pass/fail at the depth we measure, so a points
display invites the wrong question ("can I score 18?"). The tables show a
0–3 star rating instead — ★ TLS 1.3, ★★ + PQC key exchange, ★★★ + PQC
signature — with the 0–100 kept underneath for sorting, country averages and
tracking over time. No public CA issues PQC certificates yet, so today's best
possible is two stars; the open third star is the room left to grow.

The partial points (TLS 1.2 = 5, modern curve = 15) are real but they answer
"how far from the next star", not "which star" — the hover tooltip shows the
full breakdown.

## How pqc-monitor computes its 0–100, for comparison

Read their scoring code (`scanner/crypto_assessor.py`). Their number is the
average of many graded checks, most of which are classical TLS hygiene, not
PQC: the TLS version, cipher suite and certificate graded against three
guideline files (NIST SP 800-131A, BSI TR-02102, CCN-STIC-221), a
certificate-chain score (80 minus penalties for incomplete chains, weak
intermediates, missing HSTS/CAA), a cipher-enumeration score (80 minus
penalties for RC4/3DES/export ciphers, no forward secrecy, no TLS 1.3), and
PQC as one more term in the average: 95 if detected, 30 if not. Since their
PQC detection never fires (see the benchmark write-ups), that term is a
constant 30 in practice, and their score differences come entirely from the
hygiene checks. That's why cloudflare.com came out "78" on their scale.

Takeaway: their granularity comes from measuring more things, not from
splitting the PQC facts finer. Ours is deliberately a PQC-migration score
built from the three facts that matter for it, so stars are the honest
display at our measurement depth. A hygiene dimension would be a new probe
(cipher enumeration, chain walk), not a re-weighting — noted as possible
future work.

## Worked examples (Jul 22 scan)

- A normal PQC site today: ★★, 75 = TLS 1.3 (20) + ML-KEM (55) + no PQC sig (0).
- **cloudflare.com / google.com → ★★ (75)**
- **rbc.com → ★ (35)** — TLS 1.3, modern curve, no PQC
- **canada.ca → no stars (20)** — still on TLS 1.2
- Canada: 317 sites at ★★, 292 at ★, 136 at zero; average 48.5/100.

## Open question

Should a site's second star look different when its PQC is entirely the
CDN's doing? The score currently measures the connection a user actually
gets, which is quantum-safe regardless of who enabled it; the `pqc_source`
column carries the via-provider / own-effort distinction separately. An
outlined star for "rented" is one option if the distinction should be
visible in the rating itself.
