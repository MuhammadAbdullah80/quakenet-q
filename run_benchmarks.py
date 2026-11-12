"""QuakeNet-Q benchmark run over the benchmark earthquakes.

    python run_benchmarks.py                 # every benchmark with enough data
    python run_benchmarks.py --quick         # 1 layer, fewer restarts: a smoke test of the pipeline
    python run_benchmarks.py --retry-roads   # first ask Overpass once more for missing road answers

For each benchmark earthquake (skipped, with the reason, when the data is too thin):
  1. plan at hour 12: real aftershocks so far (topped up with synthetic ones under 30), 10
     candidate sites by greedy spread selection (Ridgecrest: the published 10), choose 4;
  2. exact optimum by enumerating all 210 networks of the exact objective (src.qubo, order 4);
  3. XY-mixer QAOA at 3 layers in four variants:
       mean-cold  : minimise the mean energy, random starts (computed exactly as CVaR with alpha = 1,
                    which is the mean of the whole distribution);
       cvar-cold  : minimise the CVaR (best alpha fraction), random starts;
       mean-warm  : mean energy, starting only from the median of the best angles found on the
                    OTHER earthquakes (leave-one-out, so no earthquake sees its own answer);
       cvar-warm  : the same with CVaR;
     Before tuning, the cost is divided by a constant so that the energies of the 210 allowed
     networks span ENERGY_SPAN units: the expansion's own scale (largest coefficient = 1) left the
     allowed networks within about 0.4 units of each other, so the useful angles were near 10 and
     random starts in [-0.5, 0.5] never reached them. A constant factor changes only the angle
     scale, not which network is best. The angles are put in a canonical sign (P(theta) = P(-theta)
     for this circuit, checked at run time) so that medians across earthquakes make sense.
     P(best) per measurement is read from the exact output distribution of the tuned circuit;
     the final pick is the best (by the true objective) of the 10 most frequent sampled networks;
  4. classical references: the expert rule (azimuthal gap) and greedy forward selection;
  5. the simulated location test on the later aftershocks (hours 12 to 168): plain (constant
     0.1 s picking error, every station hears every event) and with hearing range.

Writes results/benchmarks.json and research/benchmarks/2026-11-12_benchmark_results.md. Every
number in the Markdown comes from this run. Uses the cache in data/cache (set QUAKENET_OFFLINE=1
to forbid network use).
"""
from __future__ import annotations

import argparse
import json
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from src import instances
from src.baselines import expert_rule, greedy_forward
from src.geometry import Scorer
from src.location import V_TRUE, location_errors
from src.qaoa_solver import run_xy_qaoa
from src.qubo import build_objective, energies, to_hamiltonian
from src.sources import BENCHMARKS, QuakeNetError

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent
OUT_JSON = ROOT / "results" / "benchmarks.json"
OUT_MD = ROOT / "research" / "benchmarks" / "2026-11-12_benchmark_results.md"

AT_HOURS = 12.0
N_SITES, K = 10, 4
LAM = 150.0
CVAR_ALPHA = 0.1       # mean of the best 10 % of outcomes (best of 0.25 / 0.1 / 0.05 in a trial on two events)
ENERGY_SPAN = 3.0      # energies of the 210 allowed networks are rescaled to span this many units
TARGET = 0.20          # decision 7: aim for 20 % chance of the best network per measurement
SHOTS = 1024
TOP_M = 10
MIN_VALID = 10         # fewer later aftershocks than this cannot test a network
VARIANTS = ("mean-cold", "cvar-cold", "mean-warm", "cvar-warm")


def index(sel) -> int:
    return sum(1 << i for i in sel)


