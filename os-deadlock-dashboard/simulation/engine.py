"""Deterministic step-based state machine for the Deadlock Lab.

Every function takes a state dict and returns a NEW state (the input is never mutated),
so Streamlit reruns and Reset are always safe. Deadlock detection and recovery call the
real algorithms in algorithms/deadlock.py.
"""
from copy import deepcopy
from typing import Dict, List, Tuple

from algorithms.deadlock import detect_deadlock, recover_by_terminating
from .scenarios import get_sim_scenario

READY, RUNNING, WAITING, BLOCKED, COMPLETED, TERMINATED = (
    "Ready", "Running", "Waiting", "Blocked by deadlock", "Completed", "Terminated")
ACTIVE_WAIT = (WAITING, BLOCKED)


def fmt_vec(vec, resources) -> str:
    parts = [f"{v} x {r}" for v, r in zip(vec, resources) if v]
    return ", ".join(parts) if parts else "nothing"


def _log(state, event, why):
    state["log"].append({"n": len(state["log"]) + 1, "event": event, "why": why})


def new_state(key: str) -> Dict:
    sc = get_sim_scenario(key)
    n, m = len(sc["processes"]), len(sc["resources"])
    state = {
        "scenario_key": key, "name": sc["name"], "description": sc["description"],
        "resources": sc["resources"], "total": sc["total"], "processes": sc["processes"],
        "events": sc["events"], "can_deadlock": sc["can_deadlock"], "event_index": 0,
        "available": list(sc["total"]),
        "allocation": [[0] * m for _ in range(n)], "request": [[0] * m for _ in range(n)],
        "status": [READY] * n, "log": [], "detection": None, "recovered": False,
        "stall_logged": False,
    }
    _log(state, "Initial resource allocation",
         f"Resources: " + ", ".join(f"{r} has {t} instance(s)" for r, t in
                                   zip(sc["resources"], sc["total"]))
         + ". Nothing is allocated yet and every process is Ready.")
    return state


def live_detection(state: Dict) -> Dict:
    """Run the real detection algorithm on the current live state (read-only)."""
    return detect_deadlock(state["available"], state["allocation"], state["request"])


def _grant(state, p, vec):
    state["available"] = [a - v for a, v in zip(state["available"], vec)]
    state["allocation"][p] = [a + v for a, v in zip(state["allocation"][p], vec)]
    state["request"][p] = [0] * len(vec)
    state["status"][p] = RUNNING


def _grant_pending(state):
    """After resources are released, grant waiting requests that now fit (index order)."""
    changed = True
    while changed:
        changed = False
        for p, st in enumerate(state["status"]):
            req = state["request"][p]
            if st in ACTIVE_WAIT and any(req) and all(r <= a for r, a in zip(req, state["available"])):
                _grant(state, p, req)
                _log(state, f"{state['processes'][p]} is granted {fmt_vec(req, state['resources'])}",
                     "Resources were released, so its waiting request can now be satisfied. "
                     f"It returns to Running. Available is now {state['available']}.")
                changed = True


def next_hint(state: Dict) -> str:
    i = state["event_index"]
    if i < len(state["events"]):
        _, p, vec = state["events"][i]
        return f"{state['processes'][p]} will request {fmt_vec(vec, state['resources'])}."
    for p, st in enumerate(state["status"]):
        if st == RUNNING:
            return (f"{state['processes'][p]} will finish and release "
                    f"{fmt_vec(state['allocation'][p], state['resources'])}.")
    if any(s in ACTIVE_WAIT for s in state["status"]):
        if state["detection"] and state["detection"]["has_deadlock"]:
            return "Choose a recovery method and press Recover from Deadlock."
        return "Nobody can progress. Press Detect Deadlock to analyse the waiting processes."
    return "Simulation complete. Press Reset Scenario to run it again."


