"""QuakeNet-Q end-to-end experiment.

    python run_experiment.py            # full run (a few minutes on a laptop)
    python run_experiment.py --quick    # 1 seed, p = 1 only (under a minute)

Pipeline
  1. classical : real Ridgecrest data -> site gains, pair redundancy, access risk -> QUBO
  2. quantum   : Dicke state + XY-mixer QAOA picks 4 of 10 sites (COBYLA tunes the angles)
  3. classical : re-score the sampled networks with the true D-criterion, compare with
                 exact search and classical heuristics, evaluate on LATER aftershocks

Writes results/results.json and figures/*.png (a --quick run writes results_quick.json and figures_quick/).
"""
from __future__ import annotations

import argparse
import json
import time
import warnings
from math import log
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr

from src.baselines import (backward_elimination, brute_force, greedy_forward, random_pick,
                           simulated_annealing)
from src.geometry import DECISION_HOURS, Scorer, load_instance
from src.qaoa_solver import run_penalty_qaoa, run_xy_qaoa
from src.qubo import build_qubo, energies, to_hamiltonian

warnings.filterwarnings("ignore", category=Warning, module="scipy")

ROOT = Path(__file__).resolve().parent
LAM = 150.0          # information units one unit of access risk must buy
PENALTY = 2.0        # penalty weight of the ablation (scaled units, largest QUBO coefficient = 1)
SHOTS = 1024
TOP_M = 10           # sampled networks re-scored classically with the true criterion
C = dict(ink="#1f2933", grey="#9aa5b1", blue="#2563eb", orange="#ea580c", green="#059669", red="#dc2626")


def index(sel) -> int:
    return sum(1 << i for i in sel)