def prepare(event_id: str) -> dict:
    """Instance, objective and exact optimum of one earthquake, or {"skipped": reason}."""
    data = instances.load_event_data(event_id)
    events, synthetic = instances.planning_events(data, AT_HOURS, min_real=30, seed=0)
    valid = data.aftershocks[(data.aftershocks[:, 4] > AT_HOURS)]
    base = dict(event_id=event_id, name=data.name, magnitude=data.magnitude,
                real_events_at_12h=int((data.aftershocks[:, 4] <= AT_HOURS).sum()),
                design_events=len(events), synthetic_used=bool(synthetic), valid_events=len(valid),
                stations=len(data.stations), pool=len(data.pool), feasibility_checked=data.feasibility_checked)
    if len(valid) < MIN_VALID:
        return dict(base, skipped=f"only {len(valid)} later aftershocks (M >= 2.5, 12 h to 7 days) to test on; "
                                  f"at least {MIN_VALID} needed")
    cands, _ = instances.select_sites(data, events, n=N_SITES)
    if len(cands) < N_SITES:
        return dict(base, skipped=f"only {len(cands)} candidate sites at 4 km spacing in the pool")
    inst = instances.make_instance(data, cands, events, k=K, valid=valid)
    design = Scorer(inst, inst.design)
    d0 = design.d_score([])
    sets = inst.feasible_sets()

    def true_obj(sel) -> float:
        return design.d_score(list(sel)) - LAM * float(inst.risk[list(sel)].sum()) - d0

    f = np.array([true_obj(s) for s in sets])
    obj = build_objective(inst, design, LAM, order=K)
    h, _ = to_hamiltonian(obj)
    diag = energies(obj)
    feas = np.array([index(s) for s in sets])
    factor = ENERGY_SPAN / float(np.ptp(diag[feas]))
    h, diag = h * factor, diag * factor
    return dict(base, inst=inst, energy_factor=factor, true_obj=true_obj, sets=sets, f=f, exact=sets[int(f.argmax())],
                h=h, diag=diag, max_abs_expansion_error=float(np.abs([obj.value(s) for s in sets] - f).max()))


def run_variant(p: dict, variant: str, layers: int, seed: int, restarts: int, maxiter: int, init=None) -> dict:
    objective, start = variant.split("-")
    kw = dict(cvar_alpha=CVAR_ALPHA if objective == "cvar" else 1.0, diag=p["diag"])
    if start == "warm":
        kw.update(init=init, restarts=0)
    else:
        kw.update(restarts=restarts)
    t0 = time.time()
    r = run_xy_qaoa(p["h"], K, layers, seed=seed, shots=SHOTS, maxiter=maxiter, **kw)
    probs, exact = r["probs"], p["exact"]
    theta = np.array(r["theta"])
    if theta[layers] < 0:                       # canonical sign: gamma_0 >= 0
        theta = -theta
    counts = {s: c for s, c in r["counts"].items() if len(s) == K}
    top = sorted(counts, key=counts.get, reverse=True)[:TOP_M]
    final = max(top, key=p["true_obj"]) if top else None
    feas = np.array([index(s) for s in p["sets"]])
    return dict(variant=variant, seed=seed, p_best=float(probs[index(exact)]),
                valid_fraction=float(probs[feas].sum()), best_sampled=int(r["counts"].get(exact, 0)),
                most_likely_is_exact=bool(int(np.argmax(probs)) == index(exact)),
                final_sites=list(final) if final else None, final_is_exact=final == exact,
                final_rank=int((p["f"] > p["true_obj"](final) + 1e-9).sum()) + 1 if final else None,
                evaluations=r["evaluations"], seconds=round(time.time() - t0, 1), theta=theta.tolist(),
                objective_value=float(r["cvar"]))


def location_test(p: dict, picks: dict[str, tuple]) -> dict:
    """Mean 3-D location error on the later aftershocks for each named network, plain and with
    hearing range. With hearing, events that some network cannot locate (fewer than 4 stations
    hear them) are left out of every mean, so all networks are compared on the same events."""
    inst = p["inst"]
    plain = {name: location_errors(inst, tuple(sel), inst.valid, trials=1) for name, sel in picks.items()}
    hear = {name: location_errors(inst, tuple(sel), inst.valid, trials=1, hearing=True) for name, sel in picks.items()}
    common = np.all([np.isfinite(e) for e in hear.values()], axis=0)
    return {name: dict(sites=list(map(int, sel)), objective=p["true_obj"](sel),
                       rank=int((p["f"] > p["true_obj"](sel) + 1e-9).sum()) + 1 if len(sel) == K else None,
                       loc_mean_km=float(plain[name].mean()),
                       loc_mean_km_hearing=float(hear[name][common].mean()) if common.any() else None,
                       unlocated_hearing=int((~np.isfinite(hear[name])).sum()))
            for name, sel in picks.items()} | {"_hearing_common_events": int(common.sum())}


