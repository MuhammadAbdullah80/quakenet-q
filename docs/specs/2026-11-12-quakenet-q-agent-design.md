# QuakeNet-Q Agent: Design Specification

**Status:** Version 2, as built. Approved by the team; this version records what was built and measured  
**Date:** 2026-11-12  
**Author:** QuakeNet-Q team (drafted with Claude Code)  
**Reviewers:** All team members  
**Supersedes:** The single-run proof of concept in commit `d34e328`

---

## Version 2: what was built

Version 1 of this document was the design. The team approved it with eight technique changes
(`docs/DECISIONS.md`, decisions 12 to 18), two system changes (a web API and a test console, decisions
21 and 25) and one removal (no AI or LLM features, decision 23). This section says what exists now.
Where the rest of the document and this section disagree, this section and `docs/API.md` win.

### How it runs

- **Backend:** a FastAPI service on the team laptop (`api/`), bound to 127.0.0.1 and reached through a
  Tailscale Funnel tunnel with a shared bearer token. The agent (`src/agent/`) runs inside it.
- **Frontend:** a Next.js test console on Vercel (`web/`), one page per module. The browser never calls
  the backend; the passcode protects every change. With the laptop off it shows saved results.
- **No command-line agent.** The commands in "API Contracts" became web endpoints, listed in
  `docs/API.md`. The experiments are scripts: `run_experiment.py` and `run_benchmarks.py`.

### Requirement status

| Requirement | Status |
|---|---|
| FR-1 Live feed | Built. Reads the USGS 2.5_day feed at most once a minute. Live mode is off by default and has been tested only with a recorded feed. The trigger magnitude is a setting a scientist can change (3.0 to 9.0) |
| FR-2 Replay | Built. Simulated clock; tests check that no later data is used |
| FR-3 Aftershocks, T0 plan | Built. Synthetic aftershocks (Wells & Coppersmith rupture length, Gutenberg-Richter magnitudes) when fewer than 30 real ones exist |
| FR-4, FR-5 Stations, cache | Built, through one outbound gateway (`src/sources.py`) |
| FR-6, FR-7 Candidate pool, backups | Built. Road check worked for all six benchmarks after one retry |
| FR-8 Spread selection | Built. Ridgecrest keeps the 10 published sites so results stay comparable |
| FR-9 Team overrides | **Not built** |
| FR-10 Velocity ensemble | Built (three uniform models, 5.5, 6.0 and 6.5 km/s) |
| FR-11 to FR-13 Exact objective | Built. 385 terms, zero error on all 210 networks |
| FR-14 QAOA, Dicke + XY | Built |
| FR-15, FR-16 CVaR, warm start | Built, alpha = 0.1. During tuning the circuit's output comes from an exact simulator of the same circuit, checked against Qiskit's Statevector (decision 29) |
| FR-17, FR-18 Sampling, logging | Built. 1,024 shots on Qiskit's StatevectorSampler |
| FR-19 Hardware demo | **Replaced** by a simulated gate-noise study (`src/noise.py`, page "Noise study"). No hardware access |
| FR-20 Self-check | Built. Two retries with more layers and shots, then the exact optimum is published and flagged |
| FR-21, FR-22 Plan, confidence | Built. Errors are relative to the predicted information gain (decision 30) |
| FR-23 to FR-25 Monitoring, drift, re-plan | Built. Interval, duration and thresholds are settings |
| FR-26 Reference strategies | **Partly built.** Each plan reports the expert rule; greedy and annealing are compared in the experiment and benchmark scripts |
| FR-27, FR-28 Memory | Built. The velocity weights stay equal in practice: without measured arrival times the models cannot be told apart |
| FR-29 Leave-one-out | **Partly built.** `run_benchmarks.py` warm-starts each earthquake from the angles of the other ones; there is no full replay loop |
| NFR-1 Plan within 5 minutes | Met. A plan takes seconds; a 24-hour replay about 20 seconds |
| NFR-2 to NFR-8 | Met. 305 tests run offline in about 45 s |
| Hearing range (decision 16) | Built, opt-in, with assumed constants (decision 26) |
| DN score (decision 18) | In the experiment only; the planner uses the D-criterion |
| NMC check (decision 17) | **Not built** |

### What was measured

