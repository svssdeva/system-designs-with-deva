<div align="center">

# System Designs with Deva

**Buildable, interview-shaped breakdowns of the systems that run a country.**

Companion to the **[System Design — What If](https://youtube.com/@beyondcodekarma)** series — reverse-engineer a real system, then rebuild a working toy of it and defend every choice.

`UPI` · `IRCTC` · `Hotstar` *(soon)* — verified facts, labelled sources, real diagrams.

![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-f54e00) ![Docs](https://img.shields.io/badge/docs-HTML%20site-1b1915) ![Systems](https://img.shields.io/badge/systems-2%20ready%20·%201%20coming-9fbbe0)

</div>

---

The goal here is not to *admire* these systems. It's to understand them well enough to **build a working toy of each one** — and to walk into a system-design interview able to defend every box on the board.

Each system gets one folder and seven numbered docs, written in the order a real interview walks: how it works → requirements & API → high-level design → services → data → failures → build-it-yourself.

> [!NOTE]
> Every non-obvious claim carries a label, and that honesty is the point:
> `[V]` **verified** (a spec/circular/on-record statement, fetched and read) · `[R]` **reported** (credible secondary, hedged) · `[I]` **inferred** (our arithmetic/opinion, an estimate). Where the honest answer is "not published," it says **UNKNOWN** — no invented peak-TPS records, no made-up internal latencies, no stack folklore.

## Systems

| System | What it is | Status |
| :-- | :-- | :-- |
| **[UPI](./upi/)** | India's instant payment rails — ~22B txns/month across 700+ banks | ✅ **Ready** — [7 docs](./upi/) + [build guide](./upi/07-build-it-yourself.md) |
| **[IRCTC](./irctc/)** | The Tatkal booking storm — tens of thousands of tickets/min on fixed inventory | ✅ **Ready** — [7 docs](./irctc/) + [build guide](./irctc/07-build-it-yourself.md) + [API contracts](./irctc/api-contracts.md) |
| **Hotstar** | Tens of millions of concurrent live viewers on one cricket ball | 🚧 Coming with its video |

## Read it two ways

- **On GitHub** — open any folder; the Markdown renders with diagrams inline. Start at **[`upi/`](./upi/)**.
- **As an HTML site** — [`upi/index.html`](./upi/index.html) and [`irctc/index.html`](./irctc/index.html) are self-contained, offline-ready pages rendering each breakdown on the "digital blackboard" from the videos, diagrams and all. Open one locally, or serve it with GitHub Pages (each system folder carries its own `index.html`).

## What's in a system folder

Using UPI as the worked example:

| Doc | Interview stage |
| :-- | :-- |
| [`01-how-it-really-works`](./upi/01-how-it-really-works.md) | The machine as it exists today — the ground truth. |
| [`02-requirements-and-api`](./upi/02-requirements-and-api.md) | Functional + non-functional requirements, back-of-envelope, the API contract. |
| [`03-high-level-design`](./upi/03-high-level-design.md) | The box diagram, and a trace of one request through it. |
| [`04-services-and-interactions`](./upi/04-services-and-interactions.md) | Domain decomposition: the real service catalog + the who-calls-whom matrix. |
| [`05-data-layer`](./upi/05-data-layer.md) | Database-per-store matrix, ACID/isolation, locking, caching. |
| [`06-failures-and-operations`](./upi/06-failures-and-operations.md) | Failure matrix, replication, disaster recovery, edge, observability, CDC. |
| [`07-build-it-yourself`](./upi/07-build-it-yourself.md) | Pick-your-stack table, minimal build order, cost envelope. |

## Use it for interview prep

1. **Read `01`, then close it.** Try to redraw `03` (the board) on a blank page before reading it — the gap between your board and ours is your study list.
2. **Treat `04`–`06` as the follow-up round.** For each question ("two payments leave the same account at once — why don't I lose money?"), answer out loud *before* reading on. Say the rejected alternative and the number that chose between them — that's what senior sounds like.
3. **Build the toy in `07`.**

> [!TIP]
> The fastest way to make a design stick is to build it. `07-build-it-yourself` gets a Postgres ledger, a Redis mapper, and a Kafka journal running on one laptop — and nothing teaches double-entry like watching your own ledger's `CHECK` constraint refuse to go below zero.

## Credit

Made by **beyondcodekarma** · *System Designs with Deva*. Licensed under **[CC BY 4.0](./LICENSE)** — use it, remix it, teach from it; just keep the credit.
