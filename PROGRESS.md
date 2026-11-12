# QuakeNet-Q: Progress

Last updated: 2026-11-12

## Where we are

**Stage: the agent, the API and the console are built and running. Documents and the video remain.**

| Area | Status |
|---|---|
| Ridgecrest experiment (exact objective, location test) | ✅ Built, full run committed (`results/results.json`) |
| Science layer v2: more earthquakes, hearing range, velocity ensemble, CVaR, noise study | ✅ Built and tested |
| Benchmarks on five more earthquakes | ✅ Run (`results/benchmarks.json`); South Napa skipped (too few aftershocks) |
| Agent loop: trigger, first plan, hourly checks, re-plans, memory | ✅ Built; a real 24-hour Ridgecrest replay runs in about 20 seconds |
| Live mode (watching the USGS feed) | ✅ Built, off by default; tested with a fake feed only |
| Web API v1 + v2 (FastAPI, on the team laptop) | ✅ Built, 303 tests pass |
| Next.js console with agent pages (Vercel) | ✅ Built: Settings, Live feed, Plan, Monitor, Memory, Noise study |
| Frontend redesign (`docs/FRONTEND_BRIEF.md`) | ✅ Merged: console restyle, landing scroll story at `/`, guide at `/guide` |
| Report, README, video script | ✅ Report rebuilt as a formatted 20-page document: cover, contents, idea history, caveats, brief checklist, glossary; PDF copy alongside |
| Video | ❌ Not recorded |
| Spec v2 | ✅ "Version 2: what was built" section with a status for every requirement; HTML rebuilt |

## Measured results

**Ridgecrest 2019, 4 of 10 sites** (`python run_experiment.py`):
- The circuit encodes the exact score (385 terms), zero error on all 210 networks.
- QAOA final pick was the exact optimum in **15 of 15** runs.
- Chance per measurement of the best network: **5.1%, 8.3%, 11.0%** for 1, 2, 3 layers (random: 0.48%). Target 20%: missed.
- Simulated location error on 217 later aftershocks: **3.00 km** with no new sensors, **2.63 km** expert rule, **2.31 km** our pick (rank 4 of 210).

**Benchmarks, five earthquakes** (`python run_benchmarks.py`, 3 layers, 3 seeds, 11 minutes):

| Earthquake | P(best) mean / CVaR, cold start | Final pick exact, CVaR cold | Our optimum vs expert rule (location error) |
|---|---|---|---|
| Ridgecrest 2019 | 3.8% / 9.6% | 3/3 | 2.4% better |
| Monte Cristo Range 2020 | 1.2% / 7.3% | 3/3 | 0.1% worse |
| Anchorage 2018 | 0.4% / 1.6% | 2/3 | 0.7% worse |
| Ferndale 2022 | 6.0% / 7.0% | 3/3 | 2.9% worse |
| Puerto Rico 2020 | 6.2% / 8.2% | 3/3 | 15.8% worse |

- CVaR raised the share of exact final picks from 8/15 (mean objective) to 14/15.
- The 20% target was missed in all 60 runs.
- **The optimised network beat the expert rule on only 1 of 5 earthquakes** in the simulated location test.
  The score we optimise (D-criterion) does not always predict the simulated error. We report this as it is.

**Noise study** (simulated, not hardware): on a 6-site, 2-sensor version, P(best) falls from 52% to
24% and valid outcomes from 100% to 61% at gate error 1%.

## Next steps, in order

1. Decide what to say about the expert-rule result in the pitch. Suggested: the agent's value is speed,
   automation and re-planning; the score itself is not yet better than a field rule on most earthquakes.
2. Record the video (`VIDEO_SCRIPT.md`), add the team name to the report, make the repo visible to judges, submit.

## Risks to watch

- **Deadline:** the brief says 12 Nov 2026, 23:59. The team said it will confirm.
- **The laptop must be on** for the live site to show live data; otherwise it shows saved snapshots.
- **Live mode** has not run against a real qualifying earthquake.
- **Hearing-range constants** are assumptions, and the location test is a simulation.
