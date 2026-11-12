# Benchmark earthquakes: QAOA variants and the location test

Generated 2026-11-12T16:20:28Z by `run_benchmarks.py` in 11.0 minutes. Every number below comes from that run (`results/benchmarks.json`), on data cached in `data/cache/`.

## Set-up

- Plan at hour 12 after the mainshock, 10 candidate sites, choose 4; risk weight 150. Real aftershocks (M >= 2.5) known by then; topped up with synthetic ones when fewer than 30 exist.
- Candidates: greedy spread selection on single-site gain from the road-checked pool (Ridgecrest: the 10 published sites).
- QAOA: Dicke state + XY ring mixer, 3 layers, 1024 shots, COBYLA up to 400 evaluations per start. Energies of the allowed networks rescaled to span 3 units before tuning (a constant factor; it changes the angle scale only). Cold starts use 10 random starts per seed, seeds [0, 1, 2]; warm starts use only the median of the best angles found on the other earthquakes (leave-one-out). CVaR uses alpha = 0.1 (the mean energy of the best 10% of the outcomes); the mean objective is computed exactly as CVaR with alpha = 1.
- **P(best)** is the chance that one measurement gives the exact best network, read from the exact output distribution of the tuned circuit. The target (decision 7) is 20%. A random valid network has 1/210 = 0.48%.
- **Final pick**: the best of the 10 most frequent sampled networks, re-scored with the true objective.
- **Location test**: the later aftershocks (12 h to 7 days) are located with each network in a simulation (true wave speed 5.8 km/s, planner assumes 6.0). *Plain*: every station hears every event with a 0.1 s picking error. *Hearing range*: a station whose simulated signal-to-noise is under 5 gives no reading and weak readings are noisier (a simplified attenuation law with an assumed noise level; see `src/geometry.py`). With hearing range, events that some network cannot locate are left out of every mean, so all networks are compared on the same events.
- **Gain over the expert rule** = expert-rule error minus the network's error (positive = better than the expert rule). These are simulated errors, not measured ones.

## Summary

| Earthquake | P(best) mean-cold | P(best) cvar-cold | P(best) mean-warm | P(best) cvar-warm | Final pick exact? (runs; mc / cc / mw / cw) | Exact optimum: gain over expert, plain | with hearing range |
|---|---|---|---|---|---|---|---|
| Ridgecrest 2019 | 3.8% | 9.6% | 7.1% | 9.6% | 3/3 / 3/3 / 3/3 / 3/3 | 0.10 km (2.4%) | 0.09 km (2.7%) |
| South Napa 2014 | skipped: only 9 later aftershocks (M >= 2.5, 12 h to 7 days) to test on; at least 10 needed | | | | | | |
| Monte Cristo Range 2020 | 1.2% | 7.3% | 1.4% | 3.1% | 0/3 / 3/3 / 0/3 / 3/3 | -0.00 km (-0.1%) | -0.01 km (-0.3%) |
| Anchorage 2018 | 0.4% | 1.6% | 0.4% | 1.3% | 0/3 / 2/3 / 0/3 / 0/3 | -0.03 km (-0.7%) | -0.01 km (-0.0%) |
| Ferndale 2022 | 6.0% | 7.0% | 6.0% | 10.0% | 3/3 / 3/3 / 3/3 / 3/3 | -0.07 km (-2.9%) | -0.04 km (-1.6%) |
| Puerto Rico 2020 | 6.2% | 8.2% | 1.2% | 10.2% | 2/3 / 3/3 / 0/3 / 3/3 | -0.39 km (-15.8%) | -0.37 km (-15.6%) |

## Per earthquake

### Ridgecrest 2019 (ridgecrest2019)

- Planning events: 1056 (1056 real by hour 12); later aftershocks for the test: 744; permanent stations: 54; pool: 2110 points, road-checked: yes.
- Exact optimum: sites [1, 3, 4, 7] (objective 407.7). Largest error of the expanded objective over all 210 networks: 0.00e+00 (it is exact).

