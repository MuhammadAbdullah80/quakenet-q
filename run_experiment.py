"""QuakeNet-Q end-to-end experiment.

    python run_experiment.py            # full run (about 30 minutes on a laptop)
    python run_experiment.py --quick    # 1 seed, p = 1 only (about 2 minutes)

Pipeline
  1. classical : real Ridgecrest data -> exact objective over all networks of up to 4 sites
  2. quantum   : Dicke state + XY-mixer QAOA picks 4 of 10 sites (COBYLA tunes the angles)
  3. classical : compare with exact search, classical heuristics and an expert rule, then test
                 every network in an independent simulated location experiment on LATER aftershocks

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

from src.baselines import (azimuthal_gap, backward_elimination, expert_rule, greedy_forward, random_pick,
                           simulated_annealing)
from src.geometry import DECISION_HOURS, Scorer, load_instance
from src.location import V_TRUE, dn_score, location_errors
from src.qaoa_solver import extend_angles, run_penalty_qaoa, run_xy_qaoa, xy_qaoa_circuit
from src.qubo import build_objective, energies, to_hamiltonian

warnings.filterwarnings("ignore", category=Warning, module="scipy")

ROOT = Path(__file__).resolve().parent
LAM = 150.0          # information units one unit of access risk must buy
PENALTY = 2.0        # penalty weight of the ablation (scaled units, largest coefficient = 1)
SHOTS = 1024
TOP_M = 10           # sampled networks re-scored classically
C = dict(ink="#1f2933", grey="#9aa5b1", blue="#2563eb", orange="#ea580c", green="#059669", red="#dc2626")


def index(sel) -> int:
    return sum(1 << i for i in sel)


def main(quick: bool) -> None:
    t_start = time.time()
    inst = load_instance()
    design, valid = Scorer(inst, inst.design), Scorer(inst, inst.valid)
    sets = inst.feasible_sets()
    n, k = inst.n, inst.k
    d_empty = design.d_score([])

    def true_obj(sel) -> float:           # the objective we care about, computed directly
        return design.d_score(sel) - LAM * float(inst.risk[list(sel)].sum()) - d_empty

    f_true = np.array([true_obj(s) for s in sets])
    exact_true = sets[int(f_true.argmax())]

    # ---------------------------------------------------------------- 1. classical: formulation
    objectives = {order: build_objective(inst, design, LAM, order) for order in (2, 3, 4)}
    exact = objectives[4]
    fidelity = []
    for order, obj in objectives.items():
        f = np.array([obj.value(s) for s in sets])
        h_o, _ = to_hamiltonian(obj)
        fidelity.append(dict(
            order=order, terms=len(obj.terms), spearman=float(spearmanr(f, f_true)[0]),
            max_abs_error=float(np.abs(f - f_true).max()),
            rank_of_its_optimum=int((f_true > f_true[f.argmax()] + 1e-9).sum()) + 1,
            gates_one_layer=xy_qaoa_circuit(h_o, k, 1).decompose(reps=3).size()))
    f_pair = np.array([objectives[2].value(s) for s in sets])

    lam_sweep = []
    for lam in (0, 50, 100, 150, 200, 300, 400):
        ft = np.array([design.d_score(s) - lam * inst.risk[list(s)].sum() for s in sets])
        pair = build_objective(inst, design, lam, 2)
        fp = np.array([pair.value(s) for s in sets])
        best = sets[int(ft.argmax())]
        lam_sweep.append(dict(lam=lam, exact_true=best, pairwise_optimum=sets[int(fp.argmax())],
                              rank_of_pairwise_optimum=int((ft > ft[fp.argmax()] + 1e-9).sum()) + 1,
                              risk=float(inst.risk[list(best)].sum()), blur_valid_km=valid.blur_km(best)))

    # ---------------------------------------------------------------- 2. quantum: QAOA on the exact objective
    h, const = to_hamiltonian(exact)
    h_pen, _ = to_hamiltonian(objectives[2], penalty=PENALTY, k=k)   # ablation uses the pairwise QUBO
    e_all = energies(exact)
    e_feas = np.array([e_all[index(s)] for s in sets])
    feas_idx = np.array([index(s) for s in sets])
    opt_idx = index(exact_true)

    reps_list = [1] if quick else [1, 2, 3]
    seeds = [0] if quick else [0, 1, 2, 3, 4]
    runs = []
    for seed in seeds:
        warm = None
        for reps in reps_list:
            t0 = time.time()
            xy = run_xy_qaoa(h, k, reps, seed=seed, restarts=2, shots=SHOTS, init=warm)
            warm = extend_angles(xy["theta"], reps)
            pen = run_penalty_qaoa(h_pen, reps, seed=seed, restarts=3, shots=SHOTS)
            p_opt = float(xy["probs"][opt_idx])
            top = sorted(xy["counts"], key=xy["counts"].get, reverse=True)[:TOP_M]
            final = max(top, key=true_obj)
            runs.append(dict(
                reps=reps, seed=seed, seconds=round(time.time() - t0, 1),
                xy_ratio=float((e_feas.max() - (xy["energy"] + const)) / (e_feas.max() - e_feas.min())),
                xy_p_opt=p_opt, xy_shots_for_95=float(log(0.05) / log(1 - p_opt)),
                xy_feasible=float(xy["probs"][feas_idx].sum()),
                xy_opt_sampled=int(xy["counts"].get(exact_true, 0)),
                xy_most_likely_is_exact=bool(int(np.argmax(xy["probs"])) == opt_idx),
                xy_final=final, xy_final_is_exact=bool(final == exact_true),
                xy_depth=xy["depth"], xy_gates=xy["gates"], xy_evaluations=xy["evaluations"],
                pen_feasible=float(pen["probs"][feas_idx].sum()), pen_p_opt=float(pen["probs"][opt_idx]),
                pen_depth=pen["depth"]))
            r = runs[-1]
            print(f"p={reps} seed={seed}  XY: ratio={r['xy_ratio']:.3f} P(opt)={r['xy_p_opt']:.3f} "
                  f"final={final}  | penalty: feasible={r['pen_feasible']:.3f} P(opt)={r['pen_p_opt']:.4f} "
                  f"({r['seconds']}s)", flush=True)

    best_run = max(runs, key=lambda r: (r["reps"], r["xy_p_opt"]))
    qaoa_pick = tuple(best_run["xy_final"])

    # ---------------------------------------------------------------- 3. classical: baselines + independent tests
    centre = inst.design[:, :2].mean(axis=0)
    sa_picks = [simulated_annealing(n, k, true_obj, seed=s) for s in range(5)]
    dn = np.array([dn_score(inst, s, inst.design) for s in sets])
    d_plain = np.array([design.d_score(s) for s in sets])
    picks = {
        "Exact (brute force)": exact_true,
        "Hybrid QAOA (XY mixer)": qaoa_pick,
        "Greedy forward": greedy_forward(n, k, true_obj),
        "Backward elimination": backward_elimination(n, k, true_obj),
        "Simulated annealing": max(sa_picks, key=true_obj),
        "Expert rule (azimuthal gap)": expert_rule(inst.stations, inst.candidates, centre, k),
        "Best by D_N criterion": sets[int(dn.argmax())],
        "Random pick (seed 0)": random_pick(n, k, 0),
    }

    # Independent location experiment: every network once, the named methods three times.
    if quick:
        chosen = np.random.default_rng(0).choice(len(sets), 30, replace=False)
        pool = [sets[i] for i in chosen]
    else:
        pool = sets
    loc_all = np.array([location_errors(inst, s, inst.valid, trials=1).mean() for s in pool])
    loc_none = location_errors(inst, (), inst.valid, trials=3)

    methods = {}
    for name, sel in picks.items():
        err = location_errors(inst, sel, inst.valid, trials=3)
        network = np.vstack([inst.stations, inst.candidates[list(sel)]])
        methods[name] = dict(
            sites=list(map(int, sel)), objective=true_obj(sel), risk=float(inst.risk[list(sel)].sum()),
            rank_true=int((f_true > true_obj(sel) + 1e-9).sum()) + 1,
            blur_valid_km=valid.blur_km(sel),
            loc_error_mean_km=float(err.mean()), loc_error_median_km=float(np.median(err)),
            loc_error_p90_km=float(np.percentile(err, 90)),
            azimuthal_gap_deg=azimuthal_gap(network, centre))
    qaoa_loc_once = float(location_errors(inst, qaoa_pick, inst.valid, trials=1).mean())

    summary = dict(
        instance=dict(design_events=len(inst.design), validation_events=len(inst.valid),
                      permanent_stations=len(inst.stations), candidates=n, k=k,
                      feasible_networks=len(sets), decision_hours=DECISION_HOURS, lam=LAM,
                      access_risk=[round(float(c), 3) for c in inst.risk]),
        formulation=dict(fidelity=fidelity, exact_true=exact_true, lam_sweep=lam_sweep),
        qaoa=dict(runs=runs, uniform_p_opt=1 / len(sets), shots=SHOTS, penalty=PENALTY,
                  uniform_ratio=float((e_feas.max() - e_feas.mean()) / (e_feas.max() - e_feas.min())),
                  sa_found_exact=int(sum(p == exact_true for p in sa_picks)), sa_runs=len(sa_picks)),
        methods=methods,
        blur=dict(no_new_sensors_valid_km=valid.blur_km([]),
                  mean_random_valid_km=float(np.mean([valid.blur_km(s) for s in sets])),
                  best_possible_valid_km=float(min(valid.blur_km(s) for s in sets))),
        location_test=dict(
            v_true=V_TRUE, networks_tested=len(pool),
            no_new_sensors_mean_km=float(loc_none.mean()), no_new_sensors_median_km=float(np.median(loc_none)),
            all_networks_mean_km=float(loc_all.mean()), best_network_km=float(loc_all.min()),
            worst_network_km=float(loc_all.max()),
            rank_of_qaoa_pick=int((loc_all < qaoa_loc_once - 1e-12).sum()) + 1,
            spearman_d_vs_error=None if quick else float(spearmanr(d_plain, loc_all)[0]),
            spearman_dn_vs_error=None if quick else float(spearmanr(dn, loc_all)[0]),
            spearman_d_vs_dn=float(spearmanr(d_plain, dn)[0])),
        runtime_seconds=round(time.time() - t_start, 1), quick=quick)

    tag = "_quick" if quick else ""      # a quick run never overwrites the full results
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / f"results{tag}.json").write_text(json.dumps(summary, indent=1, default=list))
    make_figures(inst, summary, f_pair, f_true, qaoa_pick, ROOT / f"figures{tag}")

    print("\n=== Summary ===")
    for f in fidelity:
        print(f"objective with terms up to {f['order']} sites: {f['terms']} terms, Spearman {f['spearman']:.4f}, "
              f"max error {f['max_abs_error']:.2g}")
    lt = summary["location_test"]
    print(f"{'No new sensors':30s} location error={lt['no_new_sensors_mean_km']:.2f} km")
    for name, m in methods.items():
        print(f"{name:30s} sites={m['sites']} rank={m['rank_true']:3d}/{len(sets)} "
              f"location error={m['loc_error_mean_km']:.2f} km")
    print(f"done in {summary['runtime_seconds']} s -> results/results{tag}.json, figures{tag}/")


# -------------------------------------------------------------------------- figures
def make_figures(inst, s, f_pair, f_true, qaoa_pick, fig_dir: Path) -> None:
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
    fid = {f["order"]: f for f in s["formulation"]["fidelity"]}
    fig, ax = plt.subplots(figsize=(5.8, 4.6))
    ax.scatter(f_true, f_pair, s=14, c=C["blue"], alpha=.7)
    ax.set(xlabel="True objective (D-criterion − λ·risk)", ylabel="Pairwise approximation (terms up to 2 sites)",
           title=f"Pairwise: ρ = {fid[2]['spearman']:.3f}. Terms up to 4 sites: exact")
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

    # 4. independent location test (later aftershocks, wrong wave speed, noisy readings)
    lt = s["location_test"]
    show = ["Exact (brute force)", "Hybrid QAOA (XY mixer)", "Best by D_N criterion", "Expert rule (azimuthal gap)"]
    names = ["No new sensors", "Average of all networks"] + show
    vals = [lt["no_new_sensors_mean_km"], lt["all_networks_mean_km"]] + [s["methods"][m]["loc_error_mean_km"] for m in show]
    cols = [C["grey"], C["grey"]] + [C["blue"] if "QAOA" in m else C["ink"] for m in show]
    fig, ax = plt.subplots(figsize=(7.6, 3.6))
    bars = ax.barh(names[::-1], vals[::-1], color=cols[::-1])
    ax.bar_label(bars, fmt="%.2f km", padding=3, fontsize=9)
    ax.set(xlabel="Mean error when locating later aftershocks (km), lower is better", xlim=(0, max(vals) * 1.18))
    fig.tight_layout(); fig.savefig(fig_dir / "location_test.png", dpi=160); plt.close(fig)

    # 5. risk / accuracy trade-off
    sweep = s["formulation"]["lam_sweep"]
    fig, ax = plt.subplots(figsize=(5.6, 4.2))
    ax.plot([r["risk"] for r in sweep], [r["blur_valid_km"] for r in sweep], marker="o", c=C["green"])
    for r in sweep:
        ax.annotate(f"λ={r['lam']}", (r["risk"], r["blur_valid_km"]), textcoords="offset points", xytext=(6, 5), fontsize=8)
    ax.set(xlabel="Total access risk of the chosen 4 sites", ylabel="Predicted blur on later aftershocks (km)",
           title="Competing objectives: accuracy vs crew risk")
    fig.tight_layout(); fig.savefig(fig_dir / "tradeoff.png", dpi=160); plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="1 seed, p = 1 only")
    main(ap.parse_args().quick)
