# 02 · Requirements & the API Contract

The first ten minutes of the interview. Before any boxes, you scope the problem: what must
it do, how well, how big, and what does the contract on the wire look like. The prompt,
exactly as an interviewer says it: **"Design a train-ticket booking system for India —
reserved seating, dated journeys, extreme opening-minute spikes."** The first senior move
is to **not start drawing.**

---

## Scope — fence it out loud

Refusing scope is a seniority signal. Every minute on catering is a minute stolen from the
one problem this system is famous for.

**In scope:**

- **Search & availability** — per class, per quota, per date.
- **Booking** with atomic berth allocation.
- **Tatkal** — the timed 10:00 open (premium tatkal floats its price).
- **Waitlist & RAC** lifecycle — numbered queues, promotions, the chart settlement.
- **Cancellation & refunds** — including the ugly "money left but no ticket exists" path.
- **Status API** — because things *will* go wrong mid-payment.

**Out of scope (say it):** unreserved tickets, freight, catering, and the frontend app
itself.

---

## Functional requirements (five)

1. **Search & check availability** — per class, per quota, per date. `[V]`
2. **Book** — pick passengers, get berths *atomically* allocated. `[I]`
3. **Honour timed quotas** — tatkal opens at 10:00; premium tatkal floats its price. `[V]`
4. **Run the waitlist/RAC lifecycle** — numbered queues, a promotion on every cancellation,
   the nightly chart settlement. `[V/R]`
5. **Cancel & refund** — including the path where money left but no ticket was created.
   `[V]`

## Non-functional requirements — ranked (ranking *is* the design)

1. **Inventory correctness.** One berth, one passenger — no failure mode excuses a
   double-sell. This outranks everything.
2. **Fairness.** Humans must beat bots in the opening minute — a **security requirement
   wearing a scheduling costume.** (Unusual, and the interviewer notices you named it.)
3. **Availability through the storm.** Degrade **reads** before you ever degrade
   **bookings.**
4. **Latency.** For booking, **seconds are fine** — nobody abandons a confirmed berth over
   a slow spinner.

> **Correctness over speed — the exact opposite of a payments system.** A slow booking is a
> nuisance; a double-sold berth is a catastrophe on national television.

Plus the standing ones: **auditability** (per-minute records exist — see below), and
**multi-region correctness** within India (DR is the partition scheme —
[06](./06-failures-and-drills.md)).

---

## Back-of-envelope — the daily average is a lie

The trap: **14.53 lakh tickets/day (avg FY26) is only ~17 bookings/second.** Trivial. But
this system is designed for **one specific minute.** `[I from V volumes]`

**The violent minute:**

```
avg day:   1,453,000 bookings/day ÷ 86,400 s ≈ 17 bookings/s   [I — a red herring]
the spike: recorded 37,410 bookings in ONE minute (16 Aug 2025)  [R via ANI]
           alongside ~4 lakh availability checks/min             [V]
```

**Size the two roads separately:**

```
WRITE path: design for ~40,000 bookings/min ≈ 700/s with headroom   [I — estimate]
READ path:  12–13× that (the 12.5:1 ratio)  ≈ 4 lakh checks/min      [V ratio]
```

**Sanity-check against the real bar:** official capacity is quoted as a **range,
25–32k bookings/min**; **5 lakh+ concurrent sessions**; recorded peak minute **37,410**
(16 Aug 2025). `[V/R]` Don't blend records with capacity — quote each with its date. Our
numbers sit right on the bar.

> The shape these numbers force: **two roads, sized 12.5:1** — a cheap read tier in front,
> a metered write tier behind — and an **admission gate** so the opening minute never hits
> the booking API raw. The envelope drew the architecture.

---

## The API contract

### Pick the style, out loud

- **REST on the public edge.** Cacheable availability, dumb-simple clients, CDN-friendly —
  which matters at 4 lakh reads/min. `[I]`
- **gRPC between internal services.** Typed contracts, low latency on the booking hop.
  `[I]`
- **GraphQL — skipped, and say why:** this client asks **three fixed questions**, not
  arbitrary graph queries. A resolver fan-out in the opening minute is a self-inflicted
  wound. (No client-graph problem = no GraphQL.) `[I]`

### The four calls that matter

| Call | Shape | Notes |
|---|---|---|
| **GET availability** | train · date · class · quota | cheap, **cacheable, seconds-stale OK** — it's a rumour, not a promise |
| **POST book** | passengers · class · quota · payment ref | carries **two headers** (below); returns **`202 Accepted` + booking ID** — allocation resolves **async** |
| **GET booking-status** | booking ID | polling a pending booking is the honest UX |
| **POST cancel** | booking ID | itself a small **financial transaction** |

**Every mutation is idempotent. No exceptions.** `[D]`

### The two headers that do the heavy lifting

**`POST book`** carries:

1. **Admission token** — proof you passed the waiting-room gate (below).
2. **Idempotency key** — so a double-tap during the storm never books twice.

IRCTC's *own* internal booking dedup/idempotency is **not published — UNKNOWN**; we
present idempotency as a **design requirement**, not an IRCTC fact.

### The admission token — the tatkal answer

At 10:00 you do **not** let raw traffic touch the booking API. A **waiting room** in front
issues **admission tokens at the rate the core can survive** — everyone else holds a
**queue position, not a database connection.** `[D]` The real system rations sessions too:
at peak it even **force-logs-you-out after each completed booking** (since Mar 2015). `[V]`
Same instinct, cruder tool — we build the polite version on the board
([03](./03-high-level-design.md), [06](./06-failures-and-drills.md)).

---

## Identifiers — four IDs, four jobs

| ID | Who / form | Job |
|---|---|---|
| **PNR** | 10 digits (public) | the passenger-visible reservation reference |
| **Booking ID** | ours | drives the async 202 lifecycle |
| **Idempotency key** | ours | collapses retries of the *same* call |
| **Admission token** | ours | proves you passed the gate |

The **PNR** is **commonly documented** as a reservation-centre prefix (first 3) + a
7-digit serial — but the railways have **never published the encoding**, so say "commonly
documented," not fact. `[R only]` Don't overload one number with two meanings.

---

## What to carry forward

- **In:** search · book · tatkal · WL/RAC · cancel/refund · status. **Out:** unreserved,
  freight, catering, frontend.
- **NFRs ranked: correctness > fairness > availability > latency** — the opposite of a
  payments system.
- **Envelope:** the average (~17/s) is a lie; design for **~40k bookings/min write** +
  **~4 lakh checks/min read** (12.5:1), against a **25–32k/min** capacity bar and a
  **37,410/min** record (16 Aug 2025). `[V/R]`
- **Contract:** REST edge, gRPC internal, **skip GraphQL**; `202`-async book; every
  mutation idempotent; **admission token + idempotency key** on `POST book`.

Next: [03 · High-level design →](./03-high-level-design.md)
