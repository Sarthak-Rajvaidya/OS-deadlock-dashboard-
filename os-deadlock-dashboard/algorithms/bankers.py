"""Banker's Algorithm: validation, Need, safety algorithm, resource-request.

All functions are pure: they never mutate their inputs.
Matrices are lists of lists of ints; vectors are lists of ints.
Any number of processes (n >= 1) and resource types (m >= 1) is supported.
"""
from copy import deepcopy
from typing import Dict, List, Optional


class ValidationError(ValueError):
    """Raised when a state is malformed. The message explains how to fix it."""


def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def validate_state(available, allocation, maximum) -> List[str]:
    """Return a list of human-readable problems (empty list = valid state)."""
    errors: List[str] = []
    if not isinstance(available, (list, tuple)) or len(available) == 0:
        return ["Available must be a non-empty vector (at least one resource type)."]
    m = len(available)
    if not isinstance(allocation, (list, tuple)) or len(allocation) == 0:
        return ["Allocation must contain at least one process row."]
    if not isinstance(maximum, (list, tuple)) or len(maximum) == 0:
        return ["Maximum must contain at least one process row."]
    n = len(allocation)
    if len(maximum) != n:
        errors.append(
            f"Allocation has {n} rows but Maximum has {len(maximum)}; both need one row per process.")
    for name, mat in (("Allocation", allocation), ("Maximum", maximum)):
        for i, row in enumerate(mat):
            if not isinstance(row, (list, tuple)) or len(row) != m:
                errors.append(
                    f"{name} row P{i + 1} must have {m} values (one per resource type).")
    if errors:
        return errors
    for j, v in enumerate(available):
        if not _is_int(v):
            errors.append(f"Available[R{j + 1}] must be an integer.")
        elif v < 0:
            errors.append(f"Available[R{j + 1}] = {v} is negative; use 0 or more.")
    for name, mat in (("Allocation", allocation), ("Maximum", maximum)):
        for i, row in enumerate(mat):
            for j, v in enumerate(row):
                if not _is_int(v):
                    errors.append(f"{name}[P{i + 1}][R{j + 1}] must be an integer.")
                elif v < 0:
                    errors.append(f"{name}[P{i + 1}][R{j + 1}] = {v} is negative; use 0 or more.")
    if errors:
        return errors
    for i in range(n):
        for j in range(m):
            if allocation[i][j] > maximum[i][j]:
                errors.append(
                    f"Allocation[P{i + 1}][R{j + 1}] = {allocation[i][j]} exceeds Maximum "
                    f"= {maximum[i][j]}. Lower the allocation or raise the maximum.")
    return errors


def require_valid(available, allocation, maximum) -> None:
    errs = validate_state(available, allocation, maximum)
    if errs:
        raise ValidationError(" ".join(errs))


def calculate_need(maximum, allocation) -> List[List[int]]:
    """Need[i][j] = Maximum[i][j] - Allocation[i][j]."""
    return [[mx - al for mx, al in zip(mrow, arow)] for mrow, arow in zip(maximum, allocation)]


def _leq(a, b) -> bool:
    return all(x <= y for x, y in zip(a, b))