- Ridgecrest: QAOA's final pick was the exact optimum in 15 of 15 runs. Chance per measurement 5.1% to
  11.0% for 1 to 3 layers. Simulated location error 3.00 km with no new sensors, 2.63 km expert rule,
  2.31 km our pick.
- Five benchmark earthquakes: CVaR made the final pick exact in 14 of 15 runs (8 of 15 without). The
  20% target (AC-7) was missed in all runs.
- **AC-16:** the best-scoring network beat the expert rule on 1 of 5 earthquakes in the simulated
  location test (Ridgecrest, 2.4%); on Puerto Rico it was 15.8% worse. The D-criterion does not always
  predict location error.

Sources: `results/results.json`, `results/benchmarks.json`,
`research/benchmarks/2026-11-12_benchmark_results.md`.

---

## Context

### The problem

After a large earthquake, response teams install portable seismometers to record the aftershocks. In the
first hours, the instruments that matter most are the **few that send data in real time**. Thousands of
cheap nodal sensors may follow later, but those typically record to internal memory and are collected
weeks afterwards. Where the first real-time instruments go decides how sharply aftershocks can be
located while the emergency is still unfolding.

Methods for choosing optimal station sites have been published since the 1970s–90s:
- Kijko (1977), early optimal network planning;
- Rabinowitz & Steinberg (1990), the D-optimality criterion;
- Hardt & Scherbaum (1994), aftershock networks designed from the mainshock alone.

Published accounts of real deployments still describe siting qualitatively. For example, the USGS
at Ridgecrest in 2019 aimed to "improve azimuthal coverage and provide additional near-field
observations" (Cochran et al. 2020). We found no tool that recommends sites automatically after an
earthquake. Existing tools are either for designing a network in advance (AuScope Seismic Network
Design App) or for judging an existing network (SN-CAST). Both claims rest on short descriptions and
must be re-checked (R-1).

### Why the published methods stay on paper, and how we respond

| Barrier (evidence in `research/`) | Response in this design |
|---|---|
| Computed ideal spots are often unusable (access, permits, noise, safety) | Candidates are built from reachable places, each with backup spots (FR-6, FR-7, FR-21) |
| Cheap dense nodes reduce scarcity | Scope limited to the first few real-time instruments (Out of Scope, OS-1) |
| A sensible human layout may be nearly as good | An explicit expert-rule baseline, with the gain over it reported honestly (FR-26, AC-16) |
| Results depend on an assumed Earth model | Sites are scored across several velocity models (FR-10) |
| Teams want more than location accuracy | Scope stated as location accuracy only (OS-3) |
| Aftershocks migrate | Hourly re-planning (FR-23 to FR-25) |
| No tool and no expert time during a crisis | The autonomous agent itself (FR-1 to FR-5) |
| Field teams distrust black boxes | Every site comes with its reason and score (FR-21) |

### What the proof of concept already showed

On the real Ridgecrest 2019 data (commit `d34e328`):
- The quantum circuit (Dicke state plus XY-mixer QAOA) found the exact optimum in 15 of 15 runs.
- Per-shot success probability was 5.1–10.0%, against 0.48% for a random valid network.
- The pairwise score tracked the true score with Spearman ρ = 0.987.
- Predicted blur on later aftershocks fell from 2.73 km to 1.50 km.

Known weaknesses that this design must fix:
- the approximate score,
- grid-only candidate sites,
- a single velocity model,
- no human-style baseline,
- one earthquake only,
- predicted rather than tested accuracy.

### Positioning

This is a **proof of concept**. The full pipeline runs end to end on real data, with the quantum step
simulated in Qiskit. No quantum speedup is claimed: with 210 valid networks, classical search finds the
same answer instantly. The contribution is an autonomous, tested pipeline whose decision step is a
quantum optimisation algorithm, evaluated honestly against exact and classical references.

---

## System Overview

### What happens when an earthquake occurs

