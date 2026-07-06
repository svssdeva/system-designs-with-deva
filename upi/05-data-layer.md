# 05 · The Data Layer

The follow-up round where the interviewer stops nodding and starts probing:
*which database, which isolation level, which lock, what do you cache?* This is where
UPI's "correctness over everything" turns into concrete storage choices.

The core move: **there is no one database.** Each store has a different job, and the
right engine for a ledger is the wrong engine for a mapper.

---

## Database-per-store

| Store | Job | Right shape | Why |
|---|---|---|---|
| **Ledger** (bank core) | hold balances, move money | **Relational, ACID, with constraints** | Money = correctness > throughput. A `balance >= 0` CHECK and double-entry rows are non-negotiable. One bank's slice (≤ ~50M txns/day) fits a sharded RDBMS. `[I]` |
| **VPA / mobile mapper** | resolve address → PSP/account | **Key-value** (Redis/Aerospike-class) + a small RDBMS source of truth | Read-heavy (~10–30K lookups/s `[I]`), cache-friendly, tolerates ms-stale. |
| **Dedup / idempotency** | reject duplicate txns | **Two layers:** KV with TTL (fast reject) + a unique constraint in the RDBMS (durable backstop) | Mirrors the real thing: fast-path reject at the edge, durable guarantee at the ledger. `[I]` |
| **Fraud features** | in-path risk score | **In-memory feature store** | Hard ~75 ms budget `[V]` forces cache-first; no disk in the hot path. |
| **Journal / stream** | append-only event log | **Kafka** | Replay for recon, fan-out to fraud + analytics. Unanimous choice — NPCI, PhonePe and Brazil's Pix all use it. `[V]` |
| **Search / analytics** | recon, dashboards, investigations | **Downstream** search/OLAP (e.g. Elasticsearch/warehouse), fed by CDC off the log | Query-heavy, not on the money path; never the source of truth. |

**Where a document store does *not* fit:** the money ledger. A schemaless document DB
gives you flexible shape and eventual consistency — the opposite of what a balance
needs. You cannot express "this account's balance may never go below zero, atomically,
under concurrent debits" as cleanly or safely in a document model as with a relational
CHECK constraint and row locks. Documents are fine for *append-only records* (a receipt,
an event) — but the authoritative balance belongs in a constrained relational table.

> **`[V]` counter-example — read this before you over-generalize:** **PhonePe uses
> HBase (a wide-column store) as its source of truth**, on a WAL + MemStore append path,
> with **Aerospike** on the fraud hot path (<20 ms), Kafka (RabbitMQ as fallback queue),
> Elasticsearch, and MirrorMaker-2 replication, across 3 on-prem data centres
> active-active. `[V]` So "always relational for money" is a *default*, not a law — a
> team that engineers its own correctness (append-only writes, careful compaction,
> application-level invariants) can make a wide-column store the book of record. The
> point isn't "relational always wins"; it's **know what invariant you're buying and how
> your store enforces it.**

---

## ACID vs isolation: the anomaly that loses money

Here is the canonical UPI correctness question. **Two debits leave the same account at
the same instant. Why don't I lose money?**

Account has **₹100**. Two payments of **₹80** each arrive concurrently.

### Under READ COMMITTED (the anomaly)

```
Txn A: read balance = 100  →  100 >= 80 OK  →  write 100 - 80 = 20
Txn B: read balance = 100  →  100 >= 80 OK  →  write 100 - 80 = 20
```

Both read the *pre-debit* balance of 100, both pass the check, both write 20. The
account paid out **₹160 it did not have**. Read-committed lets each transaction see a
consistent snapshot but does **not** stop this read-then-write race — a classic **lost
update**. This is the bug that ends the interview if you miss it.

### Three ways to fix it

**1. SERIALIZABLE isolation.** Force the two transactions to behave as if they ran one
after the other. B is made to see A's write (20), fails the `20 >= 80` check, and is
declined. Safest; costs throughput (more aborts/retries under contention).

**2. A row lock (pessimistic).** `SELECT ... FOR UPDATE` on the account row: A takes the
lock, B blocks until A commits, then B reads the *real* 20 and is declined. Cheaper than
full serializable and precisely scoped to the hot row.