def safety_algorithm(available, allocation, maximum) -> Dict:
    """Run the Banker's safety algorithm and record every step.

    Returns dict with: safe (bool), safe_sequence (list of 0-based indices, empty if
    unsafe), need, steps (list of dicts), unfinished (list), explanation (str).
    Scans processes in index order each pass and picks the first unfinished process whose
    Need <= Work, giving a deterministic result.
    """
    require_valid(available, allocation, maximum)
    n, m = len(allocation), len(available)
    need = calculate_need(maximum, allocation)
    work = list(available)
    finish = [False] * n
    sequence: List[int] = []
    steps: List[Dict] = [{
        "step": 0, "process": None, "can_run": None, "work_before": list(work),
        "work_after": list(work), "finish": list(finish),
        "note": f"Initial: Work = Available = {work}; Finish = all False."}]
    while True:
        picked = None
        for i in range(n):
            if not finish[i] and _leq(need[i], work):
                picked = i
                break
        if picked is None:
            break
        before = list(work)
        work = [w + a for w, a in zip(work, allocation[picked])]
        finish[picked] = True
        sequence.append(picked)
        steps.append({
            "step": len(steps), "process": picked, "can_run": True,
            "work_before": before, "work_after": list(work), "finish": list(finish),
            "note": (f"P{picked + 1}: Need {need[picked]} <= Work {before}, so it can finish. "
                     f"It releases Allocation {list(allocation[picked])}; "
                     f"Work becomes {work}.")})
    unfinished = [i for i in range(n) if not finish[i]]
    safe = not unfinished
    if safe:
        seq_txt = " -> ".join(f"P{i + 1}" for i in sequence)
        explanation = (f"SAFE. Every process can finish in some order. Safe sequence: {seq_txt}.")
    else:
        blocked = ", ".join(f"P{i + 1}(Need {need[i]})" for i in unfinished)
        explanation = (
            f"UNSAFE. With Work = {work}, no remaining process has Need <= Work: {blocked}. "
            "No safe sequence exists. Unsafe does NOT mean deadlocked yet; it means deadlock "
            "is possible if processes request their maximum.")
    return {"safe": safe, "safe_sequence": sequence, "need": need, "steps": steps,
            "unfinished": unfinished, "final_work": work, "explanation": explanation}


def request_resources(available, allocation, maximum, process: int, request) -> Dict:
    """Banker's resource-request algorithm. Never mutates inputs.

    status is one of:
      'invalid'  - malformed request (negative / wrong length / bad process index)
      'exceeds_need' - request > Need (process broke its declared maximum)
      'waiting'  - request > Available (valid but must wait)
      'denied_unsafe' - granting would leave the system unsafe (rolled back)
      'granted'  - granted; new_available / new_allocation hold the new state
    """
    require_valid(available, allocation, maximum)
    n, m = len(allocation), len(available)
    result = {"status": None, "granted": False, "message": "", "safety": None,
              "new_available": list(available), "new_allocation": deepcopy(allocation)}
    if not _is_int(process) or not (0 <= process < n):
        result.update(status="invalid", message=f"Process index {process} is out of range 1..{n}.")
        return result
    if not isinstance(request, (list, tuple)) or len(request) != m or not all(_is_int(x) for x in request):
        result.update(status="invalid", message=f"Request must be {m} integers (one per resource type).")
        return result
    if any(x < 0 for x in request):
        result.update(status="invalid", message="Request contains a negative value; use 0 or more.")
        return result
    need = calculate_need(maximum, allocation)
    p = f"P{process + 1}"
    if not _leq(request, need[process]):
        result.update(status="exceeds_need", message=(
            f"ERROR: {p} requested {list(request)} but its remaining Need is {need[process]}. "
            "A process may not request more than it declared as its maximum."))
        return result
    if not _leq(request, available):
        result.update(status="waiting", message=(
            f"WAIT: {p} requested {list(request)} but only {list(available)} is Available. "
            "The request is valid, so the process waits for resources to be released. "
            "This is waiting, not an unsafe state."))
        return result
    # provisional allocation on COPIES (original untouched = automatic rollback)
    tmp_avail = [a - r for a, r in zip(available, request)]
    tmp_alloc = deepcopy(allocation)
    tmp_alloc[process] = [a + r for a, r in zip(tmp_alloc[process], request)]
    safety = safety_algorithm(tmp_avail, tmp_alloc, maximum)
    result["safety"] = safety
    if safety["safe"]:
        seq = " -> ".join(f"P{i + 1}" for i in safety["safe_sequence"])
        result.update(status="granted", granted=True, new_available=tmp_avail,
                      new_allocation=tmp_alloc,
                      message=f"GRANTED: the provisional state is safe (sequence {seq}).")
    else:
        result.update(status="denied_unsafe", message=(
            f"DENIED: granting {list(request)} to {p} would leave the system UNSAFE, so the "
            "request is rolled back and the process waits."))
    return result
