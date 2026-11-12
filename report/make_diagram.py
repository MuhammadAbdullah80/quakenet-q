"""Draws the QuakeNet-Q architecture diagram -> figures/architecture.png"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent.parent / "figures" / "architecture.png"
CLASSICAL, QUANTUM, DATA, INK = "#dbeafe", "#ede9fe", "#fef3c7", "#1f2933"

LANES = [
    ("1  Classical: prepare", 0.5, [
        ("Real data", "USGS aftershocks (first 12 h)\nIRIS permanent stations", DATA, "data/fetch_data.py"),
        ("Physics model", "Travel-time sensitivities\nD-criterion per network", CLASSICAL, "src/geometry.py"),
        ("QUBO / Ising", "site gain a_i, pair redundancy b_ij,\naccess risk c_i  →  Hamiltonian H", CLASSICAL, "src/qubo.py"),
    ]),
    ("2  Quantum: choose (Qiskit)", 5.5, [
        ("Dicke state |D(10,4)>", "all 210 networks with\nexactly 4 sites, equal weight", QUANTUM, "src/qaoa_solver.py"),
        ("QAOA layers × p", "cost layer exp(-iγH)\nXY ring mixer (keeps 4 sites)", QUANTUM, "src/qaoa_solver.py"),
        ("Measure (Sampler)", "1024 shots → candidate networks", QUANTUM, "StatevectorSampler"),
    ]),
    ("3  Classical: finish and check", 10.5, [
        ("Re-score top samples", "true D-criterion − λ·risk\npick the best network", CLASSICAL, "run_experiment.py"),
        ("Baselines", "brute force (exact), greedy,\nbackward elimination, annealing", CLASSICAL, "src/baselines.py"),
        ("Evaluate", "location blur (km) on LATER\naftershocks; figures + JSON", DATA, "results/, figures/"),
    ]),
]
W, H, YS = 4.2, 1.45, [6.0, 3.6, 1.2]


def main() -> None:
    fig, ax = plt.subplots(figsize=(13, 6.6))
    ax.set(xlim=(0, 15.2), ylim=(0, 8.6)); ax.axis("off")
    centres = {}
    for li, (title, x, boxes) in enumerate(LANES):
        ax.text(x + W / 2, 8.1, title, ha="center", fontsize=13, fontweight="bold", color=INK)
        for bi, (name, body, colour, src) in enumerate(boxes):
            y = YS[bi]
            ax.add_patch(FancyBboxPatch((x, y), W, H, boxstyle="round,pad=0.02,rounding_size=0.15",
                                        fc=colour, ec=INK, lw=1.2))
            ax.text(x + W / 2, y + H - 0.3, name, ha="center", fontsize=11, fontweight="bold", color=INK)
            ax.text(x + W / 2, y + H / 2 - 0.12, body, ha="center", va="center", fontsize=9, color=INK)
            ax.text(x + W / 2, y + 0.1, src, ha="center", fontsize=7.5, color="#52606d", family="monospace")
            centres[li, bi] = (x, y)

    def arrow(p, q, **kw):
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=16, lw=1.5, color=INK, **kw))

    for li in range(3):                       # down each lane
        x = LANES[li][1] + W / 2
        arrow((x, YS[0]), (x, YS[1] + H)); arrow((x, YS[1]), (x, YS[2] + H))
    for li in range(2):                       # bottom of lane -> top of next lane
        x0, x1 = LANES[li][1] + W, LANES[li + 1][1]
        arrow((x0, YS[2] + H / 2), (x1, YS[0] + H / 2))

    # classical optimiser loop around the QAOA layers
    qx = LANES[1][1]
    ax.add_patch(FancyBboxPatch((qx + 0.55, 5.18), W - 1.1, 0.62, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc="white", ec="#7c3aed", lw=1.2, ls="--"))
    ax.text(qx + W / 2, 5.49, "COBYLA tunes γ, β  (Estimator ⟨H⟩)", ha="center", va="center", fontsize=8.5, color="#5b21b6")
    fig.tight_layout()
    fig.savefig(OUT, dpi=170)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
