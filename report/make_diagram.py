"""Draws the two report diagrams.

    python report/make_diagram.py

figures/architecture.png : one plan, from data to checked answer (the hybrid pipeline)
figures/system.png       : the whole system: the agent loop, its memory, and where each part runs
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

FIG = Path(__file__).resolve().parent.parent / "figures"
CLASSICAL, QUANTUM, DATA, HOST, INK, MUTED = "#dbeafe", "#ede9fe", "#fef3c7", "#e7f0e0", "#1f2933", "#52606d"

LANES = [
    ("1  Classical: prepare", 0.5, [
        ("Real data", "USGS aftershocks (first 12 h)\nIRIS permanent stations", DATA, "data/fetch_data.py"),
        ("Physics model", "Travel-time sensitivities\nD-criterion per network", CLASSICAL, "src/geometry.py"),
        ("Exact score → Hamiltonian", "385 terms: single sites and groups\nof 2, 3, 4 sites, minus λ·risk", CLASSICAL, "src/qubo.py"),
    ]),
    ("2  Quantum: choose (Qiskit)", 5.5, [
        ("Dicke state |D(10,4)>", "all 210 networks with\nexactly 4 sites, equal weight", QUANTUM, "src/qaoa_solver.py"),
        ("QAOA layers × p", "cost layer exp(-iγH)\nXY ring mixer (keeps 4 sites)", QUANTUM, "src/qaoa_solver.py"),
        ("Measure (Sampler)", "1024 shots → candidate networks", QUANTUM, "StatevectorSampler"),
    ]),
    ("3  Classical: finish and check", 10.5, [
        ("Re-score top samples", "true D-criterion − λ·risk\npick the best network", CLASSICAL, "run_experiment.py"),
        ("Baselines", "brute force (exact), greedy,\nbackward elimination, annealing", CLASSICAL, "src/baselines.py"),
        ("Evaluate", "simulated location error (km)\non LATER aftershocks", DATA, "results/, figures/"),
    ]),
]
W, H, YS = 4.2, 1.45, [6.0, 3.6, 1.2]


def _box(ax, x, y, w, h, title, body, colour, src=None, *, title_size=11, body_size=9):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.15", fc=colour, ec=INK, lw=1.2))
    ax.text(x + w / 2, y + h - 0.3, title, ha="center", fontsize=title_size, fontweight="bold", color=INK)
    ax.text(x + w / 2, y + h / 2 - 0.12, body, ha="center", va="center", fontsize=body_size, color=INK)
    if src:
        ax.text(x + w / 2, y + 0.1, src, ha="center", fontsize=7.5, color=MUTED, family="monospace")


def _arrow(ax, p, q, colour=INK, **kw):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=16, lw=1.5, color=colour, **kw))


def pipeline() -> None:
    fig, ax = plt.subplots(figsize=(13, 6.6))
    ax.set(xlim=(0, 15.2), ylim=(0, 8.6)); ax.axis("off")
    for title, x, boxes in LANES:
        ax.text(x + W / 2, 8.1, title, ha="center", fontsize=13, fontweight="bold", color=INK)
        for bi, (name, body, colour, src) in enumerate(boxes):
            _box(ax, x, YS[bi], W, H, name, body, colour, src)
    for li in range(3):                       # down each lane
        x = LANES[li][1] + W / 2
        _arrow(ax, (x, YS[0]), (x, YS[1] + H)); _arrow(ax, (x, YS[1]), (x, YS[2] + H))
    for li in range(2):                       # bottom of lane -> top of next lane
        _arrow(ax, (LANES[li][1] + W, YS[2] + H / 2), (LANES[li + 1][1], YS[0] + H / 2))
    qx = LANES[1][1]                          # classical optimiser loop around the QAOA layers
    ax.add_patch(FancyBboxPatch((qx + 0.55, 5.18), W - 1.1, 0.62, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc="white", ec="#7c3aed", lw=1.2, ls="--"))
    ax.text(qx + W / 2, 5.49, "COBYLA tunes γ, β  (CVaR, warm start)", ha="center", va="center", fontsize=8.5,
            color="#5b21b6")
    fig.tight_layout()
    fig.savefig(FIG / "architecture.png", dpi=170)
    plt.close(fig)


def system() -> None:
    fig, ax = plt.subplots(figsize=(13, 7.4))
    ax.set(xlim=(0, 15.2), ylim=(0, 9.4)); ax.axis("off")
    ax.text(7.6, 9.0, "The agent loop (src/agent/)", ha="center", fontsize=13, fontweight="bold", color=INK)
    w, h, y1, y2 = 3.2, 1.55, 6.7, 4.1
    top = [(0.4, "USGS live feed", "checked at most once a minute\n(or a past quake, replayed)", DATA),
           (4.2, "Trigger", "magnitude ≥ setting (e.g. 4.0)\nand a station within range", CLASSICAL),
           (8.0, "First plan", "simulated aftershocks along the\nexpected rupture if few are real", CLASSICAL),
           (11.8, "Plan (Figure 2)", "QAOA chooses 4 sites,\nexact search checks it", QUANTUM)]
    for x, t, b, c in top:
        _box(ax, x, y1, w, h, t, b, c)
    for (xa, *_), (xb, *_) in zip(top, top[1:]):
        _arrow(ax, (xa + w, y1 + h / 2), (xb, y1 + h / 2))
    bottom = [(11.8, "Publish", "sites, confidence, flag if\nthe exact answer had to be used", CLASSICAL),
              (8.0, "Hourly check", "new aftershocks: moved > 5 km\nor score fell > 20%?", CLASSICAL),
              (4.2, "Re-plan", "with a cost for every\nsensor that must move", CLASSICAL),
              (0.4, "Memory", "circuit angles, track record,\nwave-speed model weights", DATA)]
    for x, t, b, c in bottom:
        _box(ax, x, y2, w, h, t, b, c)
    _arrow(ax, (11.8 + w / 2, y1), (11.8 + w / 2, y2 + h))                 # plan -> publish
    _arrow(ax, (11.8, y2 + h / 2), (8.0 + w, y2 + h / 2))                  # publish -> check
    _arrow(ax, (8.0, y2 + h / 2), (4.2 + w, y2 + h / 2))                   # check -> re-plan
    ax.text(7.6, y2 + h / 2 + 0.18, "yes", ha="center", fontsize=8.5, color=MUTED)
    ys = (y2 + h + y1) / 2                                                # corridor between the rows
    ax.plot([4.2 + w / 2, 4.2 + w / 2, 12.6], [y2 + h, ys, ys], color=INK, lw=1.5)
    _arrow(ax, (12.6, ys), (12.6, y1))                                     # re-plan -> plan
    _arrow(ax, (8.0 + 0.9, y2), (8.0 + w - 0.9, y2), connectionstyle="arc3,rad=0.9")
    ax.text(8.0 + w / 2, y2 - 0.95, "no: wait an hour, check again", ha="center", fontsize=8.5, color=MUTED)
    _arrow(ax, (0.4 + w, y2 + h / 2), (4.2, y2 + h / 2), colour=MUTED, ls="--")
    ax.text(0.4 + w + 0.3, y2 + h / 2 + 0.15, "warm start", fontsize=8, color=MUTED)

    ax.text(7.6, 2.75, "Where it runs", ha="center", fontsize=13, fontweight="bold", color=INK)
    hw, hh, hy = 3.2, 1.5, 0.6
    host = [(0.4, "Team laptop", "FastAPI + agent + Qiskit\n127.0.0.1 only; bearer token", HOST, "api/, src/"),
            (4.2, "Tailscale Funnel", "encrypted tunnel; the laptop\nopens no ports to the internet", HOST, None),
            (8.0, "Vercel (Next.js)", "test console; server-side calls,\npasscode for any change", HOST, "web/"),
            (11.8, "Browser", "never sees the token;\nsaved results if laptop is off", HOST, None)]
    for x, t, b, c, s in host:
        _box(ax, x, hy, hw, hh, t, b, c, s, title_size=10.5, body_size=8.5)
    for (xa, *_), (xb, *_) in zip(host, host[1:]):
        _arrow(ax, (xa + hw, hy + hh / 2), (xb, hy + hh / 2))
        _arrow(ax, (xb, hy + hh / 2 - 0.3), (xa + hw, hy + hh / 2 - 0.3))
    fig.tight_layout()
    fig.savefig(FIG / "system.png", dpi=170)
    plt.close(fig)


def main() -> None:
    pipeline()
    system()
    print("wrote", FIG / "architecture.png", "and", FIG / "system.png")


if __name__ == "__main__":
    main()
