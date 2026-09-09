# Design a Video Player — frontend system design

The written companion to two videos:

- **Part 1 — Design a Video Player.** How the machine works: `<video>`, MSE, the controller
  cluster, the ABR decision, and the drills that break it.
- **Part 2 — The Follow-Up Round.** The ten questions an interviewer asks *after* you have
  drawn it, and the one question hiding inside all of them: **not how does it work — how
  would you know.**

Every diagram, number and decision from both videos is here. Nothing in these docs is
asserted without a label.

## Honesty labels

Applied to every checkable claim, so you can tell what is sourced from what.

| label | means |
|---|---|
| `[V]` | verified in a primary source (hls.js source, MDN, a measurement run here) |
| `[R]` | reported by a secondary source |
| `[I]` | an estimate or a conventional value, not a measurement |
| `[D]` | a design choice — defensible, not the only answer |

## The docs

| # | doc | the marquee mechanic |
|---|---|---|
| 01 | [How it really works](01-how-it-really-works.md) | there is no "the file" — 89 requests for one video |
| 02 | [Requirements and the API](02-requirements-and-api.md) | **the manifest IS the API contract** |
| 03 | [High-level design](03-high-level-design.md) | the controller cluster bolted onto MSE |
| 04 | [Services and interactions](04-services-and-interactions.md) | who calls whom, and **which calls can block** |
| 05 | [Data — the ABR decision](05-data-and-the-abr-decision.md) | **two EWMAs, and you take the lower one** |
| 06 | [Failures and drills](06-failures-and-drills.md) | the buffer state machine, and the three nudges |
| 07 | [Build it yourself](07-build-it-yourself.md) | the framework-agnostic core, and the deciding number |

## Sources

- **hls.js v1.6.17** — `docs/design.md` and the `src/controller/` tree. The controller list,
  the EWMA half-lives, the up/down factors, the emergency-abort path and the gap-nudge
  count are all read from source rather than from blog posts.
- **MDN** — `HTMLMediaElement`, `MediaSource`, `TimeRanges`, the cross-browser video-player
  guide. Used for the *control surface*: what the platform exposes, including the two
  platform lies in doc 01.
- **shaka-player 5.2.4** — for the comparison in doc 07.
- **Measured here, not quoted:** the gzipped bundle sizes in doc 07 were produced by
  gzipping the shipped `dist` files of the current releases. A number you cannot cite is a
  number you should not put on screen.

## Reading it as interview prep

Docs 01–03 are the model. Doc 05 is the one interviewers actually probe. Doc 04 is the
question that catches people who memorised a diagram. Doc 07 is the tech-stack round.

If you only read one section, read **doc 05's `min(fast, slow)` swimlane** — it is the most
under-explained idea in this whole topic, and it is four lines of real code.
