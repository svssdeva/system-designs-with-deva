# 01 · How IRCTC Really Works

The machine as it exists today. Before you can design a train-booking system, you have
to see what the real one *actually is* — and the first surprise is that "IRCTC" isn't
the reservation system at all. This doc fixes the mental model. Everything downstream
(requirements, the board, seat correctness) hangs off these facts.

---

## 1. IRCTC is the storefront, not the brain

The thing you call IRCTC — the website, the app, the payments — is the **storefront**.
The reservation **brain** is a separate system called **CONCERT**, built and run by
**CRIS** (Centre for Railway Information Systems, the railways' own software house), the
core of its **PRS** (Passenger Reservation System). `[V]`

| Layer | What it is | Owns berths? |
|---|---|---|
| **You** | the app / web | No |
| **IRCTC** | storefront + its own payment aggregator **iPay** | No |
| **NGeT** | CRIS's e-ticketing engine (live 28 Apr 2014, ₹74 cr) | No — it fronts PRS |
| **CONCERT / PRS (CRIS)** | the reservation core; every berth in the country | **Yes** |

PRS runs across **regional data centres — Delhi, Mumbai, Kolkata, Chennai** (+ Secunderabad
in the RTR-era grid) — each hosting its own zones' databases, stitched into one national
grid. `[V]` Every berth decision — quota math, waitlist numbers, the chart, your seat
number — happens *inside PRS*, not in the storefront.

> **Myth-bust #1:** when the internet screams "IRCTC crashed," half the time the storefront
> is fine and the queue is somewhere deeper — at the reservation core. `[I]`

**Four hops:** You → IRCTC + iPay → NGeT → CONCERT. Watch what each one is *allowed to
touch* — only the last owns inventory.

---

## 2. Two pipes: checking a train ≠ booking a train

Secret mechanism number one. **Enquiry and booking do not travel the same road**, and the
government sizes them separately at every era. `[V]`

- 2014 (NGeT launch): ~200k enquiries/min vs ~7.2k bookings/min.
- 2025 (ministry, PIB PRID 2140614): **4 lakh enquiries/min vs 32k bookings/min — a
  12.5:1 read:write ratio.** `[V]`

The availability number you're staring at is an answer from the **cheap road** (the
enquiry tier). The berth only becomes yours on the **expensive road** (a booking committed
against the system of record). The exact caching mechanism inside the enquiry tier is
**not published** — say "two separate pipes, officially sized 12.5:1," never "cached with
TTL" as fact. `[I]`

---

## 3. Pay-then-allocate — the inversion that stings

Secret mechanism number two. When you tap **book, nothing is reserved.** There is **no
cart, no hold.** IRCTC takes your **money first**, and only *then* asks the reservation
core for a berth. `[R→V-adjacent]`

In the gap between those two steps, someone else can take the seat you saw. That's why
**"money debited, ticket not booked"** is a routine failure with an entire **automated
refund machine** built around it — IRCTC's institutionalized compensating transaction.
`[V]`

Contrast with **BookMyShow-class** systems, which are **reserve-then-pay** (a TTL hold on
the seat while you pay). IRCTC inverted it to keep inventory liquid during the storm — the
refund machine is the price of that choice. We defend the ordering in
[05 · Seat correctness](./05-seat-correctness-deep-dive.md).

---

## 4. Quotas — one train is ~19 fenced pools

Secret mechanism number three. One train is **not one pool of seats.** It's carved into
around **19 named quotas** — general (GN), tatkal (TQ), premium tatkal (PT), ladies (LD),
senior lower-berth (SS), defence, headquarters (HO), and more — each an **independent pool
with its own counter and its own waitlist** over one physical inventory. `[V]`

That's why you and a friend can look at the same class on the same train and see
**different availability**: you're reading different fences over the same steel. It's
**inventory sharding, done as policy.** `[I framing]`

---

## 5. Waitlist and RAC — priced oversell, honest overbooking

Secret mechanism number four. The **waitlist is not a queue for leftovers** — it's the
railways **deliberately selling more tickets than berths, betting on cancellations.** `[V/R]`