def main(quick: bool) -> None:
    t_start = time.time()
    inst = load_instance()
    design, valid = Scorer(inst, inst.design), Scorer(inst, inst.valid)
    sets = inst.feasible_sets()
    n, k = inst.n, inst.k

    # ---------------------------------------------------------------- 1. classical: formulation
    qubo = build_qubo(inst, design, LAM)

    def true_obj(sel) -> float:           # the objective we actually care about
        return design.d_score(sel) - LAM * float(inst.risk[list(sel)].sum())

    d_empty = design.d_score([])
    f_qubo = np.array([qubo.value(s) for s in sets])
    f_true = np.array([true_obj(s) - d_empty for s in sets])
    rho = float(spearmanr(f_qubo, f_true)[0])
    exact_true = sets[int(f_true.argmax())]
    exact_qubo = sets[int(f_qubo.argmax())]
    rank_of_qubo_opt = int((f_true > f_true[f_qubo.argmax()]).sum()) + 1
    gap_pct = float(100 * (f_true.max() - f_true[f_qubo.argmax()]) / (f_true.max() - f_true.min()))

    lam_sweep = []
    for lam in (0, 50, 100, 150, 200, 300, 400):
        q = build_qubo(inst, design, lam)
        fq = np.array([q.value(s) for s in sets])
        ft = np.array([design.d_score(s) - lam * inst.risk[list(s)].sum() for s in sets])
        best = sets[int(ft.argmax())]
        lam_sweep.append(dict(lam=lam, exact_true=best, exact_qubo=sets[int(fq.argmax())],
                              spearman=float(spearmanr(fq, ft)[0]),
                              rank_of_qubo_opt=int((ft > ft[fq.argmax()]).sum()) + 1,
                              risk=float(inst.risk[list(best)].sum()),
                              blur_valid_km=valid.blur_km(best)))

    # ---------------------------------------------------------------- 2. quantum: QAOA
    h, const = to_hamiltonian(qubo)
    h_pen, _ = to_hamiltonian(qubo, penalty=PENALTY, k=k)
    e_all = energies(qubo)
    e_feas = np.array([e_all[index(s)] for s in sets])
    feas_idx = np.array([index(s) for s in sets])
    opt_idx = index(exact_qubo)

    reps_list = [1] if quick else [1, 2, 3]
    seeds = [0] if quick else [0, 1, 2, 3, 4]
    restarts = 2 if quick else 3
    runs = []
    for reps in reps_list:
        for seed in seeds:
            t0 = time.time()
            xy = run_xy_qaoa(h, k, reps, seed=seed, restarts=restarts, shots=SHOTS)
            pen = run_penalty_qaoa(h_pen, reps, seed=seed, restarts=restarts, shots=SHOTS)
            p_opt = float(xy["probs"][opt_idx])
            # hybrid finish: classical re-scoring of the most frequently sampled networks
            top = sorted(xy["counts"], key=xy["counts"].get, reverse=True)[:TOP_M]
            final = max(top, key=true_obj)
            runs.append(dict(
                reps=reps, seed=seed, seconds=round(time.time() - t0, 1),
                xy_ratio=float((e_feas.max() - (xy["energy"] + const)) / (e_feas.max() - e_feas.min())),
                xy_p_opt=p_opt, xy_shots_for_95=float(log(0.05) / log(1 - p_opt)),
                xy_feasible=float(xy["probs"][feas_idx].sum()),
                xy_opt_sampled=int(xy["counts"].get(exact_qubo, 0)),
                xy_final=final, xy_final_is_exact=bool(final == exact_true),
                xy_depth=xy["depth"], xy_evaluations=xy["evaluations"],
                pen_feasible=float(pen["probs"][feas_idx].sum()), pen_p_opt=float(pen["probs"][opt_idx]),
                pen_depth=pen["depth"]))
            r = runs[-1]
            print(f"p={reps} seed={seed}  XY: ratio={r['xy_ratio']:.3f} P(opt)={r['xy_p_opt']:.3f} "
                  f"final={final}  | penalty: feasible={r['pen_feasible']:.3f} P(opt)={r['pen_p_opt']:.4f} "
                  f"({r['seconds']}s)")

    best_run = max(runs, key=lambda r: (r["reps"], r["xy_p_opt"]))
    qaoa_pick = tuple(best_run["xy_final"])

    # ---------------------------------------------------------------- 3. classical: baselines + evaluation
    sa_picks = [simulated_annealing(n, k, true_obj, seed=s) for s in range(5)]
    picks = {
        "Exact (brute force, true score)": exact_true,
        "Hybrid QAOA (XY mixer)": qaoa_pick,
        "Greedy forward": greedy_forward(n, k, true_obj),
        "Backward elimination": backward_elimination(n, k, true_obj),
        "Simulated annealing": max(sa_picks, key=true_obj),
        "Random pick (seed 0)": random_pick(n, k, 0),
    }
    blur_all = np.array([valid.blur_km(s) for s in sets])
    methods = {name: dict(sites=list(map(int, sel)), objective=true_obj(sel) - d_empty,
                          risk=float(inst.risk[list(sel)].sum()),
                          blur_design_km=design.blur_km(sel), blur_valid_km=valid.blur_km(sel),
                          rank_true=int((f_true > true_obj(sel) - d_empty + 1e-9).sum()) + 1)
               for name, sel in picks.items()}

    summary = dict(
        instance=dict(design_events=len(inst.design), validation_events=len(inst.valid),
                      permanent_stations=len(inst.stations), candidates=n, k=k,
                      feasible_networks=len(sets), decision_hours=DECISION_HOURS, lam=LAM,
                      access_risk=[round(float(c), 3) for c in inst.risk]),
        formulation=dict(spearman_qubo_vs_true=rho, exact_true=exact_true, exact_qubo=exact_qubo,
                         rank_of_qubo_opt_in_true=rank_of_qubo_opt, gap_pct_of_range=gap_pct,
                         lam_sweep=lam_sweep),
        qaoa=dict(runs=runs, uniform_p_opt=1 / len(sets), shots=SHOTS, penalty=PENALTY,
                  uniform_ratio=float((e_feas.max() - e_feas.mean()) / (e_feas.max() - e_feas.min())),
                  sa_found_exact=int(sum(p == exact_true for p in sa_picks)), sa_runs=len(sa_picks)),
        methods=methods,
        blur=dict(no_new_sensors_design_km=design.blur_km([]), no_new_sensors_valid_km=valid.blur_km([]),
                  mean_random_valid_km=float(blur_all.mean()), best_possible_valid_km=float(blur_all.min()),
                  worst_valid_km=float(blur_all.max())),
        runtime_seconds=round(time.time() - t_start, 1), quick=quick)

    (ROOT / "results").mkdir(exist_ok=True)
    tag = "_quick" if quick else ""      # a quick run never overwrites the full results
    (ROOT / "results" / f"results{tag}.json").write_text(json.dumps(summary, indent=1, default=list))
    make_figures(inst, summary, f_qubo, f_true, rho, qaoa_pick, exact_true, ROOT / f"figures{tag}")

    print("\n=== Summary ===")
    print(f"QUBO vs true score: Spearman rho = {rho:.3f}; QUBO optimum is rank {rank_of_qubo_opt} of {len(sets)} on the true score")
    for name, m in methods.items():
        print(f"{name:34s} sites={m['sites']}  rank={m['rank_true']:3d}/{len(sets)}  blur on later quakes={m['blur_valid_km']:.2f} km")
    print(f"{'No new sensors':34s} blur on later quakes={summary['blur']['no_new_sensors_valid_km']:.2f} km")
    print(f"done in {summary['runtime_seconds']} s -> results/results{tag}.json, figures{tag}/")


