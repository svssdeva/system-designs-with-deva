# API Contracts — REST · MQTT · GraphQL

A copy-pasteable, interview-grade API reference for the Hotstar live-streaming design in
this folder. Every contract here is a **`[D]` design decision** — the buildable spec you'd
defend on a whiteboard: concrete payloads, the **signed short-TTL manifest URL**, the
**immutable segment URL**, cache headers that mark **cacheable vs must-compute**, the
**fire-and-forget** emoji path, and the **MQTT** realtime spine.

> **Read this once:** Hotstar's / JioHotstar's **real internal playback API, manifest/SSAI
> service contracts, DRM vendor and encoder vendor are not published — UNKNOWN.** This doc is
> **not** a claim about the real API. It is the **REST/JSON edge + MQTT realtime contract you'd
> build** for a live-streaming platform today — faithful to the on-screen decisions from the
> episode: **REST + edge-cacheable JSON for reads, MQTT for the emoji/social fanout, GraphQL
> deliberately skipped; signed short-TTL manifest URLs; immutable, year-cached segments;
> availability-of-playback #1 and correctness deliberately relaxed on the surround features.**
> Fact labels: `[V]` verified · `[R]` reported · `[I]` inferred · `[D]` design ·
> **UNKNOWN** where nothing is published.

Companion doc: [`02-requirements-and-api.md`](./02-requirements-and-api.md) — the scope, the
ranked NFRs, and the HLS-vs-WebRTC decision this contract is built on.

---

## 1. Decision recap — why these three styles `[D]`

| Style | Where | Why |
|---|---|---|
| **REST / JSON** | **Public read edge** (player → CDN → origin) | Manifests, scorecards, entitlement, concurrency are **cacheable JSON** read at **1M+ RPS**. Immutable segments are the **70-Tbps road** — pure edge. Dumb-simple clients, trivial idempotent-by-nature reads. Served (for JSON) from a **dedicated CDN domain with lighter security.** `[V §4]` |
| **MQTT** | **Realtime tier** (emoji/social + scoreboard push) | **50M+ live sockets** (~250k/node, ~4M/ELB, EMQX-class). Push, not poll — the one place a persistent connection earns its keep because it isn't video. Kafka(500ms batch)→Spark(2s)→MQTT. `[V §5]` |
| **GraphQL** | **Deliberately skipped** | The client asks a **small fixed set** of questions (session, manifest, score, emoji, entitlement). **No client-graph**, and a single POST-`/graphql` endpoint is **cache-hostile** — un-cacheable, hard to meter — at 1M+ RPS. Resolver fan-out on the wicket minute = self-inflicted wound. `[I/D]` |

> **Availability-of-playback is the #1 NFR** ([02](./02-requirements-and-api.md)) — the video
> must play on. Every contract below is shaped by that: reads are cacheable and stale-tolerant,
> the only must-compute hop is the per-user session, and the surround features (emoji,
> scoreboard) are **fire-and-forget with correctness deliberately relaxed** — a dropped emoji
> is not a double-sold berth.

---

## 2. REST — the read edge

**Base URL (design):** `https://api.streamlive.example/v1`
JSON in, JSON out. **The design axis is cacheable-vs-must-compute** — every response below is
marked. The only origin round-trip in the happy path is the session/entitlement call; after
that the player talks to **signed manifests and immutable segments on the CDN.**

### 2.0 Common headers

| Header | On | Purpose |
|---|---|---|
| `Authorization: Bearer <token>` | session, entitlement, concurrency | User session — the entitlement/subscription identity. `[V context]` |
| `Cache-Control` | **every read** | The contract states **out loud** whether a response is edge-cacheable and how stale it may be. This is the whole personality. `[D]` |
| `ETag` / `If-None-Match` | scorecard, concurrency | Cheap `304` revalidation for the chatty widgets. `[D]` |
| `X-Request-Id: <uuid>` | all | Per-hop trace id. |
| `X-Metric-Kind` | concurrency only | Echoes `CONCURRENCY` — never cumulative views (metric-trap guardrail on the wire, §10.4). `[V]` |

**Caching cheat-sheet — the map of the whole surface:**