- **WL flavours** clear from different pools: **GNWL** (best) > RLWL > PQWL > **TQWL**
  (worst — tatkal cancellations are rare). `[V/R]`
- Officials cite **roughly a fifth to a quarter of waitlisted tickets confirm.** `[R]`
- **RAC** is cleverer still: **two passengers share one side-lower berth** (fractional
  inventory), both guaranteed to travel — overbooking done honestly, in the data model.
  `[V]`

The bet has a **sourced price:** about **93,000 people/day** never make it off the
waitlist (RTI progression: 1.65 cr FY22 → 3.39 cr FY26 auto-dropped at chart), and
cancelled-WL charges earned the railways **over ₹1,229 cr in three years.** `[R, RTI]`
Never quote a made-up confirm %; use the RTI absolutes.

---

## 6. The chart — the nightly settlement

Secret mechanism number five. The night before departure, a **batch job** runs — the
**chart.** `[V/R]` Cancellations pour back in; **RAC climbs to confirmed, WL climbs to
RAC;** unused quota berths flow back to general; **fully-waitlisted e-tickets are
auto-cancelled with an automatic refund** (they legally cannot board); **VIKALP** moves
opted-in residual WL to alternate trains. Then remaining vacancies open to current
booking.

**Rule changed in 2025** — treat it as a design lever, not trivia: the first chart moved
from **4h before departure → 8h (Jul 2025) → ≥10h (Dec 2025)**; morning trains now charted
**~20:00 the previous night.** `[V/R]` A bigger window = more cancellations to redistribute
= more waitlisted passengers confirm. The second chart runs **30 min before** departure.

> Instant promises up front, one big honest settlement later — the same religion as UPI's
> deferred net settlement, a different temple. `[I]`

---

## 7. The tatkal war and the survivor core

Every morning at **10:00** (AC tatkal; 11:00 non-AC), a month of demand detonates into one
minute. In the 2015 window, **8–10 lakh login attempts** hit in 10:00–10:15 vs ~1.5 lakh
normal concurrency (~5–7×), and **only about a third got sessions.** `[V]` The current
multiple is **UNKNOWN.**

The 2025 defence moved the rate limit **up the identity stack** (see
[06 · Failures](./06-failures-and-drills.md)): the captcha was machine-solvable at ~98%
`[R]`, so **only Aadhaar-verified users book tatkal in the opening window** (1 Jul 2025),
**Aadhaar OTP mandatory** (15 Jul 2025), **agents locked out the first 30 min.** `[V]`

And the twist the whole story hangs on: the core that survives this war is written in
**C (~70%) + Fortran (~30%) on OpenVMS** — a design lineage from the 1980s (VAX minicomputer
→ Compaq Alpha → Itanium), with **RTR (Reliable Transaction Router)** middleware over an
in-house CRIS proprietary DB. `[V]` **It is NOT a mainframe and NOT COBOL — never say
COBOL.** It even survived a **fire**: when the **Kolkata PRS centre burned, Secunderabad
took over its territory for ~4 days** and the country kept booking. `[V/R]` Old, boring —
and correct where it counts.

---

## What to carry forward

1. **IRCTC = storefront; CRIS's PRS/CONCERT = the brain** that owns every berth. `[V]`
2. **Two pipes**, officially **12.5:1** reads:writes — availability is a cheap-road answer.
   `[V]`
3. **Pay-then-allocate** (no hold) → routine "debited, not booked" + an auto-refund machine.
   `[V]`
4. **~19 quotas** = inventory sharding as policy; **WL = priced oversell**, **RAC =
   fractional inventory.** `[V/R]`
5. The **chart** is a nightly settlement batch (window widened to ~8–10h in 2025). `[V/R]`
6. The core is **C+Fortran on OpenVMS + RTR**, DR-proven by the Kolkata fire. **Never
   COBOL/mainframe.** `[V]`

Next: [02 · Requirements & API →](./02-requirements-and-api.md)