| QAOA variant | Seed | P(best) | vs 20% target | Valid outcomes | Most likely = best? | Final pick | Rank | Exact? | Evaluations | Seconds |
|---|---|---|---|---|---|---|---|---|---|---|
| mean-cold | 0 | 4.0% | missed | 1.000 | no | [1, 3, 4, 7] | 1 | yes | 3953 | 17.0 |
| mean-cold | 1 | 4.0% | missed | 1.000 | no | [1, 3, 4, 7] | 1 | yes | 4000 | 20.1 |
| mean-cold | 2 | 3.6% | missed | 1.000 | no | [1, 3, 4, 7] | 1 | yes | 4000 | 16.9 |
| cvar-cold | 0 | 9.6% | missed | 1.000 | yes | [1, 3, 4, 7] | 1 | yes | 3729 | 14.4 |
| cvar-cold | 1 | 9.6% | missed | 1.000 | yes | [1, 3, 4, 7] | 1 | yes | 3584 | 8.0 |
| cvar-cold | 2 | 9.6% | missed | 1.000 | yes | [1, 3, 4, 7] | 1 | yes | 3869 | 17.3 |
| mean-warm | 0 | 7.1% | missed | 1.000 | no | [1, 3, 4, 7] | 1 | yes | 400 | 3.1 |
| mean-warm | 1 | 7.1% | missed | 1.000 | no | [1, 3, 4, 7] | 1 | yes | 400 | 5.2 |
| mean-warm | 2 | 7.1% | missed | 1.000 | no | [1, 3, 4, 7] | 1 | yes | 400 | 5.0 |
| cvar-warm | 0 | 9.6% | missed | 1.000 | yes | [1, 3, 4, 7] | 1 | yes | 379 | 4.8 |
| cvar-warm | 1 | 9.6% | missed | 1.000 | yes | [1, 3, 4, 7] | 1 | yes | 379 | 5.0 |
| cvar-warm | 2 | 9.6% | missed | 1.000 | yes | [1, 3, 4, 7] | 1 | yes | 379 | 4.8 |

Location test (744 later aftershocks; with hearing range, 744 events are located by every network):

| Network | Sites | Rank | Mean error, plain (km) | Gain over expert, plain | Mean error, hearing (km) | Gain over expert, hearing | Not locatable (hearing) |
|---|---|---|---|---|---|---|---|
| exact | [1, 3, 4, 7] | 1 | 4.19 | +0.10 km (+2.4%) | 3.17 | +0.09 km (+2.7%) | 0 |
| expert_rule | [0, 2, 4, 5] | 53 | 4.29 | - | 3.26 | - | 0 |
| greedy | [1, 3, 4, 7] | 1 | 4.19 | +0.10 km (+2.4%) | 3.17 | +0.09 km (+2.7%) | 0 |
| no_new_sensors | [] | - | 4.69 | - | 3.67 | - | 0 |
| qaoa_mean-cold | [1, 3, 4, 7] | 1 | 4.19 | +0.10 km (+2.4%) | 3.17 | +0.09 km (+2.7%) | 0 |
| qaoa_cvar-cold | [1, 3, 4, 7] | 1 | 4.19 | +0.10 km (+2.4%) | 3.17 | +0.09 km (+2.7%) | 0 |
| qaoa_mean-warm | [1, 3, 4, 7] | 1 | 4.19 | +0.10 km (+2.4%) | 3.17 | +0.09 km (+2.7%) | 0 |
| qaoa_cvar-warm | [1, 3, 4, 7] | 1 | 4.19 | +0.10 km (+2.4%) | 3.17 | +0.09 km (+2.7%) | 0 |

### South Napa 2014 (southnapa2014)

**Skipped:** only 9 later aftershocks (M >= 2.5, 12 h to 7 days) to test on; at least 10 needed.

Data: 5 real aftershocks by hour 12, 9 later; 187 permanent stations; pool 335 points.

### Monte Cristo Range 2020 (montecristo2020)

- Planning events: 161 (161 real by hour 12); later aftershocks for the test: 410; permanent stations: 18; pool: 657 points, road-checked: yes.
- Exact optimum: sites [0, 1, 6, 9] (objective 397.5). Largest error of the expanded objective over all 210 networks: 0.00e+00 (it is exact).

