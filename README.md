# QuakeNet-Q

**Hybrid quantum–classical placement of portable seismometers after a major earthquake.**
Qiskit Fall Fest 2026 Hackathon · Domain: **Disaster Response**

After a big earthquake, response teams rush a few portable seismometers into the field. Where they
put them decides how sharply the aftershocks can be located, and published deployment reports
describe that choice as expert judgement under time pressure. QuakeNet-Q treats it as an
optimisation problem: **choose 4 of 10 candidate sites** to make aftershock locations as sharp as
possible while avoiding redundant sensors and sites that are risky for crews to reach. A
constraint-preserving QAOA circuit in Qiskit makes the choice, and everything is checked against
exhaustive search on **real data from the 2019 Ridgecrest (California) M7.1 earthquake**.

![Map of the instance and the chosen sites](figures/map.png)

## Results at a glance

All numbers come from `python run_experiment.py` (`results/results.json`).

| Question | Answer |
|---|---|
| Does the placement help? | In a simulated location test on **217 later aftershocks** the planner never saw, the mean location error falls from **3.00 km** (no new sensors) to **2.31 km** with the chosen sites. A field rule that closes the largest azimuthal gap gives 2.63 km; the average of all 210 networks gives 2.60 km. Our pick ranks 4th of 210 in that test. |
| Is the quantum answer correct? | Yes. In 15 of 15 runs the hybrid QAOA returned sites **{1, 3, 4, 7}**, the exact optimum found by brute force over all 210 networks. |
| Does the quantum circuit do real work? | It raises the chance that one measurement gives the best network from 0.48% (random valid network) to **5.1%** with 1 layer, **8.3%** with 2 and **11.0%** with 3. Our target was 20%; we did not reach it. |
| Is the circuit's score the real score? | Yes. The circuit encodes the exact D-optimality score (385 terms with up to 4-site interactions), with zero error on all 210 networks. The usual pairwise approximation ranks well (ρ = 0.987) but picks only the 2nd-best network at risk weight λ = 300. |
| Does it beat classical methods? | **No.** Greedy, backward elimination and simulated annealing also find the optimum, and brute force takes milliseconds at this size. We claim no quantum speedup. |

![Location error on later aftershocks](figures/location_test.png)

## The problem

- **Users:** rapid-response seismology teams (e.g. USGS, INGV, GFZ) and the emergency managers who use their aftershock maps.
- **Limited resource:** 4 portable instruments.
- **Competing objectives:** location accuracy vs. sensor redundancy vs. access risk for field crews. The most informative sites sit on the active rupture, which is also the hardest place to work.

### Formulation

| Item | Definition |
|---|---|
| Variables | `x_i ∈ {0,1}`, 1 if a sensor goes to candidate site `i` (10 sites → 10 qubits) |
| Constraint | `Σ x_i = 4` (enforced by the circuit, not by a penalty) |
| True score | `D(S) = Σ_events log det F_e(S)`, the D-optimality criterion: `F_e` is the Fisher information of an aftershock's location (x, y, depth, origin time) given the permanent stations plus the chosen sites |
| Circuit objective | `f(x) = Σ_{|T|≤4} w_T Π_{i∈T} x_i − λ Σ_i c_i x_i`: the inclusion–exclusion (Möbius) expansion of `D`, exact on every 4-site network. `w_{i}` = information from site `i` alone, `w_{ij}` = pair interaction (negative when two sites are redundant), and so on up to groups of 4; `c_i` = access risk, λ = 150 |
| Test instance | 550 M≥3 aftershocks from the first 12 h (planning), 217 later aftershocks (testing), 14 permanent stations, 10 candidate sites, 210 allowed networks |

The log-determinant is not quadratic. Because the circuit only holds 4-site networks, terms up to
4 sites reproduce it exactly: 385 terms, which become Z, ZZ, ZZZ and ZZZZ terms in the Hamiltonian
(about 3,000 gates per layer, against about 900 for the pairwise version). We chose exactness and
measured the cost.

### Why this quantum algorithm

QAOA is the standard near-term algorithm for this kind of yes/no selection problem. The usual way to handle "exactly 4
sites" is a penalty term, which wastes probability on invalid answers and needs a hand-tuned
weight. We instead start in a **Dicke state** (an equal mix of all 210 valid networks) and use an
**XY ring mixer**, which only swaps a chosen site with an unchosen one. The circuit can never leave
the valid networks. Our penalty-based ablation confirms the difference: it produces a valid
4-site answer only 52–73% of the time and finds the optimum less often than random guessing
(with one untuned penalty weight, so a tuned penalty could do better).

