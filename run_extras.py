"""Runs the two results the report quotes that are not in run_experiment.py or run_benchmarks.py.

    python run_extras.py        # about a minute

1. The simulated gate-noise study (src/noise.py) on the default 6-site, choose-2 Ridgecrest instance.
2. A 24-hour Ridgecrest replay of the agent with default settings and an empty memory, so the run
   does not depend on what the team laptop has already learned.

Writes results/extras.json.
"""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from src.agent.memory import Memory
from src.agent.planner import Budget
from src.agent.sequence import SequenceStore, run_replay
from src.agent.settings import AgentSettings
from src.agent.toolkit import default_toolkit
from src.noise import noise_study

ROOT = Path(__file__).resolve().parent


def replay(hours: int = 24, step: int = 1) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        settings = AgentSettings(tmp / "settings.json").values()
        tk = default_toolkit()
        data = tk.load_event_data("ridgecrest2019")
        store = SequenceStore(tmp / "sequences")
        t0 = time.time()
        run_replay(data, hours=hours, step_hours=step, settings=settings, toolkit=tk,
                   memory=Memory(tmp / "memory"), store=store, budget=Budget())
        seconds = time.time() - t0
        doc = store.load("ridgecrest2019")
    steps = [dict(hour=s.get("hour"), stage=s.get("stage"), sites=s.get("sites"), drift=s.get("drift"),
                  drift_reason=s.get("drift_reason"), aftershocks_real=s.get("aftershocks_real"),
                  synthetic=s.get("synthetic"),
                  quantum_agreed=(s.get("plan") or {}).get("quantum_agreed"),
                  p_opt_per_shot=(s.get("plan") or {}).get("p_opt_per_shot"))
             for s in doc["steps"]]
    return dict(hours=hours, step_hours=step, seconds=round(seconds, 1), plans_made=doc["plans_made"],
                moves_total=doc["moves_total"], final_sites=doc["current_sites"], steps=steps)


def main() -> None:
    t0 = time.time()
    out = dict(noise=noise_study(), replay=replay())
    out["runtime_seconds"] = round(time.time() - t0, 1)
    path = ROOT / "results" / "extras.json"
    path.write_text(json.dumps(out, indent=1))
    r = out["replay"]
    print(f"wrote {path} in {out['runtime_seconds']} s; replay: {r['plans_made']} plans, final {r['final_sites']}")


if __name__ == "__main__":
    main()