```
 USGS live feed ──► [1 Trigger] M≥6.5 near stations
                        │ event id, origin, magnitude, focal mechanism
                        ▼
                  [2 Gather] aftershocks so far · permanent stations · memory
                        │
                        ▼
                  [3 Candidates] reachable pool ─► 10 candidates (+ backups)
                        │
                        ▼
                  [4 Score] exact objective over all ≤4-site subsets,
                        │      averaged over velocity models, minus access risk
                        ▼
                  [5 Quantum choose] Dicke(10,4) + XY-mixer QAOA, CVaR objective,
                        │            warm-started angles, Qiskit primitives
                        ▼
                  [6 Self-check] compare with exact optimum ── disagree ──► more layers/shots (max 2 retries)
                        │ agree (or retries exhausted, flagged)
                        ▼
                  [7 Publish] plan.json · map.png · plan.txt (sites, backups, reasons, confidence)
                        │
        ┌───────────────┴──────── every 60 min, up to 72 h ────────────────┐
        ▼                                                                  │
  [8 Monitor] new aftershocks ─► drift? ── no ─────────────────────────────┘
        │ yes
        ▼
  [9 Re-plan] steps 4–7 with a cost per moved sensor ─► "move A→B" or "stay"
        │
        ▼ (sequence ends)
  [10 Remember] angle library · model-ensemble weights · prediction-error record
```

### Planning stages within one earthquake

| Stage | When | Aftershocks used | Purpose |
|---|---|---|---|
| **T0 plan** | Within 5 minutes of trigger | Synthetic, generated from the mainshock (Hardt & Scherbaum 1994) | A first answer before real aftershocks accumulate |
| **Hourly plans** | Every 60 min | Real catalogue events so far (plus synthetic events while fewer than 30 real ones exist) | Refine as data arrives |
| **Re-plan** | When drift is detected | Real events | Recommend moves, priced by a moving cost |

### Where the quantum computer is used

Only in step 5. It decides which 4 of 10 candidate sites to use, at every T0, hourly and re-plan
decision. All other steps are classical: data, physics, candidate generation, scoring, checking,
reporting and memory. The quantum step is the decision-maker, and its output is always checked against
the exact optimum (step 6). How often the quantum step alone finds the optimum is logged and reported
(FR-18).

---

## Functional Requirements

### Trigger and data

- FR-1: The agent MUST poll the USGS real-time GeoJSON feed at least once per minute in live mode
  and start a run for each new event with magnitude ≥ 6.5 that has at least one permanent station within
  100 km of its epicentre (in practice, onshore or near-shore events).
- FR-2: The agent MUST support a **replay mode** that runs any past earthquake as if live, using
  catalogue data up to a simulated clock time and never data after it.
- FR-3: The agent MUST download the aftershocks recorded so far (USGS ComCat FDSN event service, M ≥ 2.5,
  within a radius R = max(50 km, 2 × rupture length) of the epicentre).
- FR-4: The agent MUST download permanent stations within radius R that are operating at the event
  time (FDSN station service).
- FR-5: The agent MUST cache every download with its source URL and retrieval time, so that every
  run can be reproduced offline.

### Candidate sites

- FR-6: The agent MUST build a pool of reachable candidate points:
  - a 2 km grid covering radius R;
  - kept only if within 1.5 km of a road (OpenStreetMap via the Overpass API);
  - not inside water;
  - at least 6 km from any permanent station;
  - at least 3 km from the mapped rupture trace (crew safety).
- FR-7: For each candidate the agent MUST keep up to 3 backup points from the pool, within 3 km and
  passing the same filters.
- FR-8: The agent MUST select the final N = 10 candidates from the pool by greedy spread selection.
  It repeatedly adds the point with the highest single-site score gain, subject to a minimum spacing of
  4 km between selected candidates. (This pre-selection is classical; its effect on the final answer is
  measured in AC-17.)
- FR-9: The team MUST be able to add or exclude candidate points through a config file before or
  during a run.

### Scoring

- FR-10: The score of a network S MUST be the D-criterion averaged over an ensemble of velocity
  models V (default: uniform 5.5, 6.0 and 6.5 km/s, plus one regional layered model where available),
  with weights w_v from memory (equal weights on first use):
  `D(S) = Σ_v w_v Σ_e log det F_e,v(P ∪ S)`
- FR-11: The objective MUST be `f(S) = D(S) − D(∅) − λ_risk Σ_{i∈S} c_i − λ_move · moves(S)`.
  - `c_i` is the access risk of site i: exp(−d_i / 5 km), where d_i is the distance to the nearest aftershock.
  - `moves(S)` is the number of sensors that change site compared with the current plan (0 for a first plan).
