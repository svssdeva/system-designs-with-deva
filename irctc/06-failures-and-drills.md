# 06 · Failures & Drills

The round that separates a design that works in the demo from one that works at **10:00:00
on tatkal morning.** This doc is the failure drills, the observability that grades a system
on one minute, DR that falls out of sharding, and the policy trade-offs a sharp interviewer
will throw back.

---

## Drill 1 — the session stampede (before the sale even opens)

It's **9:50 a.m.** — and the uncomfortable fact: in **December 2024 the real system went
down three separate times (9, 26, 31 Dec), each around 09:50, before booking even
opened.** `[V]` The killer isn't bookings — it's the **login-and-refresh stampede**, **5–7×
normal** (8–10 lakh attempts in the 2015 window vs ~1.5 lakh normal; only ~⅓ got in). `[V]`

Your answers, in order:

- **The cache eats the reads** — 4 lakh/min availability checks never touch the truth.
- **The waiting room stops issuing tokens** the moment owner queues cross their depth line.
- **Sessions get rationed** — the real system literally **force-logs-you-out after each
  booking at peak.** `[V]`
- **Tatkal traffic is bulkheaded** from normal bookings, so the storm can't drown the
  passengers who just want Thursday's train.

> **Degrade the rumours. Protect the truth.**

## Drill 2 — the payment breaker (you chose pay-first)

Mid-storm, **iPay starts timing out** — money is leaving accounts and allocations are
failing. The **naive answer** is to make booking + payment one distributed transaction —
**2PC across the gateway.** **Reject it out loud:** 2PC across a payment gateway at tatkal
volume is a latency and lock-up disaster, and iPay may not even support it.

The right pattern is the **saga with a compensating action:**

1. The **breaker trips first** — fail fast, stop feeding the wounded gateway.
2. **Every money event lands in the journal first** — captured, allocated, or failed.
3. A **reconciliation service** reads that log and **matches three sources daily:** IRCTC's
   records, the gateway's settlement file, and the bank's.
4. Any **captured-but-unallocated** payment is a **compensating transaction — an automatic
   refund.** The **idempotency key** makes the whole money hop retry-safe: same key, same
   result, never a double charge.

**The number that bounds the damage isn't yours — it's the regulator's.** The **RBI TAT
rule forces auto-reversal within T+5 working days, with mandatory compensation for delay.**
`[V]` Your refund SLA isn't a nice-to-have; it's law. You don't just design the failure
path — you **cite the regulation that grades it.**

## Drill 3 — the bot war, and the 2025 identity wall

The bots got in. The **captcha? Cracked at ~98%** — assume it's dead. `[R]` IP rate limits?
A botnet has more IPs than you have users. So the railways moved the rate limit **up the
identity stack** — from IP to **identity:**

- **Only Aadhaar-verified accounts** in the opening window (1 Jul 2025). `[V]`
- An **Aadhaar OTP per booking** (15 Jul 2025); a **DigiLocker Govt-ID fallback** for the
  non-Aadhaar case. `[V]`
- **Agents locked out the first 30 minutes.** `[V]`

**Results (per a parliamentary reply — cite as reported, not a fetched PIB primary):** over
**3 crore suspicious accounts deactivated**, and **60+ billion malicious bot requests
blocked** in H2 2025. `[R]` Enormous.

### The honest part — identity is not admission control

On **17 April 2026 the tatkal window fell over anyway** — app crashes, endless loading,
failed and duplicate payments, bookings slipping to waitlist within seconds; **IRCTC
acknowledged it publicly on X.** `[R]` What does that tell you? The identity wall stopped
the **fraud** — but never touched the **thundering herd.** Ten million genuine humans
refreshing at 10:00 is still a *load* problem.

> **Identity is not admission control.** The Aadhaar wall is a rate limiter on **WHO**; the
> waiting room is a rate limiter on **HOW MANY.** You need **both.** Solving authentication
> and calling it scale is the exact mistake the interviewer is fishing for.

**Resume Booking (Apr 2026)** — the fix they shipped is itself a callback: if your money
was deducted but the ticket didn't complete, **you finish the booking without paying
again.** `[R]` The silent auto-refund promoted into a **visible compensating transaction the
user can drive.** Same religion, better UX.

## Drill 4 — the data-centre fire (DR is the partition scheme)

Not hypothetical: the **Kolkata reservation centre burned**, and another regional centre
picked up its territory's trains **for ~4 days** while the rest of the country never
noticed. `[V/R]`

**Most systems bolt DR on as a separate active-passive standby** — a whole idle copy you
pray works on the day. **Reject that here,** because the partition scheme already gives you
DR for free: PRS shards by **territory** (Delhi, Mumbai, Kolkata, Chennai, Secunderabad).
**Your blast radius equals your partition unit — a territory, never the nation.** In our
design: every inventory owner has a **hot replica in a different region**, replicating
**synchronously within a shard.** Lose an owner → **promote its replica, reroute that
shard's keys.** The rest of the country never feels it.

