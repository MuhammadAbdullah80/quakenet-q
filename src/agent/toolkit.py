"""The science functions the agent calls, gathered in one object.

The agent reaches the science layer only through the fixed interfaces of docs/API.md
("Internal interfaces between the science layer and the agent"). Collecting them here lets the
tests pass small fakes with the same signatures, so the agent can be tested on its own.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Toolkit:
    load_event_data: Callable        # (event_id) -> EventData
    event_from_usgs: Callable        # (usgs_id, *, station_radius_km) -> EventData
    list_events: Callable            # () -> list[dict]
    planning_events: Callable        # (data, at_hours, *, min_real, seed) -> (events (E, 5), synthetic)
    select_sites: Callable           # (data, events, *, n) -> (candidates (n, 2), backups)
    make_instance: Callable          # (data, candidates, events, *, k, valid) -> Instance
    scorer: Callable                 # Scorer(inst, events (E, 3), *, mags, hearing)
    solver: Callable                 # run_xy_qaoa(h, k, reps, seed, restarts, shots, init, maxiter, cvar_alpha, diag)
    location_errors: Callable        # (inst, selected, events (E, 3), trials, seed) -> errors
    expert_rule: Callable            # (stations, candidates, centre, k) -> sites


def default_toolkit(solver: Callable | None = None) -> Toolkit:
    """The real science layer. Imported here, not at module load, so the API starts (and v1 keeps
    working) even while a science module is missing; the first agent call then fails cleanly."""
    from src import instances
    from src.baselines import expert_rule
    from src.geometry import Scorer
    from src.location import location_errors
    from src.qaoa_solver import run_xy_qaoa

    return Toolkit(load_event_data=instances.load_event_data, event_from_usgs=instances.event_from_usgs,
                   list_events=instances.list_events, planning_events=instances.planning_events,
                   select_sites=instances.select_sites, make_instance=instances.make_instance,
                   scorer=Scorer, solver=solver or run_xy_qaoa, location_errors=location_errors,
                   expert_rule=expert_rule)