| QAOA variant | Seed | P(best) | vs 20% target | Valid outcomes | Most likely = best? | Final pick | Rank | Exact? | Evaluations | Seconds |
|---|---|---|---|---|---|---|---|---|---|---|
| mean-cold | 0 | 1.4% | missed | 1.000 | no | [1, 2, 6, 9] | 2 | **no** | 4000 | 17.3 |
| mean-cold | 1 | 0.9% | missed | 1.000 | no | [1, 2, 6, 9] | 2 | **no** | 4000 | 17.9 |
| mean-cold | 2 | 1.3% | missed | 1.000 | no | [1, 2, 6, 9] | 2 | **no** | 4000 | 16.2 |
| cvar-cold | 0 | 8.4% | missed | 1.000 | yes | [0, 1, 6, 9] | 1 | yes | 3777 | 13.0 |
| cvar-cold | 1 | 6.7% | missed | 1.000 | yes | [0, 1, 6, 9] | 1 | yes | 3677 | 12.6 |
| cvar-cold | 2 | 6.7% | missed | 1.000 | yes | [0, 1, 6, 9] | 1 | yes | 3736 | 15.0 |
| mean-warm | 0 | 1.4% | missed | 1.000 | no | [1, 2, 6, 9] | 2 | **no** | 400 | 5.1 |
| mean-warm | 1 | 1.4% | missed | 1.000 | no | [1, 2, 6, 9] | 2 | **no** | 400 | 5.0 |
| mean-warm | 2 | 1.4% | missed | 1.000 | no | [1, 2, 6, 9] | 2 | **no** | 400 | 4.2 |
| cvar-warm | 0 | 3.1% | missed | 1.000 | no | [0, 1, 6, 9] | 1 | yes | 160 | 2.2 |
| cvar-warm | 1 | 3.1% | missed | 1.000 | no | [0, 1, 6, 9] | 1 | yes | 160 | 2.0 |
| cvar-warm | 2 | 3.1% | missed | 1.000 | no | [0, 1, 6, 9] | 1 | yes | 160 | 3.4 |

Location test (410 later aftershocks; with hearing range, 410 events are located by every network):

| Network | Sites | Rank | Mean error, plain (km) | Gain over expert, plain | Mean error, hearing (km) | Gain over expert, hearing | Not locatable (hearing) |
|---|---|---|---|---|---|---|---|
| exact | [0, 1, 6, 9] | 1 | 2.69 | -0.00 km (-0.1%) | 2.60 | -0.01 km (-0.3%) | 0 |
| expert_rule | [0, 1, 2, 9] | 43 | 2.69 | - | 2.60 | - | 0 |
| greedy | [0, 1, 6, 9] | 1 | 2.69 | -0.00 km (-0.1%) | 2.60 | -0.01 km (-0.3%) | 0 |
| no_new_sensors | [] | - | 5.16 | - | 5.20 | - | 0 |
| qaoa_mean-cold | [1, 2, 6, 9] | 2 | 2.69 | +0.00 km (+0.0%) | 2.61 | -0.01 km (-0.5%) | 0 |
| qaoa_cvar-cold | [0, 1, 6, 9] | 1 | 2.69 | -0.00 km (-0.1%) | 2.60 | -0.01 km (-0.3%) | 0 |
| qaoa_mean-warm | [1, 2, 6, 9] | 2 | 2.69 | +0.00 km (+0.0%) | 2.61 | -0.01 km (-0.5%) | 0 |
| qaoa_cvar-warm | [0, 1, 6, 9] | 1 | 2.69 | -0.00 km (-0.1%) | 2.60 | -0.01 km (-0.3%) | 0 |

### Anchorage 2018 (anchorage2018)

- Planning events: 324 (324 real by hour 12); later aftershocks for the test: 338; permanent stations: 71; pool: 801 points, road-checked: yes.
- Exact optimum: sites [0, 1, 2, 9] (objective 208.8). Largest error of the expanded objective over all 210 networks: 0.00e+00 (it is exact).