**3. A CHECK constraint as a backstop.** Declare `CHECK (balance >= 0)` (or debit via
`UPDATE ... SET balance = balance - 80 WHERE balance >= 80` and check rows-affected). The
database itself refuses to persist a negative balance, so even a logic bug above it
cannot overdraw the account. **This is the belt-and-suspenders every money ledger
wants** — it makes overdraw *structurally impossible*, not just unlikely.

In practice a real ledger uses **more than one**: a row lock (or serializable) to
serialize the decision *plus* the CHECK constraint so the invariant holds no matter what.

> **Interview line:** "Read-committed loses the update; I serialize the debit — a row
> lock on the account — and I keep a `balance >= 0` CHECK so the DB refuses to overdraw
> even if my code is wrong."

---

## Optimistic vs pessimistic vs distributed locking

| Strategy | How | Best when | Cost |
|---|---|---|---|
| **Optimistic** | version/CAS: read version, write only if unchanged, else retry | low contention (most accounts aren't hot) | wasted retries when a row *is* hot |
| **Pessimistic** | `SELECT ... FOR UPDATE` row lock | a genuinely hot account (payroll, a merchant) | holds a lock; blocks others; deadlock risk if lock order is sloppy |
| **Distributed** | a lock across nodes/services (e.g. a lease) | a resource spanning shards/services | slow, failure-prone; avoid on the money path |

**Doctrine for UPI:** keep the lock **local to one account row in one bank's DB** —
optimistic for the common cool path, pessimistic (row lock) for hot accounts.
**Avoid distributed locks on the hot path**; they add a network round-trip and a new
failure mode to the most latency- and correctness-sensitive step you have. The account
lives in exactly one bank's ledger, so you never *need* a cross-node lock to debit
it — a property the sharding gives you for free.

---

## Caching doctrine

Caching is where you win latency — and where you lose money if you cache the wrong
thing.

**Cacheable (read-heavy, staleness-tolerant):**

- **VPA / mobile → PSP resolution** — changes rarely; ms-stale is fine. The mapper is a
  cache in front of a small source of truth.
- **Public keys** (`ReqListKeys`), routing/config, bank-capability metadata.
- **Fraud features** — precomputed and held in memory precisely so the ~75 ms budget is
  met. `[V]`

**Never cache:**

- **Account balances / the authorization decision.** The debit must read and write the
  *authoritative* row transactionally (see the anomaly above). A cached balance is a
  lost-update waiting to happen. There is no such thing as a "good enough" balance.
- **Idempotency outcomes as anything but a durable record** — the dedup KV is a *fast
  reject*, but the guarantee lives in the RDBMS unique constraint, not the cache.

**TTL + invalidation:** give cached mappings a **TTL** (bounded staleness) *and*
**invalidate on change** (when a user re-links a VPA, evict the entry) — TTL alone lets
a stale mapping linger up to its whole lifetime; invalidation alone leaks entries if an
event is missed. You want both.

**Hot-key stampede + request coalescing:** when a very popular payee's mapping (a big
merchant, a viral UPI handle) expires, thousands of concurrent lookups can all miss and
hammer the source of truth at once — a **cache stampede**. Fix with **request
coalescing** (a.k.a. single-flight): the first miss fetches, and every concurrent
request for the same key **waits on that one in-flight fetch** instead of launching its
own. Pair it with a short **soft-TTL refresh-ahead** so the entry is renewed *before* it
hard-expires, and the stampede never forms.

> **Interview line:** "I cache resolution, keys and fraud features — never balances.
> Mappings get TTL *and* explicit invalidation, and hot keys get single-flight
> coalescing so an expiry doesn't stampede the source of truth."

---

## What to carry forward

- **Database-per-store**: relational+ACID ledger, KV mapper, two-layer dedup, in-memory
  fraud, Kafka journal, downstream search — no single database.
- The **two-concurrent-debits** anomaly under read-committed, fixed by **serializable /
  row lock / CHECK `balance >= 0`** (use more than one).
- **Local locks only** — optimistic for cool rows, pessimistic for hot ones, **no
  distributed lock on the money path**.
- **Cache** resolution/keys/features; **never** balances. TTL **and** invalidation.
  **Coalesce** hot-key misses.
- **`[V]` PhonePe uses HBase as source of truth** — "relational for money" is a strong
  default, not a universal law.

Next: [06 · Failures & operations →](./06-failures-and-operations.md)
