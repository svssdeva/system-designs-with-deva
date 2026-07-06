# System Designs with Deva

**Buildable system-design breakdowns of the systems that actually run a country.**

This repo is the companion to the **"System Design — What If"** series on YouTube
(channel: **beyondcodekarma** / *System Designs with Deva*). Each system gets one folder
and a set of numbered docs, written in the order a real system-design interview walks:
how it works → requirements & API → high-level design → services → data → failures →
build-it-yourself.

The goal is not to admire these systems. It's to **understand them well enough to build a
working toy of each one** — and to defend every choice in an interview.

## Who this is for

- **Engineers prepping for system-design interviews.** The docs are shaped like the rounds
  themselves: scope and non-functional requirements first, then the board, then the
  follow-up grilling (isolation, locking, caching, replication, DR, observability, cost).
- **Anyone who wants to actually build these.** Every system ends with a `07-build-it-yourself.md`
  that gives you a stack, a minimal build order you can run on one laptop, and an
  order-of-magnitude cost envelope.

## How it's organized

One folder per system. Inside each folder, seven numbered docs in interview order:

| Doc | What it covers |
|---|---|
| `01-how-it-really-works.md` | The machine as it exists today — the ground truth. |
| `02-requirements-and-api.md` | Functional + non-functional requirements, back-of-envelope, the API contract. |
| `03-high-level-design.md` | The box diagram, and a trace of one request through it. |
| `04-services-and-interactions.md` | Domain decomposition: the real service catalog + who-calls-whom matrix. |
| `05-data-layer.md` | Database-per-store matrix, ACID/isolation, locking, caching. |
| `06-failures-and-operations.md` | Failure matrix, replication, DR, edge, observability, CDC. |
| `07-build-it-yourself.md` | Pick-your-stack table, minimal build order, cost envelope. |

## Systems

| System | Status | Videos |
|---|---|---|
| **[UPI](./upi/)** — India's instant payment rails | ✅ Ready | Video 1 (how it works + design) · Video 2 (the follow-up round) — *(links in the video descriptions)* |
| **[IRCTC](./irctc/)** — the Tatkal booking storm | 🚧 Coming with its video | — |
| **[Hotstar](./hotstar/)** — 25M+ concurrent live viewers | 🚧 Coming with its video | — |

## How to use this for interview prep

1. **Read `01` and close it. Then try to rebuild `03` yourself** on a blank page before
   reading it. The gap between your board and ours is your study list.
2. **Treat `04`–`06` as the follow-up round.** For each question ("two payments leave the
   same account at once — why don't I lose money?"), answer out loud before reading on.
   Say the rejected alternative and the number that chose between them — that's what senior
   answers sound like.
3. **Build the toy in `07`.** Nothing teaches a design like watching your own ledger
   refuse to go below zero.

## Fact labels

Every non-obvious claim carries a label, and that honesty is the point:

- **`[V]` verified** — traced to a primary or near-primary source (a spec, a circular, an
  on-record statement) that was fetched and read.
- **`[R]` reported** — a credible secondary source; quoted with attribution or "roughly".
- **`[I]` inferred / estimate** — our arithmetic or engineering judgment. Spoken as an
  estimate, never as fact.

Where the honest answer is "not published," we say **UNKNOWN** rather than invent a number.
No peak-TPS records, no fabricated internal latencies, no made-up stack folklore.

## Credit & license

Made by **beyondcodekarma**. Licensed under
**[Creative Commons Attribution 4.0 International (CC BY 4.0)](./LICENSE)** — use it, remix
it, teach from it; just credit *System Designs with Deva / beyondcodekarma*.
