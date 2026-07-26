# 02 · Requirements & the API Contract

The first ten minutes of the interview. Before any boxes, you scope the problem: what must
it do, how well, how big, and what does the contract on the wire look like. The prompt,
exactly as an interviewer says it: **"Design a live-streaming platform for India — one
cricket ball watched by tens of millions of people at the same instant, with ads and emoji
stacked on top."** The first senior move is to **not start drawing** — and to notice this is
the mirror image of a payments system.

---

## Scope — fence it out loud

Refusing scope is a seniority signal. This system is famous for exactly one thing — holding
72 million concurrent viewers on a single live feed. Every minute spent on content
production or the recommender is a minute stolen from that.

**In scope:**

- **Live sports playback** — adaptive-bitrate (ABR) delivery from 2G to fibre, and joining
  the stream **instantly, mid-match, at any moment.**
- **Server-stitched ads (SSAI)** — the ad break arrives *inside* the video, not as a
  client-side call.
- **The social layer** — live scoreboard + the emoji/reaction fanout (5B emojis in one
  tournament). `[V]`
- **Subscription / entitlement** — the gate that decides whether this device may watch this
  match at all.

**Out of scope (say it):** content production and the encode/transcode farm, **broadcast
rights** and DRM licensing deals, and **VOD recommendations / personalization.** Those are
real systems — they are not *this* problem, and naming that is the point.

> **Interview line:** *"Video is the cheap part — a CDN serves the same bytes to millions.
> The problem you're actually hiring me to solve is the storm of tiny requests around the
> stream, and holding tens of millions of live sockets. So I'll scope out production, rights
> and recs, and spend the whole hour there."*

---

## Functional requirements (five)

1. **Watch live with ABR** — one encode ladder (the old **~10–12 renditions ~200 kbps→5 Mbps**
   is a *reported, pre-2020* figure; the exact ladder today is **UNKNOWN** — hedge it), the
   player climbs and drops with the network; **~85% of viewing is mobile on marginal
   networks.** `[R / UNKNOWN today]`
2. **Join instantly, mid-match, at any moment** — a wicket falls and **0.5–1M+ new viewers
   arrive per minute**; the join must be tens of milliseconds, not seconds. `[V]`
3. **Scoreboard + social layer** — live score push and the emoji reaction stream, delivered
   to every open client. `[V]`
4. **Server-stitched ads** — SCTE-35 markers in the feed, ads stitched **server-side** into
   ~10 demographic cohort feeds (a client-side ad call would wreck ABR on a 2G phone). `[V]`
5. **Subscription / entitlement gate** — auth + "is this device allowed to play this
   match", enforced before a manifest is ever handed out. `[V]`

## Non-functional requirements — ranked (the ranking *is* the personality)

This is the whole doc. The ranking is the **exact inverse** of UPI and IRCTC — and you say
that out loud.

1. **Availability of playback.** The video must play on. This outranks everything, and it is
   a *product* doctrine, not a platitude — "panic mode" literally kills recommendations,
   personalization and watchlist to recycle their servers into the playback path
   ([06](./06-failures-and-drills.md)). `[V]`
2. **Join-time.** A slow join at the exact ball everyone tuned in for *is* churn. 1M joins a
   minute means the join path can hold no per-viewer state on your servers — it must resolve
   against a CDN edge. `[V]`
3. **Freshness (how far behind live).** Deliberately **not** minimised. Latency is
   *engineered up* — from ~55s behind broadcast to ~15–20s — because that residual buffer is
   what protects the 2G/3G majority. Freshness is **traded on purpose** for stability and
   reach. `[V]`
4. **Cost.** Ranked **last**, and even that is a teaching beat: egress *is* the bill
   (~60–80 Tbps per live event), yet against **₹118 cr/match** in broadcast rights the infra
   is a rounding error. `[V] rights · [I] the comparison`

> **Correctness is deliberately RELAXED for the surround features — the exact opposite of a
> payments system.** A double-counted emoji, a scoreboard three seconds stale, a
> watch-position bookmark that resets — none of these are failures worth a millisecond of the
> playback budget. **A bookmark isn't money.** In UPI/IRCTC, inventory/ledger correctness was
> NFR #1 and nothing was allowed to relax it. Here, correctness is the thing we *spend* to buy
> availability. `[D]`

> **Interview line:** *"IRCTC was 25 million writes fighting over one berth — correctness
> first, latency last. Hotstar is 72 million reads of the same bytes — availability first,
> correctness deliberately relaxed on everything that isn't playback, auth or payment. Same
> crowd size, opposite war."* `[V — the canonical contrast]`

Cross-link: the payments-shaped ranking lives in
[`../irctc/02-requirements-and-api.md`](../irctc/02-requirements-and-api.md) — read them
side by side; the inversion is the lesson.

---