def check_sign_symmetry(p: dict, layers: int) -> float:
    """Largest change in the output distribution when every angle changes sign (should be ~0)."""
    from src.qaoa_solver import XYQaoaSimulator
    sim = XYQaoaSimulator(p["h"], K, layers)
    theta = np.random.default_rng(1).uniform(-1, 1, 2 * layers)
    return float(np.abs(sim.probabilities(theta) - sim.probabilities(-theta)).max())


def aggregate(per_seed: list[dict]) -> dict:
    pb = [r["p_best"] for r in per_seed]
    return dict(p_best_mean=float(np.mean(pb)), p_best_min=float(min(pb)), p_best_max=float(max(pb)),
                final_exact=int(sum(r["final_is_exact"] for r in per_seed)), runs=len(per_seed),
                valid_fraction_min=float(min(r["valid_fraction"] for r in per_seed)),
                seconds=float(sum(r["seconds"] for r in per_seed)))


def main(quick: bool, retry_roads: bool, only: list[str] | None, seeds: list[int]) -> None:
    t_start = time.time()
    layers = 1 if quick else 3
    restarts = 2 if quick else 10
    maxiter = 100 if quick else 400
    keys = [k for k in BENCHMARKS if not only or k in only]

    road_retries = {}
    if retry_roads:
        for key in keys:
            road_retries[key] = instances.retry_road_query(key)
            print("roads", road_retries[key], flush=True)

    prepared = {}
    for key in keys:
        try:
            prepared[key] = prepare(key)
        except QuakeNetError as err:
            prepared[key] = dict(event_id=key, name=BENCHMARKS[key]["name"], skipped=f"data unavailable: {err}")
        p = prepared[key]
        print(f"{key}: " + (f"SKIPPED ({p['skipped']})" if "skipped" in p else
                            f"{p['design_events']} design events (synthetic: {p['synthetic_used']}), "
                            f"{p['valid_events']} later, exact optimum {p['exact']}"), flush=True)
    usable = [k for k in keys if "skipped" not in prepared[k]]
    symmetry = max((check_sign_symmetry(prepared[k], layers) for k in usable), default=0.0)
    if symmetry > 1e-9:
        raise RuntimeError(f"P(theta) != P(-theta) (difference {symmetry}); the sign canonicalisation is invalid")

    runs: dict[str, dict[str, list]] = {k: {} for k in usable}

    def go(key, variant, seed, init=None):
        r = run_variant(prepared[key], variant, layers, seed, restarts, maxiter, init=init)
        runs[key].setdefault(variant, []).append(r)
        print(f"  {key} {variant} seed {seed}: P(best)={r['p_best']:.3f} final={r['final_sites']} "
              f"exact={r['final_is_exact']} ({r['seconds']} s)", flush=True)
        return r

    for key in usable:                                    # cold starts first: they feed the warm starts
        for variant in ("mean-cold", "cvar-cold"):
            for seed in seeds:
                go(key, variant, seed)
    for key in usable:
        for objective in ("mean", "cvar"):
            # best angles of each OTHER earthquake: its cold run (over seeds) with the lowest objective
            others = [min(runs[o][f"{objective}-cold"], key=lambda r: r["objective_value"])["theta"]
                      for o in usable if o != key]
            if not others:
                continue
            init = np.median(np.array(others), axis=0)
            for seed in seeds:
                r = go(key, f"{objective}-warm", seed, init=init)
                r["init"] = [float(x) for x in init]

    results = []
    for key in keys:
        p = prepared[key]
        row = {k: v for k, v in p.items() if k not in ("inst", "true_obj", "sets", "f", "h", "diag")}
        if "skipped" in p:
            results.append(row)
            continue
        inst = p["inst"]
        centre = inst.design[:, :2].mean(axis=0)
        picks = {"exact": p["exact"],
                 "expert_rule": expert_rule(inst.stations, inst.candidates, centre, K),
                 "greedy": greedy_forward(inst.n, K, p["true_obj"]),
                 "no_new_sensors": ()}
        for variant, rs in runs[key].items():            # the first seed's final pick is tested
            if rs[0]["final_sites"]:
                picks[f"qaoa_{variant}"] = tuple(rs[0]["final_sites"])
        t0 = time.time()
        methods = location_test(p, picks)
        common = methods.pop("_hearing_common_events")
        row.update(exact=list(p["exact"]), exact_objective=float(p["f"].max()), uniform_p_best=1 / len(p["sets"]),
                   variants={v: dict(aggregate(rs), per_seed=rs) for v, rs in runs[key].items()},
                   methods=methods, hearing_common_events=common,
                   location_seconds=round(time.time() - t0, 1),
                   risk=[round(float(c), 3) for c in inst.risk])
        exp_plain, exp_hear = methods["expert_rule"]["loc_mean_km"], methods["expert_rule"]["loc_mean_km_hearing"]
        row["gain_over_expert"] = {
            name: dict(plain_km=exp_plain - m["loc_mean_km"], plain_pct=100 * (exp_plain - m["loc_mean_km"]) / exp_plain,
                       hearing_km=(exp_hear - m["loc_mean_km_hearing"]) if exp_hear is not None else None,
                       hearing_pct=(100 * (exp_hear - m["loc_mean_km_hearing"]) / exp_hear)
                       if exp_hear is not None else None)
            for name, m in methods.items() if name not in ("expert_rule", "no_new_sensors")}
        print(f"  {key}: location test done ({row['location_seconds']} s)", flush=True)
        results.append(row)

    summary = dict(
        generated_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        settings=dict(at_hours=AT_HOURS, candidates=N_SITES, sensors=K, layers=layers, lam=LAM, cvar_alpha=CVAR_ALPHA,
                      target_p_best=TARGET, shots=SHOTS, restarts_cold=restarts, maxiter=maxiter, seeds=seeds,
                      energy_span=ENERGY_SPAN,
                      top_m=TOP_M, v_true=V_TRUE, min_valid_events=MIN_VALID, quick=quick),
        road_retries=road_retries, events=results, runtime_seconds=round(time.time() - t_start, 1))
    out_json = OUT_JSON.with_name("benchmarks_quick.json") if quick else OUT_JSON
    out_json.write_text(json.dumps(summary, indent=1, default=_json_default), encoding="utf-8")
    md = render(summary)
    out_md = OUT_MD.with_name(OUT_MD.stem + "_quick.md") if quick else OUT_MD
    out_md.write_text(md, encoding="utf-8")
    print(f"wrote {out_json} and {out_md} in {summary['runtime_seconds']} s")


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


