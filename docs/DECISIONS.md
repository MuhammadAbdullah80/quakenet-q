# QuakeNet-Q: Decision Log

Newest first. "Status" says whether the decision is reflected in the spec or code yet.

| # | Date | Decision | Why | Status |
|---|---|---|---|---|
| 32 | 2026-11-12 | Frontend unit tests use Node's built-in test runner (`npm test` in `web/`), not Jest or Vitest | Node 24 runs TypeScript directly, so pure helpers can be tested with no new dependency | In code |
| 31 | 2026-11-12 | Accent text colour is `#3d6e0c`, not the brief's `#4f8a12` | `#4f8a12` is 3.51:1 on the mist background and fails WCAG AA for normal text; `#3d6e0c` is 5.08:1. Lime `#c6f35c` stays for marks and fills | In code |
| 30 | 2026-11-12 | Drift and the track-record error are measured relative to the predicted information gain, not the net score | The net score (information minus risk cost) can be near zero, which made one error read 988% and could trigger false re-plans; the risk cost is the same on both sides, so the information gain is the right scale | In code |
| 29 | 2026-11-12 | While tuning with CVaR, compute the circuit's output with our own exact simulator (`XYQaoaSimulator`); final measurements still run the Qiskit circuit on StatevectorSampler | CVaR needs the full distribution at every step; the simulator is the same circuit, checked against Qiskit's Statevector in the tests, and makes a plan take seconds instead of minutes | In code |
| 28 | 2026-11-12 | In the benchmark, rescale the energies of the allowed networks to span 3 units before tuning | At the objective's own scale the useful angles were near 10, which random starts never reached; a constant factor changes only the angle scale | In code (benchmark) |
| 27 | 2026-11-12 | CVaR with alpha = 0.1 | Picked after a trial on two earthquakes; raised the share of runs whose final pick was exact from 8/15 to 14/15 (cold start) | In code |
| 26 | 2026-11-12 | Hearing range: Hutton & Boore (1987) attenuation, assumed rural noise 0.03 mm, P wave 0.2 of the peak, readings below signal-to-noise 5 dropped, timing error 0.1 s × max(1, 10/SNR) | Implements decision 16 with stated, simple constants; they are assumptions, not measurements | In code |
| 25 | 2026-11-12 | Frontend on Vercel; backend on the team laptop, reached through a secure tunnel with a shared secret. Replaces decision 24 | Team decision. Avoids Vercel's limits on run time, scheduling and storage for Qiskit; costs nothing; the laptop already has Tailscale. Cost: live features need the laptop on | In `ARCHITECTURE.md`; not in spec |
| 24 | 2026-11-12 | ~~Host on Vercel if its limits allow~~; otherwise frontend on Vercel and the Python API elsewhere | Team preference; Qiskit run time, scheduling and storage limits are still to verify | In `ARCHITECTURE.md`; not in spec |
| 23 | 2026-11-12 | No AI or LLM features anywhere in the app | Team decision: this is a quantum optimisation project, not a chatbot. The AI-layer design written earlier the same day is withdrawn | Docs updated |
| 22 | 2026-11-12 | Design for multiple geo-based servers, but run a single server for the MVP | Multi-region is costly and not needed for the hackathon; a `region` field and a stateless API keep the door open | In `ARCHITECTURE.md`; not in spec |
| 21 | 2026-11-12 | Frontend is a Next.js test console with one page per module; polish comes later | Every module must be testable by hand; server rendering keeps keys off the browser | In `ARCHITECTURE.md`; not in spec |
| 20 | 2026-11-12 | ~~The AI layer explains plans and never chooses sites~~ | Withdrawn by decision 23 | Withdrawn |
| 19 | 2026-11-12 | All external calls go through one gateway with per-host limits, cache, retries and a circuit breaker | Respect provider limits; survive outages | In `ARCHITECTURE.md`; not in spec |
| 18 | 2026-11-12 | Add the DN score next to the D-criterion; held-out data picks the planner | Bloem et al. (2020) found DN best for source location, but the evidence is from one research group and DN can fail on clustered quakes | Decided; not in spec |
| 17 | 2026-11-12 | Validate top layouts with a slower information-gain estimate (NMC) | Guards against DN's weak spot, as Strutz & Curtis do | Decided; not in spec |
| 16 | 2026-11-12 | Timing error depends on signal-to-noise; stations below SNR 5 do not count | A constant error overvalues distant sites (NetOpt3D's approach, simplified) | In code (opt-in, `hearing_range` setting) |
| 15 | 2026-11-12 | Add a slope under 20° filter using key-free AWS Terrain Tiles | Steep sites are unusable; OpenTopography needs a key | In code (candidate pools) |
| 14 | 2026-11-12 | Write DN ourselves; use WoWED-volcano only as a cross-check | It is GPL-3.0; copying would force our project under the same licence | Decided; not in spec |
| 13 | 2026-11-12 | Keep exhaustive checking plus QAOA; no genetic algorithm or annealing as the main search | Exact at 210 options; the others are approximations | No change needed |
| 12 | 2026-11-12 | No 3D wave paths | Needs 3D Earth models and heavy solvers; stated as a limitation | Decided; not in spec |
| 11 | 2026-11-12 | Problem statement changes from "no tool exists" to "no tool is built for aftershocks, starts itself, or re-plans" | SENSI, SN-CAST, NetOpt3D and Strutz & Curtis exist for planning ahead | Decided; not in spec |
| 10 | 2026-11-12 | Stay at 4 sensors from 10 sites | Proof of concept; every answer can be verified; the score can be made exact | In spec |
| 9 | 2026-11-12 | Position the project as a proof of concept with no speedup claim | True at this size, and the brief rewards honesty | In spec |
| 8 | 2026-11-12 | If the quantum step still disagrees after two retries, publish the exact optimum and flag it | Output is always correct; the quantum track record stays honest | In spec |
| 7 | 2026-11-12 | Train the circuit on CVaR with warm-started angles; target 20% success per shot | Raises per-shot success; missing the target is reported, not hidden | In spec |
| 6 | 2026-11-12 | Exact score: include all terms up to groups of four sites | Removes the "only an approximation" weakness for a 4-sensor choice | In spec |
| 5 | 2026-11-12 | Plan within minutes from simulated aftershocks, then refine hourly | Gives an answer before real aftershocks accumulate (Hardt & Scherbaum 1994) | In spec |
| 4 | 2026-11-12 | Build an autonomous agent with monitoring and memory, not a one-off tool | Team direction; closes the "no tool, no time in a crisis" gap | In spec |
| 3 | 2026-11-12 | Enforce "exactly k sites" with a Dicke state and XY mixer, not a penalty | Every measurement is valid; our penalty test did worse than random | In code |
| 2 | 2026-11-12 | Use real Ridgecrest 2019 data and test on later aftershocks | Evidence the problem and the result are real | In code |
| 1 | 2026-11-12 | Project: quantum placement of portable seismometers after an earthquake (Disaster Response) | Original, real, checkable against exact answers | In code |

## Corrections made along the way

- The mutual-information QUBO paper (arXiv 2407.14747) was first described as a ready recipe. It is
  quadratic only for 3 sensors, so it was dropped in favour of the San Martín et al. pattern.
- "No tool exists" was claimed before the related tools were checked. Decision 11 corrects it.
- An AI-layer section was written into the architecture from a conditional remark ("if you are using any
  AI layer"). No AI layer was ever in the spec, and the team does not want one. Decision 23 removes it.
- "2.73 km → 1.50 km" is a model prediction on later aftershocks, not a measured location error.