- FR-12: The agent MUST compute the **exact** expansion of f over all subsets of up to 4 sites (the
  Möbius coefficients; 385 terms for N = 10). Inside the 4-site subspace the resulting Hamiltonian then
  equals f exactly, with no approximation.
- FR-13: The agent MUST convert the expansion into a Qiskit `SparsePauliOp` with Z, ZZ, ZZZ and ZZZZ
  terms, normalised so that its largest coefficient has magnitude 1.

### Quantum decision step

- FR-14: The agent MUST choose sites with QAOA in Qiskit:
  - initial state: the Dicke state |D(10,4)⟩, prepared with the Bärtschi & Eidenbenz (2019) circuit;
  - each layer: a cost layer exp(−iγH), then an XY ring mixer of XXPlusYYGate in parity order;
  - p layers, with p starting at 3.
- FR-15: Parameters MUST be optimised with COBYLA on the **CVaR-α** of the energy distribution
  (Barkoutsos et al. 2020; α = 0.1), i.e. the mean energy of the best 10% of outcomes, computed exactly
  from the statevector probabilities. The plain mean energy is not used.
- FR-16: The initial angles MUST come from the angle library in memory (median of the stored optimal
  angles for the same N, k and p). If memory is empty, the agent MUST use 4 random restarts.
- FR-17: After optimisation the agent MUST sample 1,024 shots with `StatevectorSampler`. It then
  re-scores the 10 most frequent networks with f and keeps the best.
- FR-18: The agent MUST log, for every quantum decision: p, number of evaluations, P(opt) per shot,
  the rank of the chosen network, and runtime.
- FR-19: The agent MAY run a reduced instance (N = 6, k = 2) on IBM quantum hardware through
  qiskit-ibm-runtime, as a separate demonstration whose results are reported but not used for planning.

### Self-check and publish

- FR-20: The agent MUST compute the exact optimum by enumeration (210 subsets). If the quantum choice
  differs from it, the agent MUST retry with p + 2 layers and 4,096 shots, at most twice. If the quantum
  step still disagrees, the agent MUST publish the exact optimum and flag
  `quantum_agreed = false` in the plan.
- FR-21: The agent MUST publish:
  - `plan.json` (API Contracts);
  - `map.png`, showing aftershocks, permanent stations, candidates, chosen sites and backups;
  - `plan.txt`, a plain-language summary. For each site it gives coordinates, backups, reason (its
    single-site gain and redundancy with the other chosen sites), risk, and expected location
    improvement.
- FR-22: The plan MUST include a confidence level computed from the agent's prediction-error record
  (FR-28): the error of a past plan is |realised score − predicted score| / predicted score, and the level is
  "high" if the median past error is ≤ 25%, "medium" if ≤ 50%, otherwise "low". It is "unrated" when
  there is no record.

### Monitoring and re-planning

- FR-23: After publishing, the agent MUST re-check every 60 minutes for 72 hours.
- FR-24: The agent MUST declare drift when either:
  - the centroid of aftershocks from the last 6 hours has moved more than 5 km from the centroid used
    for the current plan; or
  - the realised score of the current plan on the new aftershocks is more than 20% below its predicted
    score.
- FR-25: On drift, the agent MUST re-plan (steps 4–7) with λ_move > 0 and publish either explicit
  moves ("move sensor from site A to B") or "stay".

### Learning across earthquakes

- FR-26: The agent MUST compare every plan against four reference strategies, all scored with the
  same objective f:
  - exact optimum;
  - greedy forward selection;
  - simulated annealing (Hardt & Scherbaum 1994 style);
  - an **expert rule**: pick sites in turn to minimise the largest azimuthal gap around the aftershock
    centroid, breaking ties by distance to the centroid (closer first). This mirrors the published
    qualitative practice.
- FR-27: At the end of a sequence the agent MUST store, in memory:
  - the optimal QAOA angles for (N, k, p);
  - the realised performance of each velocity model;
  - the predicted and realised plan scores.
- FR-28: The agent MUST update the velocity-model weights w_v in proportion to each model's
  realised accuracy over all past sequences, smoothed by Laplace smoothing with equal priors.
- FR-29: The agent MUST expose a **leave-one-out evaluation** command. It trains the memory on all
  benchmark earthquakes except one, replays the held-out one, and repeats for every earthquake.

---

## Non-Functional Requirements