## Back-of-envelope — the record is real, the origin is a myth

The numbers all carry a **date** and a **label**, because the credibility is in the honesty
(§10 of the fact spine is binding on this).

```
video road:  72.5M viewers × ~1 Mbps avg ABR  ≈ 70 Tbps        [I estimate — a CDN number]
             ...and NO origin serves it: one encode ladder, CDN edges replicate the bytes
             2019 disclosure:  10+ Tbps  @ 25.3M concurrent      [V — dated]
             2026 disclosure:  60–80 Tbps per live event         [V §11 — dated]
API road:    1M+ requests/sec @ 25.3M concurrent (2019)          [V — dated]
join rate:   0.5–1M+ new viewers per MINUTE at a wicket          [V]
socket road: 50M+ concurrent MQTT connections (emoji/social)     [V]  — steady 50M+ [V §11]
```

**Three roads, sized independently — and only one of them is *your* server's problem:**

```
VIDEO   → the CDN's job.   70 Tbps of segments; your origin serves "tens of streams,"     [V]
                           the edge fans them out to millions. Video is static files.
API     → your cloud's job. 1M+ RPS of tiny JSON — manifests, scorecards, entitlement.    [V]
                            THIS is the fight; the video is the easy part.
SOCKETS → the pubsub tier.  50M live connections; Kafka(500ms)→Spark(2s)→MQTT/EMQX.        [V]
```

**Sanity-check against the real bar.** Concurrency records are **ICC-official only** and are
**concurrency, not cumulative views** (the on-screen "82.1 crore" figure is *views* — the
metric trap is itself a beat): **72.5M** (T20WC '26 final, 8 Mar 2026 — current world
record) · **65.2M** (T20WC '26 semi) · **25.3M** (CWC '19 — the era every engineering talk
describes). `[V]` Quote each with its date; never blend a record with a capacity figure.

> **Interview line:** *"72 million concurrent is a CDN number, not an origin number. If any
> single box in my design has to serve 70 terabits, I've already lost — the whole trick is
> that video is immutable files the edge replicates, and my servers only ever see the storm
> of small requests around it."*

---

## The marquee decision — HLS vs WebRTC (the protocol)

Everything else follows from this one call. State the deciding number: **72.5M concurrent**,
and **per-viewer state at your edge** — HLS holds **0**, WebRTC holds **1**. Zero wins.

| **HLS / LL-HLS — CHOSEN** `[V]` | **WebRTC — REJECTED** `[I from V doctrine]` |
|---|---|
| Video is **immutable segment files** on disk; a manifest points at them. | Video is a **live peer session** — a negotiated, stateful connection. |
| The **CDN replicates the same bytes** to millions; the origin serves only **tens of streams**. | Every viewer is a **stateful session your servers hold**; fanout is **O(viewers)** on *your* fleet. |
| **Latency traded on purpose:** ~55s → ~15–20s behind live — the buffer protects 2G/3G. | Sub-second latency **nobody needs** for a match already 15–20s behind on the TV next to you. |
| **Scales past 72.5M** because the edge is **stateless** — that's the entire reason it works. | **Dies at ~10M+** — you cannot hold tens of millions of live sockets on your own servers. |

**Deciding factor:** state per viewer at the edge. Video-as-files means the CDN is a *shock
absorber* (their word) and the latency you "lose" is the price of surviving a wicket-fall
join storm on marginal networks. LL-HLS/CMAF later buys back a few seconds (~3–5s) **without
giving up the file model** — the trade is tuned, never reversed to WebRTC. `[V/I]`

```mermaid
sequenceDiagram
  autonumber
  participant P as Player (client)
  participant E as Entitlement (auth/subscription)
  participant M as Manifest svc (SSAI)
  participant A as Ad-stitcher (SCTE-35)
  participant C as CDN edge

  P->>E: POST /playback/session  (auth + is this device entitled?)
  E-->>P: 200  signed manifest URL (short-TTL)  — must-compute, per-user
  P->>M: GET master.m3u8  (signed URL)
  M->>A: stitch cohort feed at SCTE-35 markers
  A-->>M: personalized playlist (1 of ~10 cohort "virtual feeds")
  M-->>P: 200  HLS manifest (rendition ladder ~200k→5M)
  P->>C: GET seg09231.ts  (immutable URL)
  C-->>P: 200  segment  —  edge cache HIT >90%, origin untouched
  Note over P,C: join ≈ tens of ms · 1M joins/min · 70 Tbps lives entirely on the edge

  classDef client fill:#2b211b,stroke:#dfa88f,stroke-width:2px,color:#f0d9cc;
  classDef svc fill:#2b2513,stroke:#d8b45a,stroke-width:2px,color:#f0e4c4;
  classDef cache fill:#1e2b20,stroke:#9fc9a2,stroke-width:2px,color:#d5ecd6;
  classDef bank fill:#1e242e,stroke:#9fbbe0,stroke-width:2px,color:#d5e2f2;
  classDef queue fill:#251f2e,stroke:#c8b6f0,stroke-width:2px,color:#e2d9f2;

  class P client;
  class M,A svc;
  class C cache;
  class E bank;
```

