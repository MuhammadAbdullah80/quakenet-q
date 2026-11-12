# QuakeNet-Q: Progress

Last updated: 2026-11-12

## Where we are

**Stage: design is nearly final; the agent is not built yet.**
A working proof of concept exists and is pushed. Everything after it is design and research.

| Area | Status |
|---|---|
| Proof of concept (one earthquake, one run) | ✅ Built, tested (13 tests), pushed |
| Agent design spec v1 | ✅ Written (98/100 on the spec checker), committed locally |
| Research: related tools and techniques | ✅ Done, with sources |
| Spec v2 (technique changes + web system) | ⏳ Not written; needs your answers in `docs/OPEN_QUESTIONS.md` |
| Agent build | ❌ Not started |
| Web API and Next.js test frontend | ❌ Not started |
| Report, README, video for the final version | ❌ Current ones describe the proof of concept only |

## What exists today

| Item | Where | Notes |
|---|---|---|
| Proof-of-concept code | `src/`, `run_experiment.py`, `tests/` | Ridgecrest 2019, choose 4 of 10 sites |
| Results and figures | `results/results.json`, `figures/` | From the full run (15 QAOA runs) |
| Report, diagram, video script | `report/`, `figures/architecture.png`, `VIDEO_SCRIPT.md` | Describe the proof of concept |
| Design spec v1 | `docs/specs/2026-11-12-quakenet-q-agent-design.md` (+ `.html`) | 29 requirements, 21 acceptance tests |
| Research notes | `research/seismo-placement/`, `research/technique-comparison/` | About 40 source notes |
| Explainer pages | `docs/visuals/` | 7 HTML pages |
| GitHub repo | https://github.com/MuhammadAbdullah80/quakenet-q | **Private.** 2 local commits not pushed |

## Proof-of-concept results (measured)

- Hybrid QAOA returned the exact best network in **15 of 15 runs**.
- Chance of measuring the best network per shot: **5.1%** (1 layer) to **10.0%** (3 layers), against 0.48% for a random valid network.
- The pairwise score tracked the true score at Spearman ρ = **0.987**.
- Predicted blur on later aftershocks: **2.73 km → 1.50 km**. This is a model prediction, not a measured error.
- Greedy, backward elimination and simulated annealing found the same answer. No quantum speedup is claimed.

## Decided, not yet in the spec

1. Add the DN score alongside the D-criterion; held-out data decides which one plans.
2. Double-check top layouts with a slower information-gain estimate (NMC).
3. Realistic timing errors: far stations cannot hear small aftershocks.
4. Slope under 20° filter from key-free terrain tiles.
5. Write the DN code ourselves (the reference tool is GPL-licensed).
6. Keep exhaustive checking plus the quantum circuit as the search.
7. Keep simple wave-speed models; no 3D wave paths.
8. Usability claim: the agent needs no manual setup.
9. Rewrite the problem statement: tools exist for planning ahead; none is built for aftershocks, starts itself, or re-plans.
10. New system requirements (see `docs/ARCHITECTURE.md`): web API, Next.js test frontend, rate limiting, geo-based regions (designed now, single server for the MVP). The frontend is hosted on Vercel; the backend runs on the team laptop, reached through a secure tunnel.
11. No AI or LLM features in the app.

Reasons for each are in `docs/DECISIONS.md`.

## Next steps, in order

1. **You:** answer the questions in `docs/OPEN_QUESTIONS.md`. The deadline question blocks the build.
2. Write spec v2 and rebuild its HTML.
3. Write the implementation plan.
4. Build, testing each stage before the next:
   1. exact score, DN score, higher success rate;
   2. expert-rule baseline and a second earthquake;
   3. agent loop in replay mode;
   4. web API with rate limiting;
   5. Next.js test console;
   6. remaining benchmark earthquakes;
   7. live mode and the optional hardware demo;
   8. Vercel deployment and the laptop tunnel.
5. Security review against the checklist in `docs/ARCHITECTURE.md`.
6. Update the report and README; record the video; make the repo visible to judges; submit.

## Risks to watch

- **Deadline unconfirmed.** The brief says 12 Nov 2026, 23:59. The team said it is later.
- **Scope.** The spec already has 29 requirements, and the web system adds more. Stages 6 and 7 can be cut.
- **Unverified claims.** See risks R-2 to R-6 in the spec. R-1 (related tools) is now checked.
- **The expert-rule comparison may show a small gain.** We report whatever it shows.
