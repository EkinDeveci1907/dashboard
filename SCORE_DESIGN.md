# Readiness score — design note

## v2 (Jul 20) — stars on top, after the Jul 16 meeting

The Jul 16 discussion landed on presentation, not substance: the three parts of
the score are each pass/fail at the depth we measure, so showing points invites
the wrong question ("can I score 18?"). His words: *"if it's 0 or 20, then it's
a star."* So:

- **The site tables now show a star rating, 0–3:** one star per migration step
  fully done — ★ TLS 1.3, ★★ + post-quantum key exchange, ★★★ + post-quantum
  certificate signature. Today's best possible is ★★ (no public CA issues PQC
  certs), which makes the open third star the "room to grow" story at a glance.
- **The 0–100 stays underneath** (sorting, country averages, tracking over
  time, and the partial credits: TLS 1.2 = 5, modern classical curve = 15).
  Those partial points are real but they answer "how far from the next star,"
  not "which star" — the hover tooltip shows the full breakdown.

### What pqc-monitor's score actually is (he asked twice — checked Jul 20)

Read `scanner/crypto_assessor.py` in their repo. Their 0–100 is the **average
of many graded checks**, most of which are *classical* TLS hygiene, not PQC:

- per-guideline scores for the TLS version, the negotiated cipher suite, and
  the certificate (RSA/ECDSA key size, hash algorithm) — graded against three
  guideline files (NIST SP 800-131A, BSI TR-02102, CCN-STIC-221);
- a certificate-chain score (starts at 80, minus penalties for incomplete
  chain, weak intermediates, missing HSTS/CAA);
- a cipher-enumeration score (starts at 80, minus penalties for RC4/3DES/
  export/NULL ciphers, no forward secrecy, no TLS 1.3);
- and **PQC as just one more term in the average: 95 if any PQC was detected,
  30 if not.**

So their number is really "general crypto hygiene with a PQC nudge" — that's
why Cloudflare came out 78, not ~100, in their scale. And since their PQC
detection never fires (the benchmark showed they regex the cipher-suite name,
where the PQC group can't appear), the PQC term is a constant 30 for everyone
in practice; the score differences we saw were entirely the hygiene checks.

**Takeaway for ours:** their sub-granularity comes from measuring *more things*
(cipher lists, chains, HSTS), not from splitting the PQC facts finer. Our score
is deliberately a *PQC-migration* score built from the three facts that matter
for it — so at our measurement depth, stars are the honest display. If we ever
want a hygiene dimension too, that's a new probe (cipher enumeration / chain
walk), not a re-weighting — noted as possible future work.

---

# v1 below — the 0–100 (still what runs underneath)

This is the first cut at the "let's build a score" idea from the Jul 9 meeting.
The point is to turn the measurements we already take into one 0–100 number per
site, so sites can be ranked and tracked over time. Nothing here needs a new
scan — it reads the TLS version, key-exchange group, and cert signature that
`scan.py` already records.

## How the 100 points split

| Part | Points | Why |
|---|---|---|
| TLS 1.3 present | 20 | You can't negotiate a post-quantum group without TLS 1.3, so this is the floor. |
| (or TLS 1.2 only) | 5 | Safe today, but a dead end for PQC. |
| Post-quantum key exchange (ML-KEM) | 55 | The part that matters *now* — it's what stops harvest-now-decrypt-later. |
| (or a modern classical curve) | 15 | X25519 / P-256: not post-quantum, but one config change away. |
| Post-quantum signature (ML-DSA / SLH-DSA) | 25 | The second half of the migration. Almost nobody has it yet, so it's headroom. |

Three bands: **Quantum-ready (≥75)**, **Modern, not quantum-safe (35–74)**, **Legacy (<35)**.

## What the numbers look like on the 8 Jul scan (2,714 sites)

- A normal PQC site today scores **75** = TLS 1.3 (20) + ML-KEM (55) + no PQC sig (0). That's "Quantum-ready" with 25 points of room left for when CAs start issuing PQC certs. (Lines up nicely with CyberZero calling Cloudflare "78 / Ready".)
- **cloudflare.com → 75**, **google.com → 75** (quantum-ready)
- **rbc.com → 35** (TLS 1.3, modern curve, no PQC → "Modern, not quantum-safe")
- **canada.ca → 20** (still on TLS 1.2 → "Legacy" — matches what we found back in Week 3)
- Canada average **48.1 / 100**; the 1,066 "quantum-ready" sites are exactly the ML-KEM sites from the attribution work, so the two features agree.

Scores cluster at 5 / 20 / 35 / 75 rather than spreading smoothly — that's honest, not a bug: PQC is close to binary today (you have the hybrid group or you don't). The score will spread out on its own as PQC signatures start to appear and fill in the top 25 points.

## The one thing to decide with the prof

Should a site score a full 75 when its PQC is **entirely the CDN's doing** and the origin never changed? Two options:

1. **Keep it as is** — the score measures *the connection a user gets*, which is genuinely quantum-safe regardless of who enabled it. (This matches the "how secure is the Canadian connection" framing.)
2. **Split the score** — report the raw score plus an "own-effort" score that only counts PQC the organization did itself, using the CDN-vs-org attribution. Then Canada's 48 raw would sit next to a much lower own-effort number, which is the real migration gap.

My lean is to show **both**: the raw score as the headline (it's what the user actually gets), with the own-effort score beside it as the honest view of how much work Canadian organizations have really done. Want your call before I wire it into the dashboard.