- NFR-1: Speed: a full plan (steps 2–7, with cached data, N = 10, k = 4, p = 3) MUST finish within
  5 minutes on the reference laptop (Intel i7-1265U, 32 GB RAM).
- NFR-2: Reproducibility: with the same cache, config and seed, two runs MUST produce identical
  plans and metrics.
- NFR-3: Resilience: every network call MUST have a timeout of 30 s and 3 retries with exponential
  backoff. Failures fall back to the cache, or to the behaviour listed under Edge Cases.
- NFR-4: Correctness of the Hamiltonian: the diagonal of H restricted to weight-4 states MUST equal
  the normalised f within 1e-9.
- NFR-5: Constraint safety: no measurement from the main quantum circuit may have Hamming weight
  other than 4.
- NFR-6: Test suite: automated tests MUST run in under 60 s with cached data and no network access.
- NFR-7: No secrets: live and replay modes MUST work without API keys. IBM hardware access (FR-19)
  reads its token from an environment variable and is never committed.
- NFR-8: Honest reporting: every reported metric MUST be produced by a script in the repository
  from cached data. No hand-entered numbers.

---

## Acceptance Criteria

### AC-1: Trigger fires only for qualifying events (FR-1, FR-2)
- **Given** the cached USGS feed for 2019-07-04 to 2019-07-07
- **When** the agent replays it from 2019-07-06 03:00 UTC
- **Then** it starts exactly one run, for the M7.1 Ridgecrest event, and ignores every event below M6.5.

### AC-2: Replay never sees the future (FR-2, FR-5)
- **Given** replay mode at simulated time T
- **When** aftershocks and stations are loaded
- **Then** no event with origin time after T appears in any input, and every download is in the cache with its URL and retrieval time.

### AC-3: Candidates and backups are reachable (FR-6, FR-7)
- **Given** a candidate pool built for Ridgecrest
- **When** candidates and backups are generated
- **Then** every candidate is ≤ 1.5 km from a road, ≥ 6 km from every permanent station and ≥ 3 km from the rupture trace, and every backup is ≤ 3 km from its candidate and passes the same filters.

### AC-4: Team overrides are respected (FR-9)
- **Given** a config that excludes candidate point X and adds point Y
- **When** candidates are generated
- **Then** X never appears and Y is always among the 10 candidates.

### AC-5: Hamiltonian equals the objective exactly (FR-10, FR-11, FR-12, FR-13, NFR-4)
- **Given** any instance, including one with λ_move > 0 and a current plan
- **When** the exact expansion and the SparsePauliOp are built
- **Then** for all 210 four-site networks the Hamiltonian energy equals −f/scale within 1e-9, and the largest coefficient magnitude is 1.

### AC-6: Circuit never leaves 4-site networks (FR-14, NFR-5)
- **Given** the p = 3 circuit with random angles
- **When** its statevector is computed
- **Then** the probability mass outside weight-4 states is below 1e-12.

### AC-7: Higher per-shot success rate (FR-15, FR-16)
- **Given** the Ridgecrest instance and an angle library trained on the other benchmark earthquakes
- **When** QAOA runs with the CVaR objective at p = 3
- **Then** P(opt) per shot is reported. Target: ≥ 20%, twice the proof-of-concept value. Missing the target is reported, not hidden, and does not fail the build.

### AC-8: Sampling and logging (FR-17, FR-18)
- **Given** a finished QAOA optimisation
- **When** the agent samples and decides
- **Then** 1,024 shots are drawn, the 10 most frequent networks are re-scored with f, and the log records p, evaluations, P(opt), chosen rank and runtime.

### AC-9: Self-check falls back safely (FR-20)
- **Given** a quantum result that differs from the exact optimum
- **When** the self-check runs
- **Then** at most two retries occur (p + 2, then p + 4, each with 4,096 shots) and, if they still disagree, the published plan is the exact optimum with quantum_agreed = false.

### AC-10: Plan outputs are complete (FR-21, FR-22)
- **Given** a completed plan
- **When** it is published
- **Then** plan.json validates against the Data Models schema, map.png and plan.txt exist, every site has a reason, risk and backups, and the confidence field is one of the four allowed values.

### AC-11: Monitoring cadence (FR-23)
- **Given** a published plan in replay mode
- **When** 72 simulated hours pass
- **Then** exactly 72 monitoring checks run, one per hour.

