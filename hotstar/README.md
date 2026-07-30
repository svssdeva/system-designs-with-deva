# Hotstar — System Design

**Hotstar / JioHotstar** is the machine behind the largest live audiences on earth: on
**8 March 2026**, the T20 World Cup final held **72.5 million people watching the same ball at
the same instant** — an ICC-confirmed world record — on a platform of **~500 million monthly
users**. This folder breaks it down the way a system-design interview does — the map, then the
follow-up round — and hands you enough to build a working toy. It is the third system in the
trilogy: **UPI** guards a rupee, **IRCTC** guards a berth, **Hotstar** guards the pixels.

## The one-paragraph version

The first surprise is that **72 million viewers are not 72 million streams.** Live video is
**static files** — a few-second clip encoded once into a ladder of quality levels, sliced with
ad markers, and copied to a **multi-CDN** edge (Akamai + CloudFront + Jio, steered live by an
in-house engine, **ARGUS**). The **CDN does the multiplication**; Hotstar's own servers fight a
**different war** — the storm of everything *around* the video: logins, home screens,
scorecards, emojis, at **1M+ requests/second** and **60–80 Tbps** per event. Ads are stitched
**server-side** into ~10 demographic cohorts so a 2G phone never stalls. A **50-million-socket**
MQTT pipeline carries live reactions. And the twist: Hotstar **refuses reactive autoscaling** for
a match — a million joins a minute is faster than any autoscaler can boot — so capacity is
**bought, warmed and laddered before the toss**, sized by ML, with a chaos robot (**HULK**,
108k cores) attacking the platform first. When it's still drowning, **panic mode** kills
recommendations and recycles their servers into playback: *the video must play on.*

```mermaid
flowchart LR
  SRC[Stadium feed] --> ENC[Encode + package<br/>one ladder · SCTE-35]
  ENC --> ORI[(Origin + shield)]
  ORI --> CDN[Multi-CDN edge<br/>Akamai·CloudFront·Jio]
  CDN --> U[72.5M players]
  U -.->|API storm| API[Envoy · EKS services]
  API -.->|50M sockets| Q[[Kafka · EMQX/MQTT]]
  class SRC,U client
  class ENC,API svc
  class CDN,ORI cache
  class Q queue
  classDef client fill:#2b211b,stroke:#dfa88f,stroke-width:2px,color:#f0d9cc;
  classDef svc fill:#2b2513,stroke:#d8b45a,stroke-width:2px,color:#f0e4c4;
  classDef cache fill:#1e2b20,stroke:#9fc9a2,stroke-width:2px,color:#d5ecd6;
  classDef queue fill:#251f2e,stroke:#c8b6f0,stroke-width:2px,color:#e2d9f2;
```

## Myth-busts (what most explainers get wrong)

- **72M viewers ≠ 72M streams.** Video is immutable files; the **CDN** fans them out — Hotstar's
  servers barely touch the bytes. `[V]`
- **The delay is engineered, not a bug** — cut from ~55s to **15–20s** behind broadcast; the
  residual buffer is **armour for 85% mobile viewers** on 2G/3G. `[V]`
- **The real war is the API storm**, not the video — **1M+ RPS** at 25.3M concurrent (2019),
  **60–80 Tbps** per live event (2026). `[V]`
- **"82 crore / 821M concurrent" is FALSE** — that counter is **cumulative views**; the
  ICC record is **72.5M concurrent**. (IPL 2026's 551M is *reach*, not concurrency.) `[V]`
- **They reject reactive autoscaling for matches** — a million joins/min beats a ~90s+74s boot;
  capacity is **pre-provisioned on a ladder** before the toss. `[V]`
- **Panic mode is real** — P0 (playback/auth/payments) never drops; recommendations are killed
  and their servers recycled into playback. `[V]`
- **Ads are stitched server-side** (SSAI) into ~10 cohorts so client ad-calls can't wreck ABR;
  in 2026 also hybrid CSAI via DASH on Android. `[V]`
- **The encoder and DRM vendors are genuinely UNKNOWN** — never named; "10k+ instances" is
  folklore. HULK's **108k test cores** is the verified big number. `[V / UNKNOWN]`

## Contents

| # | Doc | Interview stage |
|---|---|---|
| 01 | [How it really works](./01-how-it-really-works.md) | The machine today |
| 02 | [Requirements & API](./02-requirements-and-api.md) | Scope · FR/NFR · BOE · protocol · contract |
| 03 | [High-level design](./03-high-level-design.md) | The 9-node board + a join trace |
| 04 | [Services & interactions](./04-services-and-interactions.md) | 12 services + the sync/async matrix |
| 05 | [Scale & resilience deep-dive](./05-scale-and-resilience-deep-dive.md) | The ladder · panic mode · 50M sockets · SSAI |
| 06 | [Failures & drills](./06-failures-and-drills.md) | Failure drills · chaos (HULK) · observability · trade-offs |
| 07 | [Build it yourself](./07-build-it-yourself.md) | Pick-your-stack · DB-per-store & language matrix · the philosophy |
| — | [API contracts](./api-contracts.md) | Manifest · segment · scorecard · emoji — signed URLs, caching, idempotency `[D]` (+ [Postman](./postman-collection.json)) |

**Video 1 — "Build Your Own Hotstar"** covers docs 01–03 (the machine, the spec, the board).
**Video 2 — "The Follow-Up Round"** covers 04–07 (services & interactions, the scale/resilience
deep-dive, the failure drills, and the build) — the follow-up docs mirror the ten interview
questions one-to-one. *(Video links in the descriptions.)*

Fact labels: `[V]` verified (primary/official) · `[R]` reported (reputable secondary) ·
`[I]` inferred/estimate (spoken as inference) · **UNKNOWN** where nothing is published.