![Architecture](figures/architecture.png)

## Run it

Requires Python 3.10+.

```bash
pip install -r requirements.txt
python -m pytest tests -q          # 163 checks, about 25 s
python run_experiment.py --quick   # 1 seed, p = 1: under a minute
python run_experiment.py           # full run: about 45 minutes
```

Outputs: `results/results.json` and the figures in `figures/` (the quick run writes
`results/results_quick.json` and `figures_quick/` so it never overwrites the full results). The data is cached in `data/`, so
no internet is needed. `python data/fetch_data.py` re-downloads it from USGS and IRIS.

## Repository layout

| Path | Purpose |
|---|---|
| `data/fetch_data.py`, `data/*.json` | Download and cache of USGS aftershocks and IRIS station locations |
| `src/geometry.py` | Instance, travel-time physics, D-criterion, blur metric |
| `src/qubo.py` | Exact objective (terms up to 4 sites), pairwise QUBO, Hamiltonian |
| `src/location.py` | Independent simulated location test |
| `src/sources.py`, `src/candidates.py` | Outbound data gateway; candidate sites from roads and terrain |
| `src/qaoa_solver.py` | Dicke state, XY mixer, QAOA circuits, COBYLA loop, sampling |
| `src/baselines.py` | Brute force, greedy, backward elimination, simulated annealing, expert rule, random |
| `api/` | FastAPI backend (runs on the team laptop) |
| `web/` | Next.js test console, deployed on Vercel |
| `docs/` | Architecture, API contract, decisions, design spec |
| `run_experiment.py` | End-to-end experiment and figures |
| `tests/` | Checks of the formulation and the circuit |
| `report/` | Report (.docx), its build script and the diagram script |
| `research/` | Notes on every source we consulted |
| `VIDEO_SCRIPT.md` | 3-minute pitch script |

## Limitations

- **No quantum advantage.** 210 networks can be enumerated instantly and simple classical heuristics find the optimum.
- **The exact objective does not scale.** It needs 385 terms for 4 of 10 sites, and the count grows fast with more sensors.
- **Below our success target.** The best network comes up in 5–11% of measurements, not the 20% we aimed for.
- **The location test is simulated** with the same simple physics (different wave speed, added noise), not real recordings.
- **Simplified physics:** uniform 6 km/s velocity, P arrivals only, 0.1 s picking error, flat earth.
- **Synthetic parts:** candidate sites come from a grid rule and access risk from a distance-to-rupture rule (`exp(−d / 5 km)`). Real deployments would use road, permit and safety data.
- **Noise-free simulation only.** The XY circuit is deep (depth about 2,300 to 6,300 for 1 to 3 layers, against 54–118 for the penalty circuit), so it would suffer on today's hardware.
- **The "siting is manual" claim** rests on published deployment reports, not interviews with practitioners, and "no prior quantum work" means our searches found none.

## Credits

Code in this repository was written for this hackathon, with AI assistance (Claude Code). Ideas we build on:

- Rabinowitz & Steinberg (1990), *BSSA* 80(1), 187–196: D-optimal seismic network design.
- Hardt & Scherbaum (1994), *Geophys. J. Int.* 117(3), 716–726: optimum aftershock networks by simulated annealing.
- Toledo, Jousset, Maurer & Krawczyk (2020), *J. Volcanol. Geotherm. Res.* 391, 106433: D-criterion with sequential station elimination.
- Cochran et al. (2020), *Seismol. Res. Lett.* 91, 1952–1960: the USGS rapid deployment at Ridgecrest.
- Hadfield et al. (2019), *Algorithms* 12(2), 34: Quantum Alternating Operator Ansatz (XY mixers).
- Bärtschi & Eidenbenz (2019), *FCT 2019*: deterministic Dicke-state preparation (implemented in `dicke_state` from the paper's description).
- San Martín et al., arXiv:2305.08738: QAOA sensor placement on civil structures with XY mixer and Dicke state.
- Farhi, Goldstone & Gutmann (2014), arXiv:1411.4028: QAOA.

Data: U.S. Geological Survey ComCat earthquake catalogue (public domain); station metadata from the
EarthScope/IRIS FDSN service, Southern California Seismic Network (CI).