### AC-12: Drift triggers a re-plan (FR-24, FR-25)
- **Given** a replay where the 6-hour aftershock centroid moves 8 km
- **When** the next monitoring check runs
- **Then** drift is declared and a re-plan is published with explicit move or stay instructions, priced with λ_move > 0.

### AC-13: T0 plan without real aftershocks (FR-3)
- **Given** replay at T0 + 5 min with no real aftershocks yet
- **When** the agent plans
- **Then** a T0 plan built from synthetic aftershocks is published.

### AC-14: Memory is written and used (FR-27, FR-28)
- **Given** a finished replay sequence
- **When** the agent closes the sequence and a second sequence starts
- **Then** angles.json, model_weights.json and track_record.json contain the new entries, the weights sum to 1, and the second sequence's warm start reads them.

### AC-15: Leave-one-out evaluation table (FR-29)
- **Given** the benchmark set
- **When** leave-one-out evaluation runs
- **Then** a table is produced with one row per earthquake and method, giving objective, rank among the 210 networks, and results of the three robustness tests in the Evaluation Plan.

### AC-16: Honest gain over the expert rule (FR-26)
- **Given** the leave-one-out results
- **When** the evaluation report is generated
- **Then** it states the agent's mean gain over the expert rule in blur (km and %) with the per-earthquake spread, and a negative or negligible gain is reported as such.

### AC-17: Cost of pre-selecting 10 candidates is measured (FR-8)
- **Given** any instance
- **When** the evaluation report is generated
- **Then** it states the gap between the best 4-site network among the 10 pre-selected candidates and the best over the whole pool (computed classically, offline, for this check only).

### AC-18: Hardware demo is isolated (FR-19, NFR-7)
- **Given** the IBM token environment variable is unset
- **When** quakenet hardware-demo runs
- **Then** it exits with a clear message, and no planning command ever calls the hardware.

### AC-19: Plan within 5 minutes (NFR-1)
- **Given** cached Ridgecrest data on the reference laptop
- **When** a full plan runs
- **Then** it completes in under 5 minutes and the timing is logged.

### AC-20: Runs are reproducible (NFR-2)
- **Given** two runs with the same seed, config and cache
- **When** both finish
- **Then** their plan.json files are identical except for timestamps.

### AC-21: Tests run offline and fast (NFR-6, NFR-3)
- **Given** network access disabled
- **When** the test suite runs
- **Then** all tests pass in under 60 s using cached data.

---

## Edge Cases

- EC-1: USGS feed unreachable: retry per NFR-3, log, and keep polling. No run starts without a
  confirmed event.
- EC-2: No real aftershocks yet: use synthetic aftershocks (T0 plan).
- EC-3: Fewer than 30 real aftershocks: blend real and synthetic events.
- EC-4: Epicentre offshore, or fewer than 10 reachable candidates: lower N to the number available
  (minimum 6) and state it in the plan. Below 6 candidates, publish "insufficient reachable sites" and
  stop.
- EC-5: Overpass API unavailable: build candidates from the grid only, mark
  `feasibility_checked = false` and show a prominent warning in `plan.txt`.
- EC-6: No focal mechanism available yet: generate synthetic aftershocks on both nodal planes. If
  there is still none, use a circular cloud with radius equal to half the rupture length.
- EC-7: The mainshock magnitude is revised by USGS: if the change is ≥ 0.3, re-run from step 2.
- EC-8: A second qualifying event within radius R during monitoring: merge it into the same
  sequence and declare drift.
- EC-9: Quantum step disagrees after retries: handled by FR-20.
- EC-10: Memory empty (first ever run): random restarts, equal model weights, confidence "unrated".
- EC-11: A requested k ≥ N, or k < 1: reject with a clear error message.

---

## API Contracts

**Version 2:** the agent runs behind a web API; the endpoints, JSON shapes, error codes and the fixed internal interfaces are in `docs/API.md`, which replaces the command line and module sketches below. They are kept as the original design.

### Command line

```
quakenet live                         # poll USGS feed, act on qualifying events
quakenet replay <event_id> [--until ISO_TIME] [--hours 72]
quakenet plan <event_id> --at ISO_TIME          # single plan, no monitoring
quakenet evaluate --leave-one-out               # FR-29
quakenet hardware-demo                          # FR-19, optional
```

### Module interfaces (Python, typed)