def step(state: Dict) -> Tuple[Dict, bool, str]:
    """Advance one event. Returns (new_state, progressed, message)."""
    s = deepcopy(state)
    names, res = s["processes"], s["resources"]
    i = s["event_index"]
    if i < len(s["events"]):
        _, p, vec = s["events"][i]
        s["event_index"] += 1
        pn = names[p]
        req_txt = fmt_vec(vec, res)
        if s["status"][p] in (COMPLETED, TERMINATED):
            _log(s, f"{pn} requests {req_txt} (skipped)",
                 f"{pn} is {s['status'][p]}, so it cannot make requests.")
        elif s["status"][p] in ACTIVE_WAIT:
            _log(s, f"{pn} requests {req_txt} (skipped)",
                 f"{pn} is already waiting for an earlier request.")
        elif all(v <= a for v, a in zip(vec, s["available"])):
            _grant(s, p, vec)
            _log(s, f"{pn} requests {req_txt}: granted",
                 f"Enough is Available, so {pn} receives it and keeps Running. "
                 f"Available is now {s['available']}.")
        else:
            s["request"][p] = list(vec)
            s["status"][p] = WAITING
            _log(s, f"{pn} requests {req_txt}: must wait",
                 f"Only {s['available']} is Available, which is not enough. {pn} keeps what "
                 f"it already holds ({fmt_vec(s['allocation'][p], res)}) and enters Waiting.")
        s["stall_logged"] = False
        return s, True, s["log"][-1]["event"]
    for p, st in enumerate(s["status"]):
        if st == RUNNING:
            rel = list(s["allocation"][p])
            s["available"] = [a + r for a, r in zip(s["available"], rel)]
            s["allocation"][p] = [0] * len(rel)
            s["status"][p] = COMPLETED
            _log(s, f"{names[p]} completes",
                 f"It has everything it needs, finishes, and releases {fmt_vec(rel, res)}. "
                 f"Available is now {s['available']}.")
            _grant_pending(s)
            s["stall_logged"] = False
            return s, True, s["log"][-1]["event"]
    if any(st in ACTIVE_WAIT for st in s["status"]):
        msg = "No process can progress: every remaining process is waiting."
        if not s["stall_logged"]:
            _log(s, "No process can progress",
                 "All remaining processes are waiting for resources and nobody is Running to "
                 "release any. Run Detect Deadlock to find out whether this is a true deadlock.")
            s["stall_logged"] = True
        return s, False, msg
    return s, False, "Simulation complete."


def run_to_deadlock(state: Dict) -> Tuple[Dict, str]:
    """Step until a real deadlock exists in the live state (checked with the real algorithm)."""
    s = deepcopy(state)
    for _ in range(200):
        if live_detection(s)["has_deadlock"]:
            return s, "Deadlock state reached. Press Detect Deadlock to analyse it."
        s, progressed, _ = step(s)
        if not progressed:
            break
    if live_detection(s)["has_deadlock"]:
        return s, "Deadlock state reached. Press Detect Deadlock to analyse it."
    return s, "This scenario ran to the end without reaching a deadlock."


def detect(state: Dict) -> Tuple[Dict, str]:
    s = deepcopy(state)
    det = live_detection(s)
    s["detection"] = det
    names = s["processes"]
    waiting = [names[p] for p, st in enumerate(s["status"]) if st in ACTIVE_WAIT]
    if det["has_deadlock"]:
        for p in det["deadlocked"]:
            s["status"][p] = BLOCKED
        dl = ", ".join(names[p] for p in det["deadlocked"])
        _log(s, f"Deadlock detected: {dl}",
             det["explanation"] + " These processes are now marked Blocked by deadlock.")
        return s, f"Deadlock detected: {dl}"
    if waiting:
        _log(s, "Detection: no deadlock",
             f"{', '.join(waiting)} are waiting, but each can eventually be satisfied because "
             "another process will finish and release resources. Waiting is not deadlock.")
    else:
        _log(s, "Detection: no deadlock", "No process is waiting, so nothing can be deadlocked.")
    return s, "No deadlock detected."


def recover(state: Dict, mode: str, victim: int = None) -> Tuple[Dict, str]:
    """mode: 'one' (terminate `victim`) or 'all' (terminate every deadlocked process)."""
    s = deepcopy(state)
    live = live_detection(s)
    if not live["has_deadlock"]:
        return s, "There is no deadlock to recover from."
    dead = live["deadlocked"]
    if mode == "all":
        victims = list(dead)
    elif mode == "one" and victim in dead:
        victims = [victim]
    else:
        return s, "Choose a deadlocked process to terminate."
    out = recover_by_terminating(s["available"], s["allocation"], s["request"], victims)
    s["available"], s["allocation"], s["request"] = (
        out["new_available"], out["new_allocation"], out["new_request"])
    for v in victims:
        s["status"][v] = TERMINATED
    vn = ", ".join(s["processes"][v] for v in victims)
    _log(s, f"Recovery: terminated {vn}",
         f"Their allocation ({fmt_vec(out['released'], s['resources'])}) was released. "
         f"Available is now {s['available']}.")
    # survivors that were marked Blocked go back to ordinary Waiting until re-analysed
    for p, st in enumerate(s["status"]):
        if st == BLOCKED:
            s["status"][p] = WAITING
    _grant_pending(s)
    after = live_detection(s)
    s["detection"] = after
    if after["has_deadlock"]:
        for p in after["deadlocked"]:
            s["status"][p] = BLOCKED
        _log(s, "Deadlock persists", after["explanation"])
        s["recovered"] = False
        return s, "Deadlock persists. Terminate another process."
    s["recovered"] = True
    left = [s["processes"][p] for p, st in enumerate(s["status"]) if st in (RUNNING, WAITING)]
    _log(s, "Deadlock recovered",
         "Re-running detection shows no deadlock. "
         + (f"Remaining processes ({', '.join(left)}) can now progress." if left
            else "No processes remain."))
    return s, "Deadlock recovered."