| QAOA variant | Seed | P(best) | vs 20% target | Valid outcomes | Most likely = best? | Final pick | Rank | Exact? | Evaluations | Seconds |
|---|---|---|---|---|---|---|---|---|---|---|
| mean-cold | 0 | 0.4% | missed | 1.000 | no | [0, 1, 5, 9] | 2 | **no** | 4000 | 15.8 |
| mean-cold | 1 | 0.4% | missed | 1.000 | no | [0, 1, 5, 9] | 2 | **no** | 4000 | 15.9 |
| mean-cold | 2 | 0.4% | missed | 1.000 | no | [0, 1, 5, 9] | 2 | **no** | 4000 | 14.8 |
| cvar-cold | 0 | 1.6% | missed | 1.000 | no | [0, 1, 2, 9] | 1 | yes | 2993 | 12.9 |
| cvar-cold | 1 | 1.8% | missed | 1.000 | no | [0, 1, 2, 9] | 1 | yes | 3336 | 14.3 |
| cvar-cold | 2 | 1.5% | missed | 1.000 | no | [0, 1, 5, 9] | 2 | **no** | 2752 | 11.8 |
| mean-warm | 0 | 0.4% | missed | 1.000 | no | [0, 1, 5, 9] | 2 | **no** | 400 | 5.1 |
| mean-warm | 1 | 0.4% | missed | 1.000 | no | [0, 1, 5, 9] | 2 | **no** | 400 | 5.2 |
| mean-warm | 2 | 0.4% | missed | 1.000 | no | [0, 1, 5, 9] | 2 | **no** | 400 | 5.4 |
| cvar-warm | 0 | 1.3% | missed | 1.000 | no | [0, 1, 5, 9] | 2 | **no** | 383 | 5.1 |
| cvar-warm | 1 | 1.3% | missed | 1.000 | no | [0, 1, 5, 9] | 2 | **no** | 383 | 5.0 |
| cvar-warm | 2 | 1.3% | missed | 1.000 | no | [0, 1, 5, 9] | 2 | **no** | 383 | 5.0 |

Location test (338 later aftershocks; with hearing range, 336 events are located by every network):

| Network | Sites | Rank | Mean error, plain (km) | Gain over expert, plain | Mean error, hearing (km) | Gain over expert, hearing | Not locatable (hearing) |
|---|---|---|---|---|---|---|---|
| exact | [0, 1, 2, 9] | 1 | 4.46 | -0.03 km (-0.7%) | 478.58 | -0.01 km (-0.0%) | 2 |
| expert_rule | [4, 7, 8, 9] | 138 | 4.43 | - | 478.57 | - | 2 |
| greedy | [0, 1, 2, 9] | 1 | 4.46 | -0.03 km (-0.7%) | 478.58 | -0.01 km (-0.0%) | 2 |
| no_new_sensors | [] | - | 4.44 | - | 478.56 | - | 2 |
| qaoa_mean-cold | [0, 1, 5, 9] | 2 | 4.47 | -0.04 km (-0.8%) | 478.58 | -0.01 km (-0.0%) | 2 |
| qaoa_cvar-cold | [0, 1, 2, 9] | 1 | 4.46 | -0.03 km (-0.7%) | 478.58 | -0.01 km (-0.0%) | 2 |
| qaoa_mean-warm | [0, 1, 5, 9] | 2 | 4.47 | -0.04 km (-0.8%) | 478.58 | -0.01 km (-0.0%) | 2 |
| qaoa_cvar-warm | [0, 1, 5, 9] | 2 | 4.47 | -0.04 km (-0.8%) | 478.58 | -0.01 km (-0.0%) | 2 |

### Ferndale 2022 (ferndale2022)

- Planning events: 48 (48 real by hour 12); later aftershocks for the test: 20; permanent stations: 22; pool: 141 points, road-checked: yes.
- Exact optimum: sites [0, 1, 3, 8] (objective -44.2). Largest error of the expanded objective over all 210 networks: 5.68e-14 (it is exact).

| QAOA variant | Seed | P(best) | vs 20% target | Valid outcomes | Most likely = best? | Final pick | Rank | Exact? | Evaluations | Seconds |
|---|---|---|---|---|---|---|---|---|---|---|
| mean-cold | 0 | 5.8% | missed | 1.000 | no | [0, 1, 3, 8] | 1 | yes | 4000 | 15.0 |
| mean-cold | 1 | 6.2% | missed | 1.000 | no | [0, 1, 3, 8] | 1 | yes | 4000 | 16.5 |
| mean-cold | 2 | 5.8% | missed | 1.000 | no | [0, 1, 3, 8] | 1 | yes | 4000 | 15.5 |
| cvar-cold | 0 | 7.1% | missed | 1.000 | no | [0, 1, 3, 8] | 1 | yes | 4000 | 16.5 |
| cvar-cold | 1 | 7.0% | missed | 1.000 | no | [0, 1, 3, 8] | 1 | yes | 4000 | 16.8 |
| cvar-cold | 2 | 6.8% | missed | 1.000 | no | [0, 1, 3, 8] | 1 | yes | 4000 | 16.5 |
| mean-warm | 0 | 6.0% | missed | 1.000 | no | [0, 1, 3, 8] | 1 | yes | 400 | 5.0 |
| mean-warm | 1 | 6.0% | missed | 1.000 | no | [0, 1, 3, 8] | 1 | yes | 400 | 5.2 |
| mean-warm | 2 | 6.0% | missed | 1.000 | no | [0, 1, 3, 8] | 1 | yes | 400 | 5.0 |
| cvar-warm | 0 | 10.0% | missed | 1.000 | yes | [0, 1, 3, 8] | 1 | yes | 206 | 4.5 |
| cvar-warm | 1 | 10.0% | missed | 1.000 | yes | [0, 1, 3, 8] | 1 | yes | 206 | 4.5 |
| cvar-warm | 2 | 10.0% | missed | 1.000 | yes | [0, 1, 3, 8] | 1 | yes | 206 | 4.5 |