```python
class EventSource(Protocol):
    def new_events(self, since: datetime) -> list[Mainshock]: ...
    def aftershocks(self, ev: Mainshock, until: datetime) -> list[Hypocentre]: ...
    def stations(self, ev: Mainshock) -> list[Station]: ...

def build_candidates(ev: Mainshock, quakes: list[Hypocentre], stations: list[Station],
                     cfg: CandidateConfig) -> list[Candidate]: ...           # FR-6..9
def objective_terms(cands: list[Candidate], quakes: list[Hypocentre], stations: list[Station],
                    models: list[VelocityModel], weights: list[float],
                    current: tuple[int, ...] | None, cfg: ObjectiveConfig) -> Expansion: ...   # FR-10..12
def to_hamiltonian(exp: Expansion) -> tuple[SparsePauliOp, float]: ...       # FR-13
def quantum_choose(h: SparsePauliOp, n: int, k: int, warm: AngleSet | None,
                   cfg: QaoaConfig) -> QuantumResult: ...                     # FR-14..18
def self_check(exp: Expansion, q: QuantumResult, cfg: QaoaConfig) -> Decision: ...  # FR-20
def publish(plan: Plan, out_dir: Path) -> None: ...                           # FR-21
def detect_drift(plan: Plan, new_quakes: list[Hypocentre]) -> DriftReport: ...  # FR-24
```

### Error contract

All public functions raise `QuakeNetError(code: str, message: str)`. The codes are:
`FEED_UNAVAILABLE`, `NO_STATIONS`, `INSUFFICIENT_SITES`, `INVALID_K`, `CACHE_MISS`.

---

## Data Models

**Plan** (`plan.json`)

| Field | Type | Constraint |
|---|---|---|
| event_id | str | USGS id |
| stage | str | "T0", "hourly" or "replan" |
| created_utc | str | ISO 8601 |
| sites | list[Site] | length = k |
| moves | list[{from: int, to: int}] | empty unless stage = "replan" |
| objective | float | value of f |
| exact_rank | int | 1 = optimum |
| quantum_agreed | bool | FR-20 |
| p_opt_per_shot | float | 0 to 1 |
| expected_blur_km | float | > 0 |
| expert_rule_blur_km | float | > 0 |
| confidence | str | "high", "medium", "low" or "unrated" |
| feasibility_checked | bool | EC-5 |

**Site:** id, lat, lon, reason (str), single_gain (float), risk (0–1), backups (list of {lat, lon}).

**Memory** (`memory/*.json`)

| File | Content |
|---|---|
| angles.json | {"N-k-p": list of optimal (γ, β) vectors} |
| model_weights.json | {model_name: weight}, summing to 1 |
| track_record.json | list of {event_id, stage, predicted_score, realised_score} |

---

## Evaluation Plan

### Benchmark earthquakes (to be confirmed by a data-quality check, R-2)

| Earthquake | M | Region | Why |
|---|---|---|---|
| Ridgecrest 2019 | 7.1 | California | Proof-of-concept case; known USGS rapid deployment |
| South Napa 2014 | 6.0 | California | Dense network, different fault style |
| Monte Cristo Range 2020 | 6.5 | Nevada | Sparse network, which is where scarcity matters |
| Anchorage 2018 | 7.1 | Alaska | Deep event, different geometry |
| Ferndale 2022 | 6.4 | California | Near the coast, with limited reachable land |
| Puerto Rico 2020 | 6.4 | Caribbean | Island setting, different network |

### Robustness tests used in the evaluation (AC-15)

1. **Held-out aftershocks:** blur measured on aftershocks after the planning time.
2. **Model mismatch:** travel times generated with a layered regional model plus 0.1 s noise, then
   located with the agent's ensemble using the chosen network. The measured error is reported in km.
   This is the closest test to "real" error possible for stations that were never installed.
3. **Real deployment comparison** (where station metadata exist, R-3): the agent's network against the
   stations the field team actually installed, both scored on the same held-out aftershocks.

---

## Out of Scope

- OS-1: Placing large nodal arrays (hundreds of sensors). The agent targets the first k ≤ 6
  real-time instruments.
