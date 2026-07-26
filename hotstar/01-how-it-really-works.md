# 01 · How Hotstar Really Works

The machine as it exists today. Before you can design a live-streaming system for 72
million people, you have to see what the real one *actually is* — and the first surprise
is that the hardest problem on the biggest cricket night in history **is not the video.**
This doc fixes the mental model. Everything downstream (requirements, the board, scaling)
hangs off these facts.

---

## 1. The video is static files — the CDN does the multiplication

The thing you call "streaming to 72 million" is not 72 million streams. The live feed is
chopped into **short HLS segments — plain, cacheable files sitting on a CDN.** Every viewer
pulls the *same bytes* off the nearest edge. One person watching or seventy-two million
watching, the origin serves each segment roughly once and the **CDN replicates it** out to
millions. Video is a static-file problem; the CDN is the multiplier. `[V]`

So what does Hotstar's own cloud actually fight? **The API storm that swirls around the
video** — logins, playback-start calls, scorecards, watchlist, ads, social. The player
downloads video from the edge; every *other* tap hits Hotstar's servers. The video is the
easy part. `[V]`

```mermaid
flowchart LR
  ST[Stadium feed]:::client --> ENC[Encoder ladder<br/>vendor UNKNOWN]:::svc
  ENC --> PKG[HLS packager<br/>+ SCTE-35 markers]:::svc
  PKG --> ORG[Origin + shield]:::bank
  ORG -->|"~1 fetch / segment"| CDN[Multi-CDN<br/>Akamai · CloudFront · Jio CDN]:::cache
  CDN -->|"60–80 Tbps"| PL[72.5M players]:::client

  PL -.->|"API storm<br/>1M+ RPS (2019)"| API[Hotstar cloud<br/>auth · playback · ads · social]:::svc
  API --> SHIELD[panic mode guards P0]:::bank

  classDef client fill:#2b211b,stroke:#dfa88f,stroke-width:2px,color:#f0d9cc;
  classDef svc fill:#2b2513,stroke:#d8b45a,stroke-width:2px,color:#f0e4c4;
  classDef cache fill:#1e2b20,stroke:#9fc9a2,stroke-width:2px,color:#d5ecd6;
  classDef bank fill:#1e242e,stroke:#9fbbe0,stroke-width:2px,color:#d5e2f2;
  classDef queue fill:#251f2e,stroke:#c8b6f0,stroke-width:2px,color:#e2d9f2;
```

Solid line = the video path (fanned out by the CDN). Dotted line = the API storm, the part
that can actually take Hotstar down. Keep them separate in your head — the rest of this
series lives on the dotted line.

---

## 2. The record ladder — concurrency, all dated, ICC only

One number defines this system: **concurrent viewers.** Not total views, not MAU —
how many humans are watching *the same second.* The record has only ever been broken on
Indian cricket. `[V]`

| When | Event | Concurrent |
|---|---|---|
| IPL '18 final | first time internet concurrency broke 10M | **10.3M** |
| IPL '19 final | Akamai joint PR | **18.6M** |
| CWC '19 semi (IND–NZ) | **the 4-year record** — the era every engineering talk describes | **25.3M** |
| CWC '23 final (IND–AUS) | Disney+ Hotstar | **59M** |
| T20WC '26 semi (IND–ENG, 5 Mar 2026) | ICC "global streaming record" | **65.2M** |
| **T20WC '26 final (IND–NZ, 8 Mar 2026)** | **ICC-confirmed current world record** | **72.5M** |