**Consistency, precisely** (the interviewer will push): **inside a shard, the booking write
must be strongly consistent** — you cannot promote a lagging replica and re-sell a berth,
so **replication within a shard is synchronous** (RPO ≈ 0), and you accept the write
latency as the cost of never double-selling. **Across shards, and in the enquiry tier,
eventual is fine** — availability was always a rumour. **Different consistency for different
data is not a compromise; it's the whole design.**

---

## Observability — a system graded on one minute

This system's whole year is graded on the window from **10:00 to 10:02.** You do **not**
monitor that with **five-minute average dashboards** — an average smears the one spike you
exist to survive into a flat, lying line. So:

- **Per-second panels:** tokens issued, bookings committed, owner queue depth, payment
  breaker state, refund backlog.
- **The deciding evidence it's real:** the railways publish records **measured to the
  minute** — **37,410 bookings in a single minute on 16 Aug 2025.** `[R via ANI]` You
  cannot report a per-minute record unless you're instrumented to **at least per-minute.**
- **The SLO itself:** define it on the thing that matters — the **probability an admitted
  booking commits within ~3 s during the opening window** — and set an **error budget** on
  it.
- **One alert that pages a human — burn rate:** when **owner queue depth climbs faster than
  the owners drain it**, you're minutes from breaching; widen the gate or shed load **now.**
  One page, not a wall of noise.

> **Interview line:** "The dashboard is my closing argument — I don't *hope* it's healthy,
> I can prove it to the second."

---

## Data lifecycle & CDC — feed analytics without touching the hot path

The tempting mistake is to let the analytics team **query the booking database directly**
"just for a dashboard." **Kill that in the interview** — one heavy analytical query against
the inventory owner during tatkal and you've taken down bookings to draw a chart.

The pattern is **change-data-capture.** A **Debezium-class connector tails the ledger's
transaction log** and streams every change onto **Kafka — the same journal we already
have.** Search, analytics, and the availability cache all **consume that stream, completely
off the hot path.** The write path never even knows they exist.

**Lifecycle by temperature:**

- **Hot** — current and near-future train-dates, live in the owner's memory and the ledger;
  small, fast, the only data a booking touches.
- **Warm** — recently-travelled PNRs, queryable for refunds, TDR claims and support for a
  few months.
- **Cold** — everything older, archived to cheap object storage for audit and yearly
  analytics.

And a free architecture win: the **advance reservation period was cut 120 → 60 days
(1 Nov 2024)** `[V]` — which conveniently **halves your hot inventory set.** A policy change
that's also a caching win. Notice those when they happen.

---

## Trade-off — the 25% waitlist cap (defend the number)

In 2025 they **capped the waitlist at 25% of a class's berths** (SL/3AC/2AC/1AC), replacing
a **fixed-count rule from 2013.** `[R]` **Defend it:** it's tuned to reality — officials say
only ~a fifth to a quarter of waitlisted tickets ever confirm, so capping near 25% stops
selling hope you can't honour. The sourced cost of the old bet: **~93,000/day auto-dropped
at chart** and **₹1,229 cr in cancellation charges over 3 years.** `[R, RTI]`

**But the follow-up with teeth:** economists called the cap **"uneconomical and
impractical"** — fewer waitlist seats means **lost revenue from passengers who WOULD have
confirmed**, pushed instead onto costlier trains. `[R]` The **honest senior answer:** yes —
it's a **policy trade-off, not a pure optimisation.** You're trading revenue for a promise
you can keep. **Naming the counter-argument is the answer.**

---

## The chart batch as settlement (the failure-tolerant hot path)

The hot path stays dead simple **because a batch job settles the debt.** One nightly run per
train (moved to **8–10h before departure in 2025** — a design lever, bigger restock window):
sweeps unused quota berths back to general, runs the **promotion cascade to exhaustion**,
**auto-cancels every still-waitlisted e-ticket with an automatic refund** (they legally
cannot board), hands opted-in leftovers to **VIKALP**, then opens survivors to current
booking. `[V/R]` The waitlist economy's entire honesty lives in this one boring job.

---

## What to carry forward

- **Session stampede** → cache eats reads, gate meters tokens, sessions rationed
  (force-logout), tatkal bulkheaded. `[V]`
- **Payment breaker** → saga + compensating refund, 3-way daily recon, **RBI TAT caps the
  damage.** `[V]`
- **Bot war** → rate-limit **identity, not IP** (3 cr accounts, 60 bn requests) — but the
  **17-Apr-2026 outage** proves **identity ≠ admission control.** `[R]`
- **DR = the partition scheme** (Kolkata fire); **sync within a shard (RPO≈0), eventual
  across.** `[V/R]`
- **SLO on one minute** — per-second panels, burn-rate paging; per-minute records prove
  per-minute instrumentation. `[R]`
- **CDC off the WAL → Kafka**; tier data hot/warm/cold; ARP 120→60 halves hot set. `[V]`
- **25% WL cap** = a **policy trade-off with a named counter-argument.** `[R]`

Next: [07 · Build it yourself →](./07-build-it-yourself.md)