Note the shape: the **only per-user, must-compute hop is the session/entitlement call**;
after that the player talks to **cacheable files on the edge** and never touches your origin
again for the duration of the match. That is the join path surviving 1M joins/min.

---

## The API contract

### Pick the style, out loud

- **REST + edge-cacheable JSON for reads.** Manifests, scorecards, entitlement, concurrency
  — dumb, cacheable, CDN-friendly, and served (for the JSON) from a **dedicated CDN domain
  with lighter security** so a scoreboard poll never competes with a payment for capacity.
  `[V §4]`
- **MQTT for realtime.** The emoji/social fanout and scoreboard *push* ride a pub/sub tier
  (EMQX-class), not HTTP polling — **50M+ sockets**, ~250k per node, batched every 500ms.
  This is the one place a persistent connection earns its keep, precisely because it's
  *not* video. `[V]`
- **GraphQL — skipped, and say why:** the client asks a **small, fixed set of questions**
  (get a session, get the manifest, read the score, send an emoji, check entitlement).
  There is **no client-graph** to traverse, and a single POST-`/graphql` endpoint is
  **cache-hostile** — neither URL-cacheable nor cheap to meter — on the exact minute you're
  graded at 1M+ RPS. A resolver fan-out here is a self-inflicted wound. No client-graph
  problem = no GraphQL. `[I/D]`

### The endpoints that matter (full spec: [`api-contracts.md`](./api-contracts.md))

| Call | Shape | Notes |
|---|---|---|
| **POST playback/session** | contentId · device · DRM | **must-compute** (per-user entitlement) → returns a **signed, short-TTL manifest URL**. The only origin hop in the happy path. |
| **GET manifest / segment** | signed URL / immutable URL | manifest = short-cached per cohort; **segment = `immutable`, cached a year** — the 70-Tbps road, edge-served. |
| **GET scorecard** | matchId | **cacheable, seconds-stale OK** — `s-maxage` + `stale-while-revalidate`. Freshness is relaxed by design. |
| **POST reaction (emoji)** | matchId · emoji | **batched, fire-and-forget** → `202`. No idempotency — a dropped or duplicated emoji is *acceptable*. |
| **GET entitlement** | contentId | P0 (panic-mode keeps it up); per-user short-cache. |
| **GET concurrency** | matchId | cacheable; returns **CONCURRENCY, not cumulative views** (the metric-trap guardrail on the wire). |

**Cacheable vs must-compute is the design axis here**, exactly as the platform splits its
match-day APIs. `[V §4]` The full header discipline, the signed-URL pattern, and the
multi-DRM note live in the companion.

---

## DRM — a pattern, not a vendor

Content is locked with the **standard multi-DRM trio** (a Widevine / FairPlay / PlayReady-
class set, one per platform family). This is named **as an industry pattern only** — **the
actual DRM vendor Hotstar uses has never been disclosed and is UNKNOWN.** Likewise the
encoder vendor. Don't state either as fact. `[I pattern · UNKNOWN vendor — §10.3 binding]`

---

## What to carry forward

- **In:** live ABR playback · SSAI ads · scoreboard + emoji social · subscription/entitlement.
  **Out:** content production, broadcast rights/DRM deals, VOD recommendations.
- **NFRs ranked: availability-of-playback > join-time > freshness > cost** — and correctness
  **deliberately relaxed** for every surround feature. The **inverse** of UPI/IRCTC; a
  bookmark isn't money.
- **Envelope:** 72.5M × ~1 Mbps ≈ **70 Tbps of video that no origin serves** (a CDN number);
  **1M joins/min · 1M+ RPS (2019) · 50M+ sockets.** Reality bar = 2019 disclosures + 2026's
  **60–80 Tbps/live event**; concurrency is **ICC-official, dated, and ≠ views.** `[V/§11]`
- **The marquee call: HLS/LL-HLS over WebRTC** — video-as-files means a stateless edge that
  scales past 72.5M; WebRTC's per-viewer session dies at ~10M+. Latency (55→15–20s) is
  **traded on purpose**, not a bug.
- **Contract:** REST + edge-cacheable JSON for reads, **MQTT** for the realtime fanout,
  **skip GraphQL**; signed short-TTL manifest URLs, immutable segment URLs, fire-and-forget
  emoji; **multi-DRM trio as a pattern, vendor UNKNOWN.**

Next: [03 · High-level design →](./03-high-level-design.md) · Full wire spec:
[api-contracts.md →](./api-contracts.md)