# -------------------------------------------------------------------------- figures
def make_figures(inst, s, f_qubo, f_true, rho, qaoa_pick, exact_true, fig_dir: Path) -> None:
    fig_dir.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

    # 1. map
    fig, ax = plt.subplots(figsize=(7.2, 7))
    ax.scatter(*inst.design[:, :2].T, s=6, c=C["grey"], alpha=.6, label=f"Aftershocks, first {DECISION_HOURS} h (used to plan)")
    ax.scatter(*inst.valid[:, :2].T, s=6, c=C["orange"], alpha=.6, label="Later aftershocks (used to test)")
    ax.scatter(*inst.stations.T, marker="^", s=70, c=C["ink"], label="Permanent stations (14)")
    sc = ax.scatter(*inst.candidates.T, s=260, c=inst.risk, cmap="YlOrRd", vmin=0, vmax=1,
                    edgecolors=C["ink"], linewidths=.8, label="Candidate sites (colour = access risk)")
    for i, (x, y) in enumerate(inst.candidates):
        ax.text(x, y, str(i), ha="center", va="center", fontsize=9, fontweight="bold")
    ax.scatter(*inst.candidates[list(qaoa_pick)].T, s=620, facecolors="none", edgecolors=C["blue"],
               linewidths=2.6, label="Chosen by hybrid QAOA")
    ax.scatter(*inst.mainshock[:2], marker="*", s=320, c=C["red"], edgecolors="white", label="M7.1 mainshock")
    ax.set(xlabel="km east", ylabel="km north", aspect="equal",
           title="Ridgecrest 2019: where should 4 portable seismometers go?")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=2, fontsize=8, markerscale=.5, frameon=False)
    fig.colorbar(sc, ax=ax, shrink=.6, label="access risk")
    fig.tight_layout(); fig.savefig(fig_dir / "map.png", dpi=160); plt.close(fig)

    # 2. formulation check
    fig, ax = plt.subplots(figsize=(5.6, 4.6))
    ax.scatter(f_true, f_qubo, s=14, c=C["blue"], alpha=.7)
    ax.set(xlabel="True objective (D-criterion − λ·risk)", ylabel="QUBO objective (pairwise approximation)",
           title=f"All 210 networks: Spearman ρ = {rho:.3f}")
    fig.tight_layout(); fig.savefig(fig_dir / "formulation_check.png", dpi=160); plt.close(fig)

    # 3. QAOA performance
    runs = s["qaoa"]["runs"]
    reps = sorted({r["reps"] for r in runs})
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4))
    for key, lab, col in (("xy_p_opt", "XY mixer + Dicke state (ours)", C["blue"]),
                          ("pen_p_opt", "X mixer + penalty (ablation)", C["orange"])):
        vals = [[r[key] for r in runs if r["reps"] == p] for p in reps]
        axes[0].errorbar(reps, [np.mean(v) for v in vals],
                         yerr=[[np.mean(v) - min(v) for v in vals], [max(v) - np.mean(v) for v in vals]],
                         marker="o", capsize=4, color=col, label=lab)
    axes[0].axhline(s["qaoa"]["uniform_p_opt"], ls="--", c=C["grey"], label="Random allowed network (1/210)")
    axes[0].set(xlabel="QAOA layers p", ylabel="Probability of measuring the best network", xticks=reps, yscale="log")
    axes[0].legend(fontsize=8)
    for key, lab, col in (("xy_feasible", "XY mixer + Dicke state (ours)", C["blue"]),
                          ("pen_feasible", "X mixer + penalty (ablation)", C["orange"])):
        axes[1].plot(reps, [np.mean([r[key] for r in runs if r["reps"] == p]) for p in reps], marker="o", color=col, label=lab)
    axes[1].set(xlabel="QAOA layers p", ylabel="Probability the answer has exactly 4 sites", xticks=reps, ylim=(0, 1.05))
    axes[1].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(fig_dir / "qaoa_performance.png", dpi=160); plt.close(fig)

    # 4. blur by method (validation events)
    b = s["blur"]
    names = ["No new sensors", "Average random network"] + list(s["methods"])
    vals = [b["no_new_sensors_valid_km"], b["mean_random_valid_km"]] + [m["blur_valid_km"] for m in s["methods"].values()]
    cols = [C["grey"], C["grey"]] + [C["blue"] if "QAOA" in nm else C["ink"] for nm in s["methods"]]
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    bars = ax.barh(names[::-1], vals[::-1], color=cols[::-1])
    ax.bar_label(bars, fmt="%.2f km", padding=3, fontsize=9)
    ax.set(xlabel="Mean location uncertainty of later aftershocks (km) — lower is better",
           xlim=(0, max(vals) * 1.18))
    fig.tight_layout(); fig.savefig(fig_dir / "blur_by_method.png", dpi=160); plt.close(fig)

    # 5. risk / accuracy trade-off
    sweep = s["formulation"]["lam_sweep"]
    fig, ax = plt.subplots(figsize=(5.6, 4.2))
    ax.plot([r["risk"] for r in sweep], [r["blur_valid_km"] for r in sweep], marker="o", c=C["green"])
    for r in sweep:
        ax.annotate(f"λ={r['lam']}", (r["risk"], r["blur_valid_km"]), textcoords="offset points", xytext=(6, 5), fontsize=8)
    ax.set(xlabel="Total access risk of the chosen 4 sites", ylabel="Blur on later aftershocks (km)",
           title="Competing objectives: accuracy vs crew risk")
    fig.tight_layout(); fig.savefig(fig_dir / "tradeoff.png", dpi=160); plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="1 seed, p = 1 only")
    main(ap.parse_args().quick)