| Endpoint | Cacheable? | Header | Why |
|---|---|---|---|
| `GET …/seg*.ts` (segment) | **YES — immutable** | `public, max-age=31536000, immutable` | content never changes; the 70-Tbps edge road `[V]` |
| `GET …/master.m3u8` (manifest) | short, per-cohort | `public, max-age=2` + **signed short-TTL** | SSAI-personalized per cohort; still a file `[D]` |
| `GET /scorecard/{id}` | **YES — stale OK** | `public, s-maxage=3, stale-while-revalidate=10` | freshness deliberately relaxed `[D]` |
| `GET /concurrency/{id}` | **YES — stale OK** | `public, s-maxage=5, stale-while-revalidate=15` | a big number; seconds-stale is fine `[D]` |
| `POST /playback/session` | **NO — must-compute** | `private, no-store` | per-user entitlement + signed URL `[D]` |
| `GET /entitlement` | per-user short | `private, max-age=30` | P0 auth read; panic-mode keeps it up `[V]` |
| `POST /reactions/{id}` | **N/A — write** | `no-store` | fire-and-forget `202` `[D]` |

### 2.1 `POST /playback/session` — start playback (must-compute, per-user)

The **only origin round-trip** in the happy path. Checks auth + entitlement + concurrency
policy, then mints a **signed, short-TTL manifest URL** and the DRM handshake. Not cacheable.
`[D]`

**Request**

```http
POST /v1/playback/session HTTP/1.1
Host: api.streamlive.example
Authorization: Bearer eyJhbGciOi...
Content-Type: application/json
```

```json
{
  "contentId": "match-t20wc26-final",
  "deviceType": "android-mobile",
  "drmType": "widevine",
  "network": "2g"
}
```

**Response — `200 OK`**

```json
{
  "sessionId": "PBK-2026-7c1e9a44",
  "manifestUrl": "https://cdn.streamlive.example/live/match-t20wc26-final/coh-07/master.m3u8?exp=1772982043&sig=b91f...e2",
  "manifestTtlSeconds": 45,
  "cohort": "coh-07",
  "drm": {
    "scheme": "multi-DRM trio (Widevine / FairPlay / PlayReady-class, one per platform)",
    "vendor": "UNKNOWN — not disclosed; pattern only",
    "licenseUrl": "https://lic.streamlive.example/v1/license"
  },
  "concurrency": { "ok": true, "deviceLimit": 4, "activeDevices": 1 },
  "asOf": "2026-03-08T14:59:58Z"
}
```

```
Cache-Control: private, no-store
```