# --------------------------------------------------------------------------- report

def _f(x, nd=2, unit=""):
    return "n/a" if x is None else f"{x:.{nd}f}{unit}"


def render(s: dict) -> str:
    st = s["settings"]
    L = [
        "# Benchmark earthquakes: QAOA variants and the location test",
        "",
        f"Generated {s['generated_utc']} by `run_benchmarks.py` in {s['runtime_seconds'] / 60:.1f} minutes. Every "
        "number below comes from that run (`results/benchmarks.json`), on data cached in `data/cache/`.",
        "",
        "## Set-up",
        "",
        f"- Plan at hour {st['at_hours']:.0f} after the mainshock, {st['candidates']} candidate sites, choose "
        f"{st['sensors']}; risk weight {st['lam']:.0f}. Real aftershocks (M >= 2.5) known by then; topped up "
        "with synthetic ones when fewer than 30 exist.",
        "- Candidates: greedy spread selection on single-site gain from the road-checked pool (Ridgecrest: the "
        "10 published sites).",
        f"- QAOA: Dicke state + XY ring mixer, {st['layers']} layers, {st['shots']} shots, COBYLA up to "
        f"{st['maxiter']} evaluations per start. Energies of the allowed networks rescaled to span "
        f"{st['energy_span']:.0f} units before tuning (a constant factor; it changes the angle scale only). Cold starts use "
        f"{st['restarts_cold']} random starts per seed, seeds {st['seeds']}; warm starts use only the median of the "
        "best angles found on the "
        "other earthquakes (leave-one-out). CVaR uses alpha = "
        f"{st['cvar_alpha']} (the mean energy of the best 10% of the outcomes); the mean objective is computed exactly "
        "as CVaR with alpha = 1.",
        "- **P(best)** is the chance that one measurement gives the exact best network, read from the exact "
        f"output distribution of the tuned circuit. The target (decision 7) is {st['target_p_best']:.0%}. A random "
        "valid network has 1/210 = 0.48%.",
        "- **Final pick**: the best of the 10 most frequent sampled networks, re-scored with the true objective.",
        f"- **Location test**: the later aftershocks (12 h to 7 days) are located with each network in a "
        f"simulation (true wave speed {st['v_true']} km/s, planner assumes 6.0). *Plain*: every station hears "
        "every event with a 0.1 s picking error. *Hearing range*: a station whose simulated signal-to-noise is "
        "under 5 gives no reading and weak readings are noisier (a simplified attenuation law with an assumed "
        "noise level; see `src/geometry.py`). With hearing range, events that some network cannot locate are left "
        "out of every mean, so all networks are compared on the same events.",
        "- **Gain over the expert rule** = expert-rule error minus the network's error (positive = better than "
        "the expert rule). These are simulated errors, not measured ones.",
        "",
        "## Summary",
        "",
        "| Earthquake | P(best) mean-cold | P(best) cvar-cold | P(best) mean-warm | P(best) cvar-warm | Final pick exact? "
        "(runs; mc / cc / mw / cw) | Exact optimum: gain over expert, plain | with hearing range |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for e in s["events"]:
        if "skipped" in e:
            L.append(f"| {e['name']} | skipped: {e['skipped']} | | | | | | |")
            continue
        v = e["variants"]
        pb = [f"{v[x]['p_best_mean']:.1%}" if x in v else "n/a" for x in VARIANTS]
        ex = " / ".join(f"{v[x]['final_exact']}/{v[x]['runs']}" if x in v else "-" for x in VARIANTS)
        g = e["gain_over_expert"]["exact"]
        L.append(f"| {e['name']} | {' | '.join(pb)} | {ex} | {_f(g['plain_km'])} km ({_f(g['plain_pct'], 1)}%) | "
                 f"{_f(g['hearing_km'])} km ({_f(g['hearing_pct'], 1)}%) |")
    L += ["", "## Per earthquake", ""]
    for e in s["events"]:
        L.append(f"### {e['name']} ({e['event_id']})")
        L.append("")
        if "skipped" in e:
            L += [f"**Skipped:** {e['skipped']}.", ""]
            if "design_events" in e:
                L += [f"Data: {e['real_events_at_12h']} real aftershocks by hour 12, {e['valid_events']} later; "
                      f"{e['stations']} permanent stations; pool {e['pool']} points.", ""]
            continue
        L += [f"- Planning events: {e['design_events']} ({e['real_events_at_12h']} real by hour 12"
              + (", topped up with synthetic events" if e["synthetic_used"] else "") + f"); "
              f"later aftershocks for the test: {e['valid_events']}; permanent stations: {e['stations']}; "
              f"pool: {e['pool']} points, road-checked: {'yes' if e['feasibility_checked'] else '**no**'}.",
              f"- Exact optimum: sites {e['exact']} (objective {e['exact_objective']:.1f}). Largest error of the "
              f"expanded objective over all 210 networks: {e['max_abs_expansion_error']:.2e} (it is exact).",
              "",
              "| QAOA variant | Seed | P(best) | vs 20% target | Valid outcomes | Most likely = best? | Final pick | "
              "Rank | Exact? | Evaluations | Seconds |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for name in VARIANTS:
            agg = e["variants"].get(name)
            if not agg:
                L.append(f"| {name} | - | n/a | | | | | | | | |")
                continue
            for r in agg["per_seed"]:
                L.append(f"| {name} | {r['seed']} | {r['p_best']:.1%} | {'met' if r['p_best'] >= TARGET else 'missed'} | "
                         f"{r['valid_fraction']:.3f} | {'yes' if r['most_likely_is_exact'] else 'no'} | "
                         f"{r['final_sites']} | {r['final_rank']} | {'yes' if r['final_is_exact'] else '**no**'} | "
                         f"{r['evaluations']} | {r['seconds']} |")
        L += ["", f"Location test ({e['valid_events']} later aftershocks; with hearing range, "
                  f"{e['hearing_common_events']} events are located by every network):", "",
              "| Network | Sites | Rank | Mean error, plain (km) | Gain over expert, plain | Mean error, hearing "
              "(km) | Gain over expert, hearing | Not locatable (hearing) |",
              "|---|---|---|---|---|---|---|---|"]
        for name, m in e["methods"].items():
            g = e["gain_over_expert"].get(name)
            gp = f"{g['plain_km']:+.2f} km ({g['plain_pct']:+.1f}%)" if g else "-"
            gh = f"{g['hearing_km']:+.2f} km ({g['hearing_pct']:+.1f}%)" if g and g["hearing_km"] is not None else "-"
            L.append(f"| {name} | {m['sites']} | {m['rank'] if m['rank'] else '-'} | {m['loc_mean_km']:.2f} | {gp} | "
                     f"{_f(m['loc_mean_km_hearing'])} | {gh} | {m['unlocated_hearing']} |")
        L.append("")
    L += _honest_summary(s)
    return "\n".join(L) + "\n"


def _honest_summary(s: dict) -> list[str]:
    done = [e for e in s["events"] if "skipped" not in e]
    L = ["## What this shows (and does not)", ""]
    if not done:
        return L + ["No earthquake had enough data.", ""]
    for name in VARIANTS:
        runs_ = [r for e in done if name in e["variants"] for r in e["variants"][name]["per_seed"]]
        vals = [r["p_best"] for r in runs_]
        if vals:
            L.append(f"- **{name}**: P(best) median {np.median(vals):.1%} over {len(vals)} runs (range {min(vals):.1%} "
                     f"to {max(vals):.1%}); met the 20% target in {sum(v >= TARGET for v in vals)} of {len(vals)} runs; "
                     f"final pick was the exact optimum in {sum(r['final_is_exact'] for r in runs_)} of {len(vals)}.")
    gains = [e["gain_over_expert"]["exact"] for e in done]
    L.append(f"- **Exact optimum vs the expert rule, plain location test**: gain "
             + ", ".join(f"{e['name']} {g['plain_km']:+.2f} km ({g['plain_pct']:+.1f}%)" for e, g in zip(done, gains)) + ".")
    L.append(f"- **Same, with hearing range**: "
             + ", ".join(f"{e['name']} {_f(g['hearing_km'])} km ({_f(g['hearing_pct'], 1)}%)" for e, g in zip(done, gains))
             + ".")
    L += [f"- {len(s['settings']['seeds'])} seeds per variant and one simulated noise draw per event in the location "
          "test (the first seed's final pick is tested): differences of a few percent in P(best) or a few hundredths "
          "of a km are within run-to-run variation and should not be read as real.",
          "- The location errors come from a simulation with a uniform-velocity Earth; they are model predictions, "
          "not measured errors. The hearing-range model uses assumed constants (one noise level for every site).",
          "- No quantum speedup is claimed: the exact optimum is found by enumerating 210 networks in well under a "
          "second.", ""]
    skipped = [e for e in s["events"] if "skipped" in e]
    if skipped:
        L.append("Skipped: " + "; ".join(f"{e['name']} ({e['skipped']})" for e in skipped) + ".")
        L.append("")
    return L


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--retry-roads", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--seeds", type=int, default=3)
    a = ap.parse_args()
    main(a.quick, a.retry_roads, a.only, list(range(a.seeds)))
