"""Deadlock detection (multi-instance) and recovery by termination.

Detection uses Available, Allocation and outstanding Request (NOT Maximum).
That is what separates it from the Banker's safety algorithm, which looks at
worst-case future Need.
"""
from copy import deepcopy
from typing import Dict, List, Optional

from .bankers import ValidationError, _is_int, _leq


def validate_detection_state(available, allocation, request) -> List[str]:
    errors: List[str] = []
    if not isinstance(available, (list, tuple)) or len(available) == 0:
        return ["Available must be a non-empty vector."]
    m = len(available)
    if not isinstance(allocation, (list, tuple)) or len(allocation) == 0:
        return ["Allocation must contain at least one process row."]
    n = len(allocation)
    if not isinstance(request, (list, tuple)) or len(request) != n:
        return [f"Request must have {n} rows (one per process)."]
    for j, v in enumerate(available):
        if not _is_int(v) or v < 0:
            errors.append(f"Available[R{j + 1}] must be an integer >= 0.")
    for name, mat in (("Allocation", allocation), ("Request", request)):
        for i, row in enumerate(mat):
            if not isinstance(row, (list, tuple)) or len(row) != m:
                errors.append(f"{name} row P{i + 1} must have {m} values.")
                continue
            for j, v in enumerate(row):
                if not _is_int(v) or v < 0:
                    errors.append(f"{name}[P{i + 1}][R{j + 1}] must be an integer >= 0.")
    return errors


def detect_deadlock(available, allocation, request) -> Dict:
    """Standard multi-instance deadlock detection.

    Work = Available. Finish[i] starts True for processes that hold nothing (they cannot
    be part of a deadlock). Repeatedly find an unfinished process whose outstanding
    Request <= Work, assume it finishes, and add its Allocation to Work. Processes still
    unfinished at the end are deadlocked.
    Returns deadlocked (0-based indices), steps, finish_order and an explanation.
    """
    errs = validate_detection_state(available, allocation, request)
    if errs:
        raise ValidationError(" ".join(errs))
    n = len(allocation)
    work = list(available)
    # Textbook: Finish[i] = True if Allocation[i] == 0 (holds nothing -> cannot be in a cycle)
    finish = [all(a == 0 for a in allocation[i]) for i in range(n)]
    order: List[int] = []
    steps: List[Dict] = [{
        "step": 0, "process": None, "work_before": list(work), "work_after": list(work),
        "finish": list(finish),
        "note": (f"Initial: Work = Available = {work}. Processes holding nothing are marked "
                 f"finished: {[f'P{i + 1}' for i in range(n) if finish[i]] or 'none'}.")}]
    progress = True
    while progress:
        progress = False
        for i in range(n):
            if not finish[i] and _leq(request[i], work):
                before = list(work)
                work = [w + a for w, a in zip(work, allocation[i])]
                finish[i] = True
                order.append(i)
                progress = True
                steps.append({
                    "step": len(steps), "process": i, "work_before": before,
                    "work_after": list(work), "finish": list(finish),
                    "note": (f"P{i + 1}: Request {list(request[i])} <= Work {before}, so it can "
                             f"get what it needs, finish, and release {list(allocation[i])}. "
                             f"Work becomes {work}.")})
    deadlocked = [i for i in range(n) if not finish[i]]
    if deadlocked:
        names = ", ".join(f"P{i + 1}" for i in deadlocked)
        explanation = (
            f"DEADLOCK DETECTED. {names} can never finish: each one's outstanding Request "
            f"exceeds Work ({work}) and the only way to free more resources is for another "
            "process in this set to finish first (circular dependency).")
    else:
        explanation = ("NO DEADLOCK. Every process can eventually obtain its requested "
                       "resources and finish.")
    return {"deadlocked": deadlocked, "has_deadlock": bool(deadlocked), "steps": steps,
            "finish_order": order, "final_work": work, "explanation": explanation}


def recover_by_terminating(available, allocation, request, victims: List[int],
                           terminated: Optional[List[int]] = None) -> Dict:
    """Terminate `victims` (0-based): release their Allocation, clear their Request.

    Works on copies; returns the new state plus a fresh detection run on it.
    `terminated` lets callers keep already-terminated processes out of consideration
    (their rows are already zero so this is only informational).
    """
    errs = validate_detection_state(available, allocation, request)
    if errs:
        raise ValidationError(" ".join(errs))
    n = len(allocation)
    victims = sorted(set(victims))
    bad = [v for v in victims if not _is_int(v) or not (0 <= v < n)]
    if bad or not victims:
        raise ValidationError("Choose at least one valid process to terminate.")
    new_avail = list(available)
    new_alloc = deepcopy(allocation)
    new_req = deepcopy(request)
    released = [0] * len(available)
    for v in victims:
        for j in range(len(available)):
            released[j] += new_alloc[v][j]
            new_avail[j] += new_alloc[v][j]
            new_alloc[v][j] = 0
            new_req[v][j] = 0
    after = detect_deadlock(new_avail, new_alloc, new_req)
    names = ", ".join(f"P{v + 1}" for v in victims)
    return {"victims": victims, "released": released, "new_available": new_avail,
            "new_allocation": new_alloc, "new_request": new_req, "detection_after": after,
            "recovered": not after["has_deadlock"],
            "message": (f"Terminated {names}; released {released} back to Available "
                        f"(now {new_avail}). "
                        + ("Deadlock resolved: all remaining processes can finish."
                           if not after["has_deadlock"]
                           else "Deadlock persists among remaining processes."))}


def find_wait_for_cycle(allocation, request) -> Optional[List[int]]:
    """Single-instance helper: wait-for graph cycle (P_i waits on P_j holding what i wants).

    Used only to explain a circular dependency; detect_deadlock stays authoritative.
    """
    n = len(allocation)
    m = len(allocation[0]) if n else 0
    edges = {i: [j for j in range(n) if j != i and any(request[i][r] > 0 and allocation[j][r] > 0
                                                          for r in range(m))] for i in range(n)}
    color = {i: 0 for i in range(n)}
    stack: List[int] = []

    def dfs(u):
        color[u] = 1
        stack.append(u)
        for v in edges[u]:
            if color[v] == 1:
                return stack[stack.index(v):] + [v]
            if color[v] == 0:
                c = dfs(v)
                if c:
                    return c
        stack.pop()
        color[u] = 2
        return None

    for i in range(n):
        if color[i] == 0:
            c = dfs(i)
            if c:
                return c
    return None
