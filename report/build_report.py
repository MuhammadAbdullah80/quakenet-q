"""Builds report/QuakeNet-Q_Report.docx from results/results.json and figures/.

    python report/build_report.py
"""
import json
from pathlib import Path

import numpy as np
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
R = json.loads((ROOT / "results" / "results.json").read_text())
FIG = ROOT / "figures"
TEAM = "Team: [add team name and members]"


def stats(key, reps):
    v = [r[key] for r in R["qaoa"]["runs"] if r["reps"] == reps]
    return float(np.mean(v)), float(min(v)), float(max(v))


doc = Document()
style = doc.styles["Normal"]
style.font.name, style.font.size = "Calibri", Pt(11)
for lvl, size in ((1, 16), (2, 13)):
    h = doc.styles[f"Heading {lvl}"]
    h.font.name, h.font.size, h.font.color.rgb = "Calibri", Pt(size), RGBColor(0x1F, 0x29, 0x33)


def para(text, bold=False, italic=False, align=None):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold, run.italic = bold, italic
    if align:
        p.alignment = align
    return p


def bullets(items):
    for it in items:
        doc.add_paragraph(it, style="List Bullet")


def figure(name, caption, width=6.0):
    doc.add_picture(str(FIG / name), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    c = para(caption, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    c.runs[0].font.size = Pt(9)


def table(header, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Light Grid Accent 1"
    for cell, text in zip(t.rows[0].cells, header):
        cell.text = text
        cell.paragraphs[0].runs[0].bold = True
    for row in rows:
        for cell, text in zip(t.add_row().cells, row):
            cell.text = str(text)
    if widths:
        for row in t.rows:
            for cell, w in zip(row.cells, widths):
                cell.width = Inches(w)
    doc.add_paragraph()


I, F, Q, B, M = R["instance"], R["formulation"], R["qaoa"], R["blur"], R["methods"]
qaoa = M["Hybrid QAOA (XY mixer)"]
p1, p3 = stats("xy_p_opt", 1), stats("xy_p_opt", 3)
uni = Q["uniform_p_opt"]
n_runs = len(Q["runs"])
n_exact = sum(r["xy_final_is_exact"] for r in Q["runs"])
lam300 = next(s for s in F["lam_sweep"] if s["lam"] == 300)
sites = "{" + ", ".join(map(str, qaoa["sites"])) + "}"

# ------------------------------------------------------------------ title
t = doc.add_heading("QuakeNet-Q", 0)
para("Hybrid quantum–classical placement of portable seismometers after a major earthquake", bold=True)
para("Qiskit Fall Fest 2026 Hackathon · Domain: Disaster Response")
para(TEAM)

# ------------------------------------------------------------------ 1
doc.add_heading("1. Problem and who it serves", 1)
para("When a large earthquake strikes, the permanent seismic network is usually too sparse to locate "
     "the thousands of aftershocks precisely. Response teams therefore install a small number of "
     "portable seismometers within hours or days. Where those instruments go determines how sharply "
     "aftershocks can be located, and sharp locations show which faults are still active, which feeds "
     "aftershock forecasts and decisions about where rescuers and residents are safe.")
para("Optimal network design has been studied in seismology since the 1990s (Rabinowitz & Steinberg "
     "1990; Hardt & Scherbaum 1994), but the published accounts of real rapid deployments that we "
     "found, such as the USGS response at Ridgecrest in 2019 (Cochran et al. 2020), describe siting "
     "in qualitative terms: improve azimuthal coverage, get near-field observations, work around "
     "access and permits. We did not find a documented tool that recommends sites after an earthquake.")
para("Problem statement. ", bold=True).add_run(
    "Given the aftershocks recorded in the first 12 hours, the permanent stations, and a set of "
    "candidate sites, choose where to put a limited number of portable seismometers so that later "
    "aftershocks are located as accurately as possible, without wasting instruments on redundant "
    "sites and without sending crews to unnecessarily risky locations.").bold = False
bullets([
    "Users: rapid-response seismology teams (for example USGS, INGV, GFZ) and the emergency managers who rely on their aftershock maps.",
    "Limited resource: 4 portable instruments.",
    "Competing objectives: location accuracy, sensor redundancy, and access risk. The most informative sites lie on the active rupture, which is also the hardest and most dangerous place to work.",
])

# ------------------------------------------------------------------ 2
doc.add_heading("2. Formulation", 1)
doc.add_heading("2.1 Test instance (real data)", 2)
table(["Item", "Value", "Source"], [
    ["Earthquake", "M7.1 Ridgecrest, California, 6 July 2019", "USGS ComCat"],
    ["Planning events", f"{I['design_events']} aftershocks (M≥3) in the first {I['decision_hours']} h", "USGS ComCat"],
    ["Test events", f"{I['validation_events']} later aftershocks (to 13 July), never seen by the planner", "USGS ComCat"],
    ["Permanent stations", f"{I['permanent_stations']} stations of network CI", "IRIS/EarthScope FDSN"],
    ["Candidate sites", f"{I['candidates']} grid nodes at least 6 km from any permanent station", "Rule (Section 2.3)"],
    ["Budget", f"k = {I['k']} sensors → {I['feasible_networks']} allowed networks", "Assumption"],
], widths=[1.5, 3.3, 1.7])
figure("map.png", "Figure 1. The instance. Grey dots were used for planning, orange dots for testing. "
       "Numbered circles are candidate sites coloured by access risk; blue rings mark the sites chosen by the hybrid QAOA.", 4.6)

doc.add_heading("2.2 Variables, objective, constraint", 2)
bullets([
    "Decision variables: x_i ∈ {0, 1} for i = 0…9; x_i = 1 means a sensor is placed at candidate site i. One qubit per site.",
    "Constraint: Σ x_i = 4.",
    "True score (classical): D(S) = Σ_e log det F_e(S), the D-optimality criterion. F_e is the 4×4 Fisher information matrix of aftershock e's location (x, y, depth, origin time) from P-wave arrival times at the permanent stations plus the chosen sites. A larger determinant means a smaller location error ellipsoid.",
    "Plain-language metric: “blur” = the expected hypocentre uncertainty in km, the square root of the trace of the location covariance, averaged over events.",
    "Access risk: c_i = exp(−d_i / 5 km), where d_i is the distance from site i to the nearest early aftershock.",
])
para("The log-determinant is not quadratic in x, so it cannot be put on a QAOA circuit directly. "
     "We keep the first two orders of its inclusion–exclusion expansion:")
para("maximise  f(x) = Σ_i (a_i − λ c_i) x_i + Σ_{i<j} b_ij x_i x_j     subject to  Σ_i x_i = 4", bold=True,
     align=WD_ALIGN_PARAGRAPH.CENTER)
bullets([
    "a_i = D({i}) − D(∅): information gained by site i alone.",
    "b_ij = D({i, j}) − D({i}) − D({j}) + D(∅): interaction of two sites; negative when they are redundant.",
    f"λ = {I['lam']:.0f}: how much information one unit of access risk must buy.",
])
para("Substituting x_i = (1 − Z_i)/2 gives an Ising Hamiltonian with Z and ZZ terms whose ground state "
     "(within the 4-site subspace) is the best network. The formulation is exact for one- and two-site "
     "networks and an approximation for four; Section 5.1 measures how good it is.")

doc.add_heading("2.3 Assumptions we made", 2)
bullets([
    "Uniform P-wave velocity of 6 km/s and a picking error of 0.1 s.",
    "Candidate sites come from a regular 6×6 grid over the study area; nodes within 6 km of a permanent station are dropped and the 10 closest to the aftershock cloud are kept.",
    "The access-risk rule is our own proxy. A real deployment would use roads, land permits and safety assessments.",
])

# ------------------------------------------------------------------ 3
doc.add_heading("3. Choice of quantum algorithm", 1)
para("We use the Quantum Approximate Optimization Algorithm (QAOA; Farhi et al. 2014), the standard "
     "near-term algorithm for QUBO problems, in its constraint-preserving form (the Quantum "
     "Alternating Operator Ansatz of Hadfield et al. 2019):")
bullets([
    "Initial state: the Dicke state |D(10,4)⟩, an equal superposition of exactly the 210 allowed networks, prepared with the deterministic circuit of Bärtschi & Eidenbenz (2019).",
    "Cost layer: exp(−iγH), built from RZ and RZZ gates, which imprints each network's score as a phase.",
    "Mixer: a ring of XY gates, exp(−iβ(XX+YY)/2). Each gate swaps a chosen site with an unchosen neighbour, so the number of chosen sites never changes.",
    "A classical optimiser (COBYLA) tunes the 2p angles to minimise ⟨H⟩ (Qiskit Estimator); the tuned circuit is then measured 1024 times (Qiskit Sampler).",
])
para("Why not the textbook penalty approach? Adding a penalty P(Σx − 4)² lets the circuit spend "
     "probability on invalid answers and requires tuning P. San Martín et al. (arXiv:2305.08738) "
     "found XY mixers with Dicke states better for sensor placement on structures; we tested the "
     "same question on our problem as an ablation (Section 5.2).")

# ------------------------------------------------------------------ 4
doc.add_heading("4. Architecture and implementation", 1)
figure("architecture.png", "Figure 2. Architecture. Classical code prepares the Hamiltonian, the Qiskit circuit "
       "chooses the sites, and classical code re-scores and checks the result.", 6.4)
bullets([
    "Stage 1 (classical): data/fetch_data.py caches USGS and IRIS data; src/geometry.py computes the D-criterion; src/qubo.py builds the QUBO and the Hamiltonian (SparsePauliOp).",
    "Stage 2 (quantum): src/qaoa_solver.py builds the circuits gate by gate in Qiskit 2.6.2 and runs the hybrid loop with StatevectorEstimator and StatevectorSampler.",
    f"Stage 3 (classical): run_experiment.py re-scores the {10} most frequently measured networks with the true objective, picks the best, and compares it with src/baselines.py.",
    "tests/ holds 13 automated checks: the Hamiltonian equals the QUBO on every basis state, the Dicke circuit is exactly uniform over allowed networks, the XY mixer never leaves them, and brute force is never beaten.",
    f"Experiment: p = 1, 2, 3 layers × 5 random seeds, 3 optimiser restarts each; total runtime {R['runtime_seconds']:.0f} s on a laptop.",
])

# ------------------------------------------------------------------ 5
doc.add_heading("5. Results", 1)
doc.add_heading("5.1 Is the QUBO a fair stand-in for the real score?", 2)
para(f"Across all {I['feasible_networks']} allowed networks the QUBO value and the true objective have a Spearman rank "
     f"correlation of {F['spearman_qubo_vs_true']:.3f}, and at λ = {I['lam']:.0f} the QUBO optimum is the true optimum. "
     f"The approximation is not perfect: when we repeated the check for seven values of λ, the QUBO optimum was the "
     f"true optimum in six, and at λ = 300 it was the {lam300['rank_of_qubo_opt']}nd-best network.")
figure("formulation_check.png", "Figure 3. QUBO objective against the true objective for every allowed network.", 3.8)

doc.add_heading("5.2 Does the quantum circuit work?", 2)
rows = []
for p in sorted({r["reps"] for r in Q["runs"]}):
    po, ra, pf, pp = stats("xy_p_opt", p), stats("xy_ratio", p), stats("pen_feasible", p), stats("pen_p_opt", p)
    rows.append([p, f"{ra[0]:.3f}", f"{100*po[0]:.1f}% ({100*po[1]:.1f}–{100*po[2]:.1f})", f"{po[0]/uni:.0f}×",
                 f"{stats('xy_shots_for_95', p)[0]:.0f}", f"{100*pf[0]:.0f}%", f"{100*pp[0]:.2f}%"])
table(["p", "Approx. ratio", "P(best network), XY", "vs random", "Shots for 95%", "Valid answers, penalty", "P(best), penalty"],
      rows)
para(f"A random allowed network is the best one with probability 1/210 = {100*uni:.2f}% and has an approximation ratio of "
     f"{Q['uniform_ratio']:.3f}; it would take about 630 shots to see the optimum with 95% confidence. The XY-mixer QAOA "
     f"raises that probability to {100*p1[0]:.1f}% at p = 1 and {100*p3[0]:.1f}% at p = 3, and every measurement is a valid "
     f"4-site network. After the classical re-scoring step, the pipeline returned the exact optimum, sites {sites}, in "
     f"{n_exact} of {n_runs} runs.")
para("The penalty-based circuit produced a valid 4-site answer only about half to three quarters of the time and measured "
     "the optimum less often than random guessing among valid networks. On this problem the constraint-preserving design is "
     "what makes QAOA useful. One caveat: we used a single penalty weight (P = 2 in scaled units) and did not tune it, "
     "so a better-tuned penalty circuit could do better than ours did.")
figure("qaoa_performance.png", "Figure 4. Left: probability of measuring the best network (log scale; bars show the range over 5 seeds). "
       "Right: probability that a measurement is a valid 4-site network.", 6.2)

doc.add_heading("5.3 Comparison with exact and classical methods", 2)
table(["Method", "Sites", "Rank of 210 (true objective)", "Blur on later aftershocks (km)"],
      [["No new sensors", "–", "–", f"{B['no_new_sensors_valid_km']:.2f}"],
       ["Average random network", "–", "–", f"{B['mean_random_valid_km']:.2f}"]] +
      [[name, ", ".join(map(str, m["sites"])), m["rank_true"], f"{m['blur_valid_km']:.2f}"] for name, m in M.items()])
para(f"On the {I['validation_events']} later aftershocks, which played no part in planning, the chosen network reduces the mean "
     f"location uncertainty from {B['no_new_sensors_valid_km']:.2f} km to {qaoa['blur_valid_km']:.2f} km. The hybrid QAOA matches "
     f"the exact brute-force answer. So do greedy selection, backward elimination and simulated annealing "
     f"({Q['sa_found_exact']} of {Q['sa_runs']} seeds): this instance is easy for classical methods.")
figure("blur_by_method.png", "Figure 5. Location uncertainty on later aftershocks for each method (lower is better).", 5.2)

doc.add_heading("5.4 The trade-off between accuracy and crew risk", 2)
para(f"Ignoring risk (λ = 0), the best network is {{0, 1, 4, 7}} with a blur of {B['best_possible_valid_km']:.2f} km but a total "
     f"access risk of {F['lam_sweep'][0]['risk']:.2f}. At λ = {I['lam']:.0f} the optimiser swaps high-risk site 0 for low-risk site 3: "
     f"risk falls to {qaoa['risk']:.2f} for a cost of {qaoa['blur_valid_km'] - B['best_possible_valid_km']:.2f} km in blur. "
     "Larger λ pushes sensors away from the rupture and accuracy degrades quickly.")
figure("tradeoff.png", "Figure 6. Exact optimum for different risk weights λ.", 3.8)

# ------------------------------------------------------------------ 6
doc.add_heading("6. Limitations and reflection", 1)
bullets([
    "No quantum advantage. With 210 allowed networks, brute force takes milliseconds and simple heuristics find the optimum. We make no speedup claim; the instance is small so that every result can be verified exactly.",
    f"The QUBO approximates the real criterion. It ranked networks well (ρ = {F['spearman_qubo_vs_true']:.3f}) but picked the 2nd-best network at λ = 300. The classical re-scoring step exists to catch such cases, and it would matter more for larger budgets, where higher-order interactions grow.",
    "QAOA finds the optimum by sampling, not with certainty. The single most likely measurement is not guaranteed to be the best network; the probability of the optimum was 5–11% per shot.",
    "The circuit is deep. After decomposition the XY-mixer circuit is 445–595 layers deep, against 54–118 for the penalty circuit, mostly because of the Dicke-state preparation and the XY gates. We ran a noise-free statevector simulation only; on current hardware this depth would be a serious problem.",
    "Simplified physics: uniform velocity, P arrivals only, a fixed picking error, no station noise or site effects. The blur values are relative indicators, not operational location errors.",
    "Synthetic inputs: candidate sites and access risk follow rules we wrote, and λ is a judgement call that a response team would need to set.",
    "Evidence limits: our statement that siting is mostly manual rests on published deployment reports, not interviews, and “no earlier quantum formulation” means only that our literature searches found none.",
    "What we would do next: a layered velocity model, real access data, larger instances (20–30 sites) where enumeration stops being trivial, and noisy simulation.",
])

# ------------------------------------------------------------------ refs
doc.add_heading("References", 1)
for ref in [
    "Bärtschi, A. & Eidenbenz, S. (2019). Deterministic preparation of Dicke states. FCT 2019, LNCS 11651.",
    "Cochran, E. S. et al. (2020). The U.S. Geological Survey's rapid seismic array deployment for the 2019 Ridgecrest earthquake sequence. Seismological Research Letters 91, 1952–1960. doi:10.1785/0220190296",
    "Farhi, E., Goldstone, J. & Gutmann, S. (2014). A quantum approximate optimization algorithm. arXiv:1411.4028.",
    "Hadfield, S. et al. (2019). From the quantum approximate optimization algorithm to a quantum alternating operator ansatz. Algorithms 12(2), 34.",
    "Hardt, M. & Scherbaum, F. (1994). The design of optimum networks for aftershock recordings. Geophysical Journal International 117(3), 716–726. doi:10.1111/j.1365-246X.1994.tb02464.x",
    "Rabinowitz, N. & Steinberg, D. M. (1990). Optimal configuration of a seismographic network: a statistical approach. Bulletin of the Seismological Society of America 80(1), 187–196.",
    "San Martín, G. et al. Quantum-based combinatorial optimization for optimal sensor placement in civil structures. arXiv:2305.08738.",
    "Toledo, T., Jousset, P., Maurer, H. & Krawczyk, C. (2020). Optimized experimental network design for earthquake location problems. Journal of Volcanology and Geothermal Research 391, 106433.",
    "U.S. Geological Survey. ANSS Comprehensive Earthquake Catalog (ComCat), https://earthquake.usgs.gov/fdsnws/event/1/ ; station metadata: EarthScope/IRIS FDSN station service, network CI.",
]:
    doc.add_paragraph(ref, style="List Number")
para("Code was written for this hackathon with AI assistance (Claude Code); the ideas above are credited to their authors.", italic=True)

out = ROOT / "report" / "QuakeNet-Q_Report.docx"
doc.save(out)
print("wrote", out)
