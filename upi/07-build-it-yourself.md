# 07 · Build It Yourself

The payoff. You've seen the machine; now build a toy of it on one laptop, and be able
to defend every stack choice. This doc has three parts: **pick your stack** (what the
real world runs vs what you'd choose today), a **minimal build order**, and an
**order-of-magnitude cost envelope** — clearly marked as an estimate.

The honest kicker up front: half of "modern" UPI still moves settlement as
**password-protected zip files over SFTP**. Boring tech wins where auditors live.
`[V]` Build accordingly.

---

## What's actually public (and what isn't)

Before the opinion table — the ground truth, so you know which column is fact and
which is judgment.

**On record `[V]`:**

- **NPCI** (Tittu Varghese, via AIM): UPI runs a **100% open-source stack**; **Kafka**
  is named — "every backend system writes directly into a Kafka stream." Stated
  figures: **~240K API req/s across 684 banks; peak ~24K TPS, avg ~17K; internal
  P99 ≈ 100 ms; fraud check ≈ 75 ms.** `[V]` Ecosystem OSS bill (attribute to the
  *ecosystem*, not the switch): Linux, Java, Postgres, Kafka, Kubernetes, OpenJDK
  crypto. NPCI's own GitHub: DRUNIX (Go), FALCON. `[V]`
- **PhonePe** (own blog/GitHub `[V]`): Java/Dropwizard; **HBase = source of truth**
  (WAL + MemStore); **Aerospike** hot path (fraud <20 ms, 3 on-prem DCs active-active);
  **Kafka** (RabbitMQ fallback queue); Elasticsearch; MirrorMaker-2; in-house
  orchestrator Drove.
- **Contrast beats:** **Visa authorizations = IBM z/TPF mainframe** `[V]`; **Brazil Pix
  = Kafka (AMQ Streams) + OpenShift + Ansible** `[V]`; **Juspay** = 1M+ LOC **Haskell**
  switch, **Hyperswitch in Rust** (open source) `[V]`. Exotic languages work in
  payments.

**NOT public — keep these UNKNOWN, never invent:**

- The central switch's exact **language / framework / database** — "Java/Spring" is
  **uncited folklore**, not fact. **UNKNOWN.**
- NPCI's **hardware**. **UNKNOWN.**
- **Google Pay's backend.** **UNKNOWN.**
- The concrete **1-billion-a-day re-architecture**. **UNKNOWN.** (Call it the
  "1-billion-a-day rebuild," never "UPI 3.0" — that term doesn't exist.) `[R]`

> Framing line: *"NPCI won't show you the blueprints — but they've said the whole thing
> is open source, and the one TPAP that opens its garage is PhonePe."*

---

## Pick your stack

The **"You'd pick today"** and **"Why"** columns are **`[I]` — our engineering judgment,
present them as opinion, not fact.**

| Layer | Real world runs | You'd pick today `[I]` | Why / tradeoff `[I]` |
|---|---|---|---|
| **Switch (router)** | Java ecosystem (folklore — see UNKNOWN above); Pix on Kafka+K8s `[V]` | **Go or Java**, over Rust | Stateless L7 routing is I/O-bound. Go/JVM give GC pauses that are tiny next to the 10–15 s timeout budget, a huge hiring pool, and mature TLS/HSM libs. Rust buys P99.9 latency you don't need at ~100 ms P99 — and costs velocity. Haskell/Rust are viable (Juspay proves it) if the team is elite. |
| **Bank ledger** | CBS (COBOL-era cores) + position accounts | **Postgres, double-entry, serializable** | Money = correctness > throughput; one bank's slice (~50M txns/day max) fits a sharded RDBMS. **Not** an eventual-consistency KV. |
| **VPA mapper** | NPCI mapper + PSP stores (PhonePe = Aerospike) `[V]` | **Redis / Aerospike-class KV + Postgres source of truth** | Read-heavy (~10–30K lookups/s), cache-friendly, tolerates ms-stale. |
| **Txn journal / stream** | **Kafka** (NPCI + PhonePe + Pix, all `[V]`) | **Kafka** — this one's unanimous | Append-only journal, replay for recon, fan-out to fraud/analytics. The single most defensible choice in the whole build. |
| **Idempotency / dedup** | central validation + `UT4` recon | **KV with TTL (Redis) + unique-constraint RDBMS backstop** | Two layers, like the real thing: fast-path reject + durable constraint. |
| **Settlement batch** | NTSL files over SFTP (!) `[V]` | boring batch jobs + object storage | Files survive audits; don't stream what settles 12×/day. |
| **Fraud scoring** | in-path, ~75 ms budget `[V]` | in-memory feature store + async model | The hard latency budget forces a cache-first shape. |

The database-per-store logic in detail — relational ledger vs KV mapper vs Kafka journal, and
the SQL-vs-NoSQL reasoning per store — lives in [05 · the data layer](./05-data-layer.md).

### Language — Rust vs Go vs Java vs Node/JS

The switch language is folklore (**UNKNOWN — never say "Java/Spring" as fact**), but the
*shape* of the decision is defensible. **Languages are budgets, not religions:** the
correctness core wants boring hireable JVM/Go; only a genuinely latency-bound service earns
Rust; the edge wants Node. The deciding criterion is in the last column. Picks are **`[I]`**;
the real-world stacks are **`[V]`.**

| Language | Where it fits `[I]` | Deciding criterion |
|---|---|---|
| **Go / Java (JVM)** | the **switch/router, orchestrator, and bank-ledger services** | **P99 ≈ 100 ms `[V]`** with a **10–15 s timeout budget** — GC pauses are tiny against that. Huge Indian hiring pool, mature TLS/HSM/crypto libs. **PhonePe is Java/Dropwizard `[V]`**; NPCI's ecosystem bill names **Java `[V]`.** This is the boring, correct default for the money path. |
| **Rust** | **only** a genuinely latency-bound hot service (e.g. a fraud/edge path fighting the tail) | Rust buys **P99.9** you **don't need at ~100 ms P99** — so spend it only where the tail actually hurts. **Juspay's Hyperswitch is Rust `[V]`** — proof it works, but that's an elite team's choice, not a default. |
| **Node / JS** | the **PSP/TPAP app edge + web & app frontends** | Great for the **REST/BFF edge and I/O fan-out** to the switch. **NOT the switch core or the ledger** — you never put a debit leg on the event loop. |
| **Exotic (Haskell)** | viable for the whole switch **if the team is elite** | **Juspay runs a 1M+ LOC Haskell switch `[V]`** — "exotic languages work in payments." A capability statement, not a recommendation for a normal team. |

**Rejected, and why:** **Rust everywhere = a velocity tax** — you pay the borrow checker on
CRUD that clears P99 with room to spare. **An eventual-consistency KV for the ledger** loses the
`balance >= 0` invariant (see [05](./05-data-layer.md)). Keep each choice a **budget line, not a
religion** — spend the exotic/low-latency option only where the number forces it.

---

## A minimal build order (laptop toy)

Build the *smallest* thing that demonstrates the correctness properties — nothing more.
Four pieces, in order:

**1. The relational ledger with a balance CHECK constraint.** Start here — it's the
whole point. Postgres, one `accounts` table and one `entries` table (double-entry).

```sql
CREATE TABLE accounts (
    id       TEXT PRIMARY KEY,
    balance  BIGINT NOT NULL DEFAULT 0,           -- store paise, never floats
    CHECK (balance >= 0)                          -- overdraw is structurally impossible
);

-- a debit that cannot overdraw, even under a concurrent debit:
UPDATE accounts SET balance = balance - :amt
 WHERE id = :payer AND balance >= :amt;           -- 0 rows affected = declined
```

Prove it: fire two concurrent ₹80 debits at a ₹100 account and watch one get declined
(see [05 · the anomaly](./05-data-layer.md)). That single test teaches more than the
rest of the toy combined.

**2. A KV mapper with TTL.** Redis: `vpa → account/PSP`. Populate on "add beneficiary,"
read on the payment path, give entries a **TTL** and evict on change. This is your cache
+ resolution layer.

**3. An append-only journal keyed by Txn ID.** One table (or a Kafka topic) you only
ever `INSERT` into — every request, every leg outcome, every reversal, tagged with the
**35-char Txn ID**. This is your source of recon truth: you should be able to
reconstruct any payment's story by replaying the journal for its Txn ID.

**4. A small orchestrator owning transaction state.** A single service that: mints the
Txn ID, checks the dedup store (reject a duplicate Txn ID), calls the mapper, drives the
**debit leg then the credit leg**, fires a **reversal** if the credit fails, and writes
every step to the journal. It owns the `SUCCESS | FAILURE | DEEMED` state machine — the
banks just execute legs.

That's the whole toy: **ledger + mapper + journal + orchestrator.** It reproduces
idempotency, the two-leg flow, reversal-on-failure, and no-overdraw — the properties
that *are* UPI. You do **not** need the 12-cycle netted settlement, HSM crypto, or
19 APIs to learn the design.

---

## The honest kicker on settlement

Even in the real system, once authorization is done, interbank settlement is **not** a
glamorous streaming pipeline — it's **net-settlement files (NTSL/DSR) shipped over SFTP**
a dozen times a day, netted and posted to RTGS accounts at the RBI. `[V]` For your toy,
"settlement" can honestly be a nightly batch job that reads the journal, nets each
account pair, and writes a file. That's not a shortcut — **that's what production does.**

---

## Cost envelope — ESTIMATE

**⚠️ Order-of-magnitude only. `[I]` — ESTIMATE, not a quote.** This is *not* what NPCI
spends (their real infra cost is **UNKNOWN**); it's what a *small production-shaped
clone* of this design would cost you per month on commodity cloud, to calibrate
intuition.

| Piece | Shape | Monthly `[I] ESTIMATE` |
|---|---|---|
| Stateless switch fleet | a handful of mid VMs behind an L4 LB | ~$hundreds |
| Postgres ledger (HA, replicated) | primary + sync replica, modest IOPS | ~$hundreds |
| Kafka journal | small managed cluster, few partitions | ~$hundreds |
| Redis mapper/dedup | one small managed instance | ~$tens–hundreds |
| Object storage (journal archive, settlement files) | cheap, grows slowly | ~$tens |
| **Total (toy-to-small-prod)** | — | **~low $1,000s / month `[I] ESTIMATE`** |

The laptop toy above is **~$0** (all of it runs in local containers). The table is only
to show the *shape*: the money is in the **replicated stateful stores** (ledger + Kafka),
not the stateless switch — which is exactly why the real design keeps the center
stateless and cheap to scale. Real numbers at UPI scale are **UNKNOWN** and would be
dominated by on-prem DCs, HSMs, and bank integration, none of which this envelope
models.

---

## What to carry forward

- Public facts are narrow: **Kafka + open-source stack** (NPCI, on record), **HBase +
  Aerospike** (PhonePe). The switch's exact **language/DB/hardware, GPay's backend, and
  the 1B/day rebuild are UNKNOWN** — don't invent them.
- **You'd pick** Go/Java switch, Postgres serializable ledger, Redis/Aerospike mapper,
  **Kafka journal (unanimous)** — the "why" column is opinion `[I]`.
- **Language rule:** **Go/JVM for the switch + ledger** (P99 ≈ 100 ms `[V]` leaves GC pauses
  irrelevant; PhonePe = Java `[V]`), **Rust only for a genuinely tail-bound service**
  (Hyperswitch `[V]`), **Node for the app/BFF edge** — never the ledger. Exotic (Haskell,
  Juspay `[V]`) works only for an elite team. The switch's real language is **UNKNOWN.**
- Build the toy in four pieces: **ledger (CHECK balance>=0) → KV mapper (TTL) →
  append-only journal (Txn ID) → orchestrator (owns the state machine).**
- **Settlement is files over SFTP** — boring tech wins.
- The cost table is an **ESTIMATE** of a small clone, not NPCI's real spend (UNKNOWN).

← Back to [the UPI index](./README.md)