- **`manifestUrl` is a signed capability**, not a static path — see [2.6](#26-the-signed-url-pattern). Short TTL (~30–60s); the player re-mints on expiry.
- **DRM = pattern only.** The `vendor` field is literally `UNKNOWN` — never name one (§10.3 binding). `[I pattern · UNKNOWN vendor]`
- `concurrency` enforces the per-account device cap — a subscription/entitlement concern, **must-compute**.

**Status codes**

| Code | Meaning |
|---|---|
| `200 OK` | Session minted; go fetch the manifest. |
| `401 / 403` | No session, **or not entitled** (subscription gate — the P0 auth read). |
| `409 Conflict` | Device-concurrency cap exceeded (too many simultaneous streams). |
| `451` | Geo/rights-blocked for this device (rights are **out of scope** to *decide*, in scope to *enforce*). |
| `503 Service Unavailable` | Playback path degraded — retry with client jitter/backoff (panic-mode client kit). `[R]` |

### 2.2 `GET …/master.m3u8` — the manifest (signed, short-cached, SSAI-stitched)

Fetched with the **signed URL** from §2.1. Returns the HLS master playlist — the rendition
ladder — with **SSAI already stitched** server-side at the SCTE-35 markers, for this device's
cohort (one of ~10 "virtual feeds"). Still a *file*, so it's cacheable — but short, and
per-cohort. `[V/D]`

```http
GET /live/match-t20wc26-final/coh-07/master.m3u8?exp=1772982043&sig=b91f...e2 HTTP/1.1
Host: cdn.streamlive.example
```

```
#EXTM3U
#EXT-X-VERSION:7
#EXT-X-STREAM-INF:BANDWIDTH=228000,RESOLUTION=256x144      144p.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=628000,RESOLUTION=512x288      288p.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=1400000,RESOLUTION=854x480     480p.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=3300000,RESOLUTION=1280x720    720p.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080   1080p.m3u8
```

```
Cache-Control: public, max-age=2
```

- Rendition ladder ~200 kbps → ~5 Mbps (~10–12 rungs, **reported** — exact ladder UNKNOWN;
  hedge it). `[R]`
- The media playlists carry **`#EXT-X-DISCONTINUITY`** at ad boundaries — the SSAI seam. Ads
  are stitched server-side precisely so a 2G client's ABR is never broken by a client ad call.
  `[V]`

### 2.3 `GET …/seg*.ts` — the segment (immutable, edge-served — the 70-Tbps road)

The bytes. **Immutable content, cached for a year.** No auth on the segment itself — the
signed *manifest* was the capability, and **DRM is the real content lock.** This is the road
that carries ~60–80 Tbps per live event, and **>90% of it is a CDN cache HIT that never
touches your origin.** `[V]`

```http
GET /live/match-t20wc26-final/720p/seg09231.ts HTTP/1.1
Host: cdn.streamlive.example
```

```
HTTP/1.1 200 OK
Content-Type: video/mp2t
Cache-Control: public, max-age=31536000, immutable
X-Cache: HIT
```

> **Interview line:** *"The segment URL is immutable and cached for a year, so 72 million
> players requesting the same ball hit the edge, not my origin. My origin serves 'tens of
> streams'; the CDN is a shock absorber that fans them out. That single `immutable` header is
> why the 70-terabit number is survivable."* `[V]`

### 2.4 `GET /scorecard/{matchId}` — the score (cacheable, seconds-stale OK)

A chatty widget read by millions. **Freshness is deliberately relaxed** — a scoreboard three
seconds behind is fine, and that lets the edge absorb the read. `s-maxage` caches at the CDN;
`stale-while-revalidate` serves the old value while one origin fetch refreshes it — the
anti-thundering-herd move. `[V §4 / D]`

```http
GET /v1/scorecard/match-t20wc26-final HTTP/1.1
Host: api.streamlive.example
If-None-Match: "sc-8842"
```

**Response — `200 OK`**

```json
{
  "matchId": "match-t20wc26-final",
  "innings": 2,
  "score": { "runs": 168, "wickets": 4, "overs": "17.3" },
  "batting": [
    { "name": "SURYA", "runs": 61, "balls": 34 },
    { "name": "HARDIK", "runs": 22, "balls": 11 }
  ],
  "lastEvent": "FOUR",
  "asOf": "2026-03-08T15:42:11Z",
  "stale": true
}
```

```
Cache-Control: public, s-maxage=3, stale-while-revalidate=10
ETag: "sc-8843"
```

- `stale: true` + `asOf` say **out loud** the number may have moved — the same honesty the
  availability read used in the IRCTC design. `[D]`
- `304 Not Modified` on a matching `If-None-Match` — cheapest possible refresh for a widget
  polled by millions. `[D]`

### 2.5 `POST /reactions/{matchId}` — emoji (batched, fire-and-forget)

The social layer. **Correctness deliberately relaxed:** a dropped or double-counted emoji is
acceptable, so there is **no idempotency key and no durable ack.** The client **batches**
reactions and fires; the edge returns `202` and never blocks playback. Ingest is Go → Kafka
(500ms batches) → Spark (2s windows) → MQTT fanout. `[V §5 / D]`

```http
POST /v1/reactions/match-t20wc26-final HTTP/1.1
Host: api.streamlive.example
Content-Type: application/json
```

```json
{ "batch": [
  { "emoji": "🔥", "ts": 1789012931 },
  { "emoji": "🔥", "ts": 1789012931 },
  { "emoji": "👏", "ts": 1789012932 }
] }
```

**Response — `202 Accepted`**

```json
{ "accepted": 3, "note": "fire-and-forget; not guaranteed, not idempotent, not ordered" }
```

```
Cache-Control: no-store
```

> **Interview line:** *"There is no idempotency key on the emoji path, on purpose. A double
> emoji costs nothing; guaranteeing exactly-once on 5 billion reactions would cost the
> playback budget. Correctness is the thing I spend here to buy availability — the exact
> inverse of the booking API in the IRCTC design."* `[D]`

Delivery back to clients is **not** HTTP — it's the MQTT tier (§3).

### 2.6 The signed-URL pattern

The manifest URL from §2.1 is a **short-lived signed capability**, minted only after the
must-compute entitlement check:

```
https://cdn.streamlive.example/live/{matchId}/{cohort}/master.m3u8?exp=<unix>&sig=<hmac>
                                                                     └── HMAC(secret, path + exp [+ client class])
```

- **`exp`** — short TTL (~30–60s). Expired → `403` **at the edge**, no origin call. The player
  re-mints via `POST /playback/session`.
- **`sig`** — HMAC over the path + expiry (optionally an IP/ASN class), so a leaked link dies
  fast and can't be trivially shared.
- The **segments inside** the manifest are **not** individually signed — they're immutable and
  year-cached (§2.3); the signed *manifest* gates entry, **DRM** gates the content. That split
  is what keeps the 70-Tbps road pure-edge while entitlement stays enforced. `[D]`
- **The DRM license request re-checks the session.** The `licenseUrl` handshake (§2.1) is
  **must-compute and re-validates entitlement** before it releases keys — so a leaked signed
  manifest, even inside its ~45s window, yields **no playable bytes** without a live
  subscription. The signed URL gates the *edge*; the license re-check gates the *content*. `[D]`

### 2.7 `GET /entitlement` & `GET /concurrency/{matchId}`

```http
GET /v1/entitlement?contentId=match-t20wc26-final HTTP/1.1
Authorization: Bearer eyJhbGciOi...
```
```json
{ "entitled": true, "plan": "super", "deviceLimit": 4, "reason": "ACTIVE_SUBSCRIPTION" }
```
```
Cache-Control: private, max-age=30
```
A **P0 read** — panic-mode keeps auth/subscription alive while recs/watchlist die. `[V]`

```http
GET /v1/concurrency/match-t20wc26-final HTTP/1.1
```
```json
{ "matchId": "match-t20wc26-final", "concurrent": 72500000, "metric": "CONCURRENCY",
  "note": "NOT cumulative views — ICC-official concurrency only", "asOf": "2026-03-08T15:42:00Z" }
```
```
Cache-Control: public, s-maxage=5, stale-while-revalidate=15
X-Metric-Kind: CONCURRENCY
```
The `metric` / `X-Metric-Kind` fields put the **metric-trap guardrail on the wire** — the
number is concurrency, never the cumulative-views figure the on-screen counter shows. `[V §10.4]`

---

## 3. MQTT — the realtime spine (50M sockets)

The emoji/social fanout and the scoreboard *push* ride a **pub/sub tier**, not HTTP polling —
this is the one place a persistent connection earns its keep, precisely because it isn't
video. EMQX-class brokers: **~250k connections per node, ~4M per ELB, 8-node clusters
(Mnesia limit) federated by a Go "reverse bridge" to ~50M concurrent.** `[V §5]`

```
CONNECT  wss://rt.streamlive.example/mqtt        (over WebSocket; QoS 0)
SUBSCRIBE  match/{matchId}/reactions             ← aggregated emoji bursts (2s Spark windows)
SUBSCRIBE  match/{matchId}/score                 ← scoreboard deltas pushed on change
```

- **QoS 0, fire-and-forget** — matches the relaxed-correctness contract of the emoji write.
  A missed frame of the emoji rain is invisible; guaranteed delivery to 50M sockets is not
  worth the cost. `[D]`
- **Server-side aggregation** — clients receive **batched counts / bursts** (Kafka 500ms →
  Spark 2s), never one message per emoji. This is what turns 5B raw reactions into a socket
  tier that survives. `[V]`
- **Pushes are capacity events.** A rich push to 51M devices is a self-inflicted DDoS if
  un-managed; engineering **pre-scales the socket tier before marketing fires**, on a 90-second
  reaction budget. `[V/R]`

```mermaid
sequenceDiagram
  autonumber
  participant P as Player (client)
  participant I as Reaction ingest (Go)
  participant K as Kafka (500ms batch)
  participant S as Spark (2s window)
  participant B as MQTT broker (EMQX)

  P->>I: POST /reactions (batched 🔥🔥👏)  — fire-and-forget
  I-->>P: 202 Accepted
  I->>K: append (no ack to client)
  K->>S: 500ms micro-batch
  S->>B: publish match/{id}/reactions (aggregated burst)
  B-->>P: MQTT push (QoS 0) to ~50M subscribed sockets

  classDef client fill:#2b211b,stroke:#dfa88f,stroke-width:2px,color:#f0d9cc;
  classDef svc fill:#2b2513,stroke:#d8b45a,stroke-width:2px,color:#f0e4c4;
  classDef cache fill:#1e2b20,stroke:#9fc9a2,stroke-width:2px,color:#d5ecd6;
  classDef bank fill:#1e242e,stroke:#9fbbe0,stroke-width:2px,color:#d5e2f2;
  classDef queue fill:#251f2e,stroke:#c8b6f0,stroke-width:2px,color:#e2d9f2;

  class P client;
  class I svc;
  class K,S queue;
  class B cache;
```

---

## 4. GraphQL — deliberately skipped `[D]`

We do **not** expose a GraphQL API. Stated plainly because "why not GraphQL" is a real
interview follow-up ([02](./02-requirements-and-api.md)).

**Why we skip it:**

1. **No client-graph problem.** The client asks a small, fixed set — start a session, fetch a
   manifest, read the score, send an emoji, check entitlement. Those are cacheable REST
   resources and one MQTT subscription, not a graph to traverse.
2. **Cache-hostile at 1M+ RPS.** A single POST-`/graphql` endpoint is neither URL-cacheable
   nor `s-maxage`-friendly nor easy to meter — and cacheability *is* the design (the scorecard
   and segment are graded on cache-hit, not compute). GraphQL throws that away.
3. **Resolver fan-out on the wicket minute.** A generic resolver layer invites N+1 fan-out and
   unbounded query cost on the exact minute you're graded at peak concurrency. A self-inflicted
   wound.

> **The honest line:** *"There's no client-graph here — the client asks five fixed questions
> and subscribes to one topic. GraphQL would trade away the cacheability that makes the read
> edge survive 1M requests a second, to solve an over-fetch problem I don't have. So: REST +
> cacheable JSON at the edge, MQTT for realtime, skip GraphQL."*

---

## 5. Async · caching · relaxed-correctness (the repeats)

The patterns that recur across the whole contract:

- **Cacheable-vs-must-compute is the axis.** Segments (`immutable`, 1y), manifests (2s +
  signed), scorecard/concurrency (`s-maxage` + `stale-while-revalidate`) are the **cacheable**
  road; only `POST /playback/session` and `GET /entitlement` are **must-compute** per-user.
  This split *is* the API-storm survival plan. `[V §4]`
- **Signed short-TTL manifests, immutable segments.** Entitlement is enforced once at the
  session hop; the signed manifest is a ~45s capability; the segments inside are immutable and
  edge-served; **DRM** (multi-DRM trio, **vendor UNKNOWN**) is the real content lock. `[D]`
- **Fire-and-forget surround features.** Emoji `POST` → `202`, no idempotency, no durable ack;
  MQTT delivery is QoS 0. **Correctness is deliberately relaxed** on everything that isn't
  playback/auth/payment — a dropped emoji is not a double-sold berth. `[D]`
- **Freshness is traded, not maximised.** Scoreboard seconds-stale, playback 15–20s behind
  live — both are *deliberate* buys for stability and reach, not defects. `[V]`
- **Panic-mode aware.** Under load the server sets a client flag; clients skip non-essential
  calls, add request jitter and backoff, and lean on client-side caches. P0 reads
  (playback/session, entitlement) stay up; recs/watchlist die first. `[V/R]`

---

## What to carry forward

- **REST + edge-cacheable JSON at the read edge** (immutable segments = the 70-Tbps road;
  scorecard/concurrency `s-maxage` + `stale-while-revalidate`), **MQTT** for the 50M-socket
  realtime fanout, **GraphQL skipped** (no client-graph; cache-hostile at 1M+ RPS). `[D]`
- **`POST /playback/session` is the only must-compute hop** → a **signed short-TTL manifest
  URL**; segments are **immutable, year-cached**; DRM = **multi-DRM trio as a pattern, vendor
  UNKNOWN.**
- **Emoji/social is fire-and-forget** — `202`, no idempotency, QoS 0 — because **correctness is
  deliberately relaxed** on the surround features (the inverse of the IRCTC booking contract).
- The **real** Hotstar/JioHotstar internal playback API, SSAI service contracts, DRM and
  encoder vendors are **UNKNOWN / unpublished** — everything above is the `[D]` spec you'd
  build, faithful to the on-screen decisions.

Back to the scope + NFR ranking: [02 · Requirements & the API Contract →](./02-requirements-and-api.md)
