# Research plan: Aftershock seismometer placement (quantum hybrid)

Date: 2026-11-12 · Depth: medium · Genre: validation + decision

## Underlying decision
Should the team build its Qiskit Fall Fest 2026 entry on "hybrid QAOA for temporary aftershock seismometer placement" (Disaster Response domain)? If so, which papers, data and formulation should it use?

## Falsifiable hypotheses
- **H1:** No published work formulates seismic station or network placement as QUBO/Ising, or solves it with QAOA or quantum annealing.
  *Refuted by* any such paper or preprint.
- **H2:** Operational rapid aftershock deployments choose sites mainly by expert judgement and logistics, not by an automated optimiser.
  *Refuted by* a documented operational tool used by the USGS, GFZ, EarthScope, INGV or similar.
- **H3:** The classical design criteria (D-optimal / error ellipsoid, azimuthal gap, coverage) can be approximated by a pairwise (quadratic) objective over discrete candidate sites.
  *Refuted by* evidence that pairwise approximations are invalid for station selection.
- **H4:** Open data (USGS ComCat catalog, mainshock parameters, 1D velocity model) is enough to build a realistic 8–12-site test instance.

## Sourcing strategy
Three parallel sub-agents:
- **A:** classical lineage and operational practice
- **B:** quantum and QUBO sensor-placement literature, plus the gap check
- **C:** data, tools and Qiskit feasibility

Each source is saved to `sources/NN_slug.md` with verbatim quotes.

## Opposition queries
- "quantum annealing seismic network design"
- "automatic aftershock deployment planning tool"
- "QUBO station selection seismology"

## Risk register
- Paywalled papers: rely on abstracts and say so.
- False "no results" for the gap: make no "first ever" claim.

## Stop criteria
Each hypothesis is confirmed, refuted or marked under-determined, with at least 3 sources where possible.

## Changelog
- 2026-11-12: plan created.