Location test (20 later aftershocks; with hearing range, 20 events are located by every network):

| Network | Sites | Rank | Mean error, plain (km) | Gain over expert, plain | Mean error, hearing (km) | Gain over expert, hearing | Not locatable (hearing) |
|---|---|---|---|---|---|---|---|
| exact | [0, 1, 3, 8] | 1 | 2.40 | -0.07 km (-2.9%) | 2.35 | -0.04 km (-1.6%) | 0 |
| expert_rule | [1, 5, 8, 9] | 117 | 2.33 | - | 2.31 | - | 0 |
| greedy | [0, 1, 3, 8] | 1 | 2.40 | -0.07 km (-2.9%) | 2.35 | -0.04 km (-1.6%) | 0 |
| no_new_sensors | [] | - | 2.39 | - | 2.35 | - | 0 |
| qaoa_mean-cold | [0, 1, 3, 8] | 1 | 2.40 | -0.07 km (-2.9%) | 2.35 | -0.04 km (-1.6%) | 0 |
| qaoa_cvar-cold | [0, 1, 3, 8] | 1 | 2.40 | -0.07 km (-2.9%) | 2.35 | -0.04 km (-1.6%) | 0 |
| qaoa_mean-warm | [0, 1, 3, 8] | 1 | 2.40 | -0.07 km (-2.9%) | 2.35 | -0.04 km (-1.6%) | 0 |
| qaoa_cvar-warm | [0, 1, 3, 8] | 1 | 2.40 | -0.07 km (-2.9%) | 2.35 | -0.04 km (-1.6%) | 0 |

### Puerto Rico 2020 (puertorico2020)

- Planning events: 137 (137 real by hour 12); later aftershocks for the test: 710; permanent stations: 21; pool: 532 points, road-checked: yes.
- Exact optimum: sites [4, 5, 6, 9] (objective 41.4). Largest error of the expanded objective over all 210 networks: 0.00e+00 (it is exact).

| QAOA variant | Seed | P(best) | vs 20% target | Valid outcomes | Most likely = best? | Final pick | Rank | Exact? | Evaluations | Seconds |
|---|---|---|---|---|---|---|---|---|---|---|
| mean-cold | 0 | 5.8% | missed | 1.000 | no | [4, 5, 6, 9] | 1 | yes | 4000 | 15.6 |
| mean-cold | 1 | 1.2% | missed | 1.000 | no | [0, 4, 5, 9] | 3 | **no** | 4000 | 9.2 |
| mean-cold | 2 | 11.7% | missed | 1.000 | no | [4, 5, 6, 9] | 1 | yes | 4000 | 17.3 |
| cvar-cold | 0 | 4.6% | missed | 1.000 | no | [4, 5, 6, 9] | 1 | yes | 2644 | 14.0 |
| cvar-cold | 1 | 10.1% | missed | 1.000 | yes | [4, 5, 6, 9] | 1 | yes | 2441 | 8.8 |
| cvar-cold | 2 | 10.0% | missed | 1.000 | no | [4, 5, 6, 9] | 1 | yes | 2174 | 8.0 |
| mean-warm | 0 | 1.2% | missed | 1.000 | no | [0, 4, 5, 9] | 3 | **no** | 400 | 5.2 |
| mean-warm | 1 | 1.2% | missed | 1.000 | no | [0, 4, 5, 9] | 3 | **no** | 400 | 5.2 |
| mean-warm | 2 | 1.2% | missed | 1.000 | no | [0, 4, 5, 9] | 3 | **no** | 400 | 5.0 |
| cvar-warm | 0 | 10.2% | missed | 1.000 | yes | [4, 5, 6, 9] | 1 | yes | 91 | 3.9 |
| cvar-warm | 1 | 10.2% | missed | 1.000 | yes | [4, 5, 6, 9] | 1 | yes | 91 | 4.0 |
| cvar-warm | 2 | 10.2% | missed | 1.000 | yes | [4, 5, 6, 9] | 1 | yes | 91 | 4.1 |

