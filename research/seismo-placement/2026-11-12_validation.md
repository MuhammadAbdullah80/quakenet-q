# Validation report: hybrid QAOA for aftershock seismometer placement

Date: 2026-11-12 · Depth: medium · Sources: `sources/A01–A14` (classical and operational), `B01–B10` (quantum), `C01–C06` (data and Qiskit)

## Hypothesis verdicts

| # | Hypothesis | Verdict | Basis |
|---|---|---|---|
| H1 | No published quantum (QUBO/QAOA/annealing) formulation of seismic station placement exists | **Not refuted; leaning confirmed** | About 8 adversarial searches found nothing. The closest work is quantum seismic *inversion* (Nguyen & Tura 2024, arXiv 2412.06611) and quantum sensor placement in *other* fields (structures, water, factories). Limits: US-only search tool; Google Scholar, SEG and non-English literature not queried. |
| H2 | Operational rapid aftershock deployments choose sites by expert judgement and logistics, not an automated optimiser | **Under-determined; leaning confirmed** | USGS Ridgecrest (Cochran et al. 2020), SISMIKO (Moretti et al. 2023), Turkey 2023 and RAMP describe only qualitative goals ("improve azimuthal coverage", near-field). The nearest counter-evidence is the AuScope Seismic Network Design App and SN-CAST, both *pre-deployment* design tools rather than post-quake responders. Full texts were not read. |
| H3 | The classical criterion can be approximated pairwise over discrete sites | **Supported, with a caveat** | The D-criterion (log det of the location Fisher information) is not quadratic. A second-order inclusion–exclusion truncation (single-site gains plus pairwise interactions) gives an exact QUBO of an *approximate* objective. Mitigation: score final networks with the *true* D-criterion and report the correlation over all subsets. The Nakano & Uno mutual-information QUBO is quadratic only for n = 3 (higher-order for n ≥ 4), so it is not suitable. |
| H4 | Open data suffices for a realistic 8–12-site instance | **Confirmed** | The USGS ComCat FDSN query (no key, public domain) returned 261 Ridgecrest M≥3.5 events for 6–8 July 2019. The IRIS station service lists 14 permanent CI stations, with gaps to the east and southeast. A constant Vp of about 6 km/s is adequate; ObsPy is not needed. |

## Research lineage (verified via Crossref unless noted)

- **Kijko 1977**, *Pure Appl. Geophys.* 115, 999–1009, doi:10.1007/BF00881222: early optimal seismic network planning.
- **Rabinowitz & Steinberg 1990**, *BSSA* 80(1), 187–196, doi:10.1785/BSSA0800010187: the D-optimality criterion and the DETMAX algorithm.
- **Steinberg, Rabinowitz, Shimshoni & Mizrachi 1995**, *BSSA* 85(6), 1847–1857, doi:10.1785/BSSA0850061847: extension to fault systems.
- **Hardt & Scherbaum 1994**, *GJI* 117(3), 716–726, doi:10.1111/j.1365-246X.1994.tb02464.x: optimum **aftershock** networks by simulated annealing (method details are from a summary).
- **Toledo, Jousset, Maurer & Krawczyk 2020**, *JVGR* 391, 106433, doi:10.1016/j.jvolgeores.2018.08.011: D-criterion with sequential backward elimination.
- **Bloem, Curtis & Maurer 2020**, *GJI* 223, 944–958: maximum-entropy and D-optimal network design.
- **Cochran et al. 2020**, *SRL* 91, 1952–1960, doi:10.1785/0220190296: the USGS Ridgecrest rapid deployment.

## Quantum template (credit required)

- **San Martín et al.** (arXiv 2305.08738; venue unverified): QAOA sensor placement with a bilinear objective. A Dicke state plus XY mixer enforces exactly k sensors and consistently beat the penalty version.
- **Hadfield et al. 2019** (Quantum Alternating Operator Ansatz) and **Bärtschi & Eidenbenz 2019** (Dicke states): the constrained mixer and the initial state.
- **Speziali (arXiv 2108.04075)** and **Kraus (arXiv 2507.16584)**: QUBO sensor placement with slack and penalties. Kraus reports that classical solvers still outperform; this is the reason to avoid slack qubits.

## Adversarial pass

1. *"The pairwise objective isn't the real seismology objective."* True. Report the Spearman correlation between the QUBO score and the true log-det across all C(10,4) = 210 subsets, and say plainly how often they rank differently.
2. *"Brute force solves 210 subsets instantly, so why use quantum?"* Agree openly: no speedup is claimed. The contribution is the formulation plus an honest benchmark.
3. *"Is this the first quantum work on this?"* Claim only "first we found".
4. *"Synthetic candidate sites are arbitrary."* Place them in the documented coverage gaps (east and southeast of the CI network) and list the rule used.

## Confidence

Medium. Bibliographic metadata is verified. Method details for Hardt & Scherbaum and Kijko, and the operational siting practice, come from abstracts or summaries only.