- OS-2: Processing seismometer data (picking, locating with real waveforms). Existing ML pickers do this.
- OS-3: Goals other than location accuracy: fault imaging, strong-motion recording, site response.
- OS-4: Field logistics: travel routing, crew scheduling, permits.
- OS-5: Claims of quantum speedup, or quantum hardware at planning scale. Hardware appears only as the
  FR-19 demonstration.
- OS-6: Notifying real agencies. Outputs are shown on the team's web console and stored on the team laptop.
- OS-7: Earthquakes outside regions covered by USGS ComCat at M ≥ 2.5.

---

## Architecture

**Version 2:** the same modular monolith, laid out as `src/` (science), `src/agent/` (the agent), `api/` (FastAPI) and `web/` (Next.js console). `docs/ARCHITECTURE.md` describes hosting and security.

**Style: modular monolith in one Python package (`quakenet/`).** A small team, one runtime and a
batch-style loop do not justify services. Every module is pure and testable except `sources`
(network) and `memory` (files), which sit behind interfaces so replay and tests can substitute cached
versions.

| Module | Responsibility | Depends on |
|---|---|---|
| `sources` | USGS feed, ComCat, FDSN stations, Overpass; caching | network, cache |
| `synthetic` | Aftershock generation from the mainshock (Wells & Coppersmith 1994 rupture length, focal planes) | — |
| `candidates` | Pool, filters, backups, spread selection | sources (roads) |
| `physics` | Velocity models, Fisher matrices, blur | — |
| `objective` | Exact expansion of f | physics |
| `quantum` | Dicke state, XY mixer, cost layer, CVaR-COBYLA, sampling (Qiskit only here) | objective |
| `baselines` | Exact, greedy, annealing, expert rule | objective |
| `agent` | Orchestrates stages, self-check, drift, re-plan | all above |
| `memory` | Angle library, model weights, track record | files |
| `report` | plan.json, map.png, plan.txt, evaluation tables | agent outputs |
| `cli` | Commands in API Contracts | agent |

**Boundary conditions.** This design holds while N ≤ 12 (exact enumeration and exact expansion stay
cheap). Above that, the exact expansion grows combinatorially, so the objective must fall back to
second- or third-order terms, and the self-check must use classical heuristics instead of enumeration.
The `objective` and `self_check` interfaces are designed to allow that change without touching the
`quantum` or `agent` modules.

**Trade-offs accepted.**
- Statevector simulation limits N to about 25.
- A deeper cost layer, with 4-body terms, makes hardware execution unrealistic.
- The pre-selection to 10 candidates is classical, and its effect is measured (AC-17) instead of
  assumed away.

---

## Risks and Open Checks

- R-1: Verify what the AuScope Network Design App and SN-CAST can do (inputs, live data, automation)
  before claiming the gap. This affects the problem statement. **Done; problem statement changed (decision 11).**
- R-2: Confirm that each benchmark earthquake has enough M ≥ 2.5 aftershocks in the first 12 h and
  accessible station metadata. Replace any that fail. **Done; South Napa 2014 has too few later aftershocks and is skipped.**
- R-3: Find station metadata for real temporary deployments (for example, the USGS Ridgecrest 2019
  network). Without it, robustness test 3 is dropped and the report says so.
- R-4: Verify that USGS event pages provide focal mechanisms quickly enough for T0 plans. Otherwise
  EC-6 applies.
- R-5: Verify the claim that nodal sensors typically do not transmit in real time, with sources,
  before it appears in the pitch.
- R-6: CVaR plus warm start may not reach the 20% P(opt) target. The report states whatever is achieved.
  **Happened: best was about 10% per measurement.**

---

## References

- Bärtschi & Eidenbenz (2019), deterministic Dicke-state preparation, FCT 2019.
- Barkoutsos et al. (2020), "Improving Variational Quantum Optimization using CVaR", *Quantum* 4, 256.
- Cochran et al. (2020), *SRL* 91, 1952–1960.
- Hadfield et al. (2019), *Algorithms* 12(2), 34.
- Hardt & Scherbaum (1994), *GJI* 117(3), 716–726.
- Kijko (1977), *Pure Appl. Geophys.* 115, 999–1009.
- Rabinowitz & Steinberg (1990), *BSSA* 80(1), 187–196.
- Toledo et al. (2020), *JVGR* 391, 106433.
- Wells & Coppersmith (1994), *BSSA* 84(4), 974–1002.
- Further sources: `research/seismo-placement/sources/`.