Location test (710 later aftershocks; with hearing range, 710 events are located by every network):

| Network | Sites | Rank | Mean error, plain (km) | Gain over expert, plain | Mean error, hearing (km) | Gain over expert, hearing | Not locatable (hearing) |
|---|---|---|---|---|---|---|---|
| exact | [4, 5, 6, 9] | 1 | 2.87 | -0.39 km (-15.8%) | 2.77 | -0.37 km (-15.6%) | 0 |
| expert_rule | [0, 1, 2, 3] | 207 | 2.48 | - | 2.40 | - | 0 |
| greedy | [4, 5, 6, 9] | 1 | 2.87 | -0.39 km (-15.8%) | 2.77 | -0.37 km (-15.6%) | 0 |
| no_new_sensors | [] | - | 2.67 | - | 2.62 | - | 0 |
| qaoa_mean-cold | [4, 5, 6, 9] | 1 | 2.87 | -0.39 km (-15.8%) | 2.77 | -0.37 km (-15.6%) | 0 |
| qaoa_cvar-cold | [4, 5, 6, 9] | 1 | 2.87 | -0.39 km (-15.8%) | 2.77 | -0.37 km (-15.6%) | 0 |
| qaoa_mean-warm | [0, 4, 5, 9] | 3 | 2.71 | -0.24 km (-9.5%) | 2.62 | -0.22 km (-9.0%) | 0 |
| qaoa_cvar-warm | [4, 5, 6, 9] | 1 | 2.87 | -0.39 km (-15.8%) | 2.77 | -0.37 km (-15.6%) | 0 |

## What this shows (and does not)

- **mean-cold**: P(best) median 3.6% over 15 runs (range 0.4% to 11.7%); met the 20% target in 0 of 15 runs; final pick was the exact optimum in 8 of 15.
- **cvar-cold**: P(best) median 7.0% over 15 runs (range 1.5% to 10.1%); met the 20% target in 0 of 15 runs; final pick was the exact optimum in 14 of 15.
- **mean-warm**: P(best) median 1.4% over 15 runs (range 0.4% to 7.1%); met the 20% target in 0 of 15 runs; final pick was the exact optimum in 6 of 15.
- **cvar-warm**: P(best) median 9.6% over 15 runs (range 1.3% to 10.2%); met the 20% target in 0 of 15 runs; final pick was the exact optimum in 12 of 15.
- **Exact optimum vs the expert rule, plain location test**: gain Ridgecrest 2019 +0.10 km (+2.4%), Monte Cristo Range 2020 -0.00 km (-0.1%), Anchorage 2018 -0.03 km (-0.7%), Ferndale 2022 -0.07 km (-2.9%), Puerto Rico 2020 -0.39 km (-15.8%).
- **Same, with hearing range**: Ridgecrest 2019 0.09 km (2.7%), Monte Cristo Range 2020 -0.01 km (-0.3%), Anchorage 2018 -0.01 km (-0.0%), Ferndale 2022 -0.04 km (-1.6%), Puerto Rico 2020 -0.37 km (-15.6%).
- 3 seeds per variant and one simulated noise draw per event in the location test (the first seed's final pick is tested): differences of a few percent in P(best) or a few hundredths of a km are within run-to-run variation and should not be read as real.
- The location errors come from a simulation with a uniform-velocity Earth; they are model predictions, not measured errors. The hearing-range model uses assumed constants (one noise level for every site).
- No quantum speedup is claimed: the exact optimum is found by enumerating 210 networks in well under a second.

Skipped: South Napa 2014 (only 9 later aftershocks (M >= 2.5, 12 h to 7 days) to test on; at least 10 needed).