Platform scale around it: **~500M MAU** (JioHotstar, Q4 FY26). `[R]` The 25.3M CWC'19 mark
is the one to memorise — nearly every war story in this series ("SSAI at 25.3M", "1M RPS at
25.3M") is anchored to that night. `[V]`

---

## 3. Everyone watches the same bytes — one encode, ~10 ad-cohorts

Here is the counting trick that makes the whole thing possible. There is **one encode
ladder** per match — a single set of quality rungs, produced once. `[V]`

Ads don't fork it into millions of streams either. Hotstar stitches ads **server-side
(SSAI)** and groups viewers into roughly **~10 demographic cohorts**, each a "virtual feed."
Net result: the live event is **"only a few tens of streams"** total — not millions. `[V]`
(Why server-side? See [05 · Scale & resilience](./05-scale-and-resilience-deep-dive.md): ~85% of viewers are on 2G/3G mobile, and
client-side ad insertion would wreck their adaptive bitrate — so the ads are baked in
upstream where the network is fat.) `[V]`

So when someone says "72M streams," the honest correction is: **72M players, tens of source
streams, one encode.** The CDN did the rest.

---

## 4. The delay is engineered — buffer as armour

That lag between the stadium roar next door and the wicket on your phone? **Deliberate.**
Hotstar cut latency from **~55s behind broadcast down to ~15–20s** — and *stopped there on
purpose.* `[V]` The residual buffer is armour: ~85% of viewing is mobile on marginal
networks, and a few extra seconds of buffered segments is what keeps the video from
stalling when a 3G connection hiccups. `[V]`

Lower latency is technically available (LL-HLS/CMAF gets to ~3–5s). Hotstar traded it away
for stability at scale. **Smoothness beats freshness** when your median viewer is on a train
on 3G. Segment length and exact ladder rungs today: **UNKNOWN** — don't quote the old
"10–12 renditions" number as current. `[I]`

---

## 5. The two wars — dated, and getting bigger

The video path and the API path each fight their own war, and the numbers are era-stamped.

- **2019, at 25.3M concurrent:** **1M+ requests/sec** hitting Hotstar's APIs, and **10+ Tbps**
  of video egress across the CDN. `[V]` Hotstar *claimed* this was "~70–75% of India's
  internet that evening" — attribute the % to them, don't state it flat. `[V, their framing]`
- **2026, per live event:** bandwidth revised **up to 60–80 Tbps.** `[V]` No fresh public
  RPS figure exists for 2026 — the 1M+ RPS number stays pinned to **2019.** `[V]`

Two rules live here: **10 Tbps is a 2019 figure, 60–80 Tbps is 2026** — never blur them; and
**there is no published 2026 RPS**, so don't invent one. `[V]`

---

## 6. The metric trap — "82 crore concurrent" is a lie

Somewhere you will see "**82.1 crore / 821M concurrent**" attached to Hotstar. **It is
fabricated** (AI-generated, and it directly contradicts the ICC-confirmed record). The real
ceiling is **72.5M concurrent.** `[V]`

The confusion is baked into the counter itself. The JioHotstar-era on-screen tally counts
**cumulative VIEWS** — every time anyone tuned in, added up — not people watching at once.
The Disney-era counter measured true concurrency. So a "views" number will always dwarf the
"concurrent" number, and press decks quietly swap one for the other. `[V]`

Same trap, 2026 edition: **IPL '26 reported ~551M** — that's **reach** (unique people over a
season), and JioHotstar **disclosed no concurrency figure** for it. `[V]` Reach ≠ concurrency.
When you see a suspiciously huge live number, ask *which* number it is.

> **Interview line:** "The record is 72.5M *concurrent* — ICC-confirmed, on the T20 World
> Cup final, 8 March 2026. Anything in the hundreds of millions is cumulative *views* or
> seasonal *reach*, not people watching the same second. Knowing which metric is on the
> slide is half the interview."

---

## 7. Panic mode — the video must play on

When the storm exceeds even the pre-provisioned fleet ([05 · Scale & resilience](./05-scale-and-resilience-deep-dive.md)), Hotstar flips a
literal switch it calls **"panic mode."** A tier of **P0 services must never go down —
playback, auth, payments.** Everything non-critical is **shed first — recommendations,
personalization, watchlist** — and the servers those features were using get **recycled into
the critical playback path.** `[V]`

There's even a **server→client flag**: clients are told the platform is in panic and *stop
making* non-essential calls, starving the storm from the edge. The doctrine, verbatim from
Hotstar engineering: *"Nobody cares for your surround features if they cannot consume your
primary feature. **The video must play on.**"* `[V]` We build this out in
[03 · High-level design](./03-high-level-design.md).

---

## 8. The twist — they reject autoscaling

Here is the design decision that surprises everyone, and the reason this system is worth
studying. At tsunami scale, Hotstar **refuses reactive autoscaling.** `[V]`

The arithmetic kills it: users join at **0.5–1M per minute**, but a new instance needs ~90s
to provision and the app another ~74s to boot — and at that scale AWS itself starts throwing
*insufficient-capacity* errors. React-to-load loses the race before it starts. `[R detail]`

So instead: **pre-provision and prewarm the whole fleet before the toss**, sized by an ML
traffic prediction (match phase, star players, stakes), then step up along a **pre-computed
concurrency ladder** with a **~2M-concurrent buffer always in hand.** `[V]` And to prove the
plan holds, they built **Project HULK** — an in-house load generator (**108,000 CPU cores,
216 TB RAM, 200 Gbps, 8 regions, simulating 50M users**) that *rehearses the disaster*:
tsunami tests, AZ-kills, CDN failures, push-storm replays, on game days. `[V]` They don't
scale *to* the crowd; they **build the stadium empty and pressure-test it before anyone
arrives.**

We turn this doctrine into requirements next → [02 · Requirements & API](./02-requirements-and-api.md).

---

## What to carry forward

1. **Video = static files on a CDN.** 72M viewers ≠ 72M streams; the CDN multiplies, the
   origin serves each segment ~once. `[V]`
2. **Concurrency is THE metric**, ICC-only: **72.5M** (T20WC'26 final, 8 Mar 2026, world
   record) → 65.2M semi → 59M → 25.3M (the engineering-era anchor). `[V]`
3. **One encode + ~10 SSAI ad-cohorts = "a few tens of streams."** `[V]`
4. **The 15–20s delay is engineered** (down from 55s) — buffer armour for 85% mobile. `[V]`
5. **Two dated wars:** 1M+ RPS + 10+ Tbps at 25.3M (**2019**); **60–80 Tbps per event
   (2026)**. `[V]`
6. **The metric trap:** "82 crore concurrent" is fabricated; 551M IPL'26 is *reach*, not
   concurrency. `[V]`
7. **Panic mode** guards P0 (playback/auth/payments), sheds the rest — *the video must play
   on.* `[V]`
8. **The twist: no autoscaling.** Pre-provision + ML ladder + 2M buffer; **HULK rehearses
   the disaster** at 108k cores. `[V]`

Next: [02 · Requirements & API →](./02-requirements-and-api.md)
