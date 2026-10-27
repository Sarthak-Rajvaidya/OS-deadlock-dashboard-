"""In-dashboard Test Bench. Pure Python (no Streamlit).

Each test is built from CHECKS. A check compares an expected value (written here) with an
actual value produced by calling the real project functions. PASS = every check matched.
Nothing is hardcoded as passing.
"""
from copy import deepcopy
from typing import Callable, Dict, List

from algorithms.bankers import (ValidationError, calculate_need, request_resources,
                                safety_algorithm, validate_state)
from algorithms.deadlock import (detect_deadlock, find_wait_for_cycle,
                                 recover_by_terminating)
from algorithms.prevention import request_all_or_nothing, validate_resource_order
from simulation.scenarios import get_bankers_sample

DEADLOCK_1R = {"available": [0], "allocation": [[1], [1]], "request": [[1], [1]],
               "resources": ["R1"], "total": [2]}
NO_DEADLOCK_1R = {"available": [0], "allocation": [[1], [1]], "request": [[1], [0]],
                  "resources": ["R1"], "total": [2]}
CIRCULAR_3 = {"available": [0, 0, 0], "allocation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
              "request": [[0, 1, 0], [0, 0, 1], [1, 0, 0]],
              "resources": ["R1", "R2", "R3"], "total": [1, 1, 1]}


def _check(label, expected, actual):
    return {"check": label, "expected": expected, "actual": actual,
            "passed": expected == actual}


def _seq(s):
    return " -> ".join(f"P{i + 1}" for i in s) or "none"


def tc1():
    sa = get_bankers_sample()
    r = safety_algorithm(sa["available"], sa["allocation"], sa["maximum"])
    # independent validity check of whatever sequence the algorithm returned
    work, ok = list(sa["available"]), True
    need = calculate_need(sa["maximum"], sa["allocation"])
    for i in r["safe_sequence"]:
        if all(n <= w for n, w in zip(need[i], work)):
            work = [w + a for w, a in zip(work, sa["allocation"][i])]
        else:
            ok = False
    checks = [
        _check("State is safe", True, r["safe"]),
        _check("Sequence includes every process once", [0, 1, 2, 3, 4], sorted(r["safe_sequence"])),
        _check("Returned sequence replays validly (Need <= Work at each step)", True, ok),
    ]
    return {"checks": checks, "output": r["explanation"], "steps": r["steps"],
            "input": sa, "explanation": "The safety algorithm found a safe sequence and each step was re-verified independently."}


def tc2():
    st = {"available": [1], "allocation": [[2], [2]], "maximum": [[4], [4]]}
    r = safety_algorithm(**st)
    det = detect_deadlock(st["available"], st["allocation"], [[0], [0]])
    checks = [
        _check("State is unsafe", False, r["safe"]),
        _check("No safe sequence is invented", [], r["safe_sequence"]),
        _check("Both processes remain unfinished", [0, 1], r["unfinished"]),
        _check("Yet detection finds NO current deadlock (nobody is waiting)", False, det["has_deadlock"]),
    ]
    return {"checks": checks, "output": r["explanation"], "steps": r["steps"], "input": st,
            "explanation": "Unsafe means a deadlock is possible in the future; it is not a deadlock now because no process has an outstanding request."}


def tc3():
    sa = get_bankers_sample()
    before = deepcopy(sa)
    r = request_resources(sa["available"], sa["allocation"], sa["maximum"], 1, [1, 0, 2])
    checks = [
        _check("Status", "granted", r["status"]),
        _check("Safety check on provisional state succeeded", True, bool(r["safety"] and r["safety"]["safe"])),
        _check("P2 allocation becomes", [3, 0, 2], r["new_allocation"][1]),
        _check("Available becomes", [2, 3, 0], r["new_available"]),
        _check("Original state untouched", before, sa),
    ]
    return {"checks": checks, "output": r["message"], "steps": r["safety"]["steps"] if r["safety"] else [],
            "input": {**sa, "request": "P2 requests [1, 0, 2]"}, "explanation": "A valid request was applied provisionally, found safe, and granted."}


def tc4():
    sa = get_bankers_sample()
    before = deepcopy(sa)
    a = request_resources(sa["available"], sa["allocation"], sa["maximum"], 0, [8, 0, 0])
    b = request_resources(sa["available"], sa["allocation"], sa["maximum"], 2, [4, 0, 0])
    c = request_resources(sa["available"], sa["allocation"], sa["maximum"], 4, [3, 3, 0])
    checks = [
        _check("P1 requests [8,0,0] (> Need [7,4,3])", "exceeds_need", a["status"]),
        _check("P3 requests [4,0,0] (<= Need, > Available [3,3,2])", "waiting", b["status"]),
        _check("P5 requests [3,3,0] (<= Need and Available, but unsafe)", "denied_unsafe", c["status"]),
        _check("Unsafe request was not granted", False, c["granted"]),
        _check("Original state unchanged after all denials", before, sa),
    ]
    return {"checks": checks, "output": "\n".join([a["message"], b["message"], c["message"]]),
            "steps": c["safety"]["steps"] if c["safety"] else [], "input": {**sa, "requests": "see checks"},
            "explanation": "Invalid (exceeds Need), waiting (not enough Available) and unsafe denial are three different outcomes, and none corrupts the stored state."}


def tc5():
    d = NO_DEADLOCK_1R
    r = detect_deadlock(d["available"], d["allocation"], d["request"])
    checks = [_check("Deadlocked processes", [], r["deadlocked"]),
              _check("Finish order (P2 releases, then P1 proceeds)", [1, 0], r["finish_order"])]
    return {"checks": checks, "output": r["explanation"], "steps": r["steps"], "input": d,
            "explanation": "P1 waits, but P2 needs nothing more and will release its instance, so the wait ends."}


def tc6():
    d = DEADLOCK_1R
    r = detect_deadlock(d["available"], d["allocation"], d["request"])
    cyc = find_wait_for_cycle(d["allocation"], d["request"])
    checks = [_check("Deadlocked processes", [0, 1], r["deadlocked"]),
              _check("Circular wait exists (P1 -> P2 -> P1)", True, bool(cyc))]
    return {"checks": checks, "output": r["explanation"], "steps": r["steps"], "input": d,
            "explanation": "Each process holds one R1 and needs another; the only free instance would come from the other process."}


def tc7():
    d = DEADLOCK_1R
    before = deepcopy(d)
    r = recover_by_terminating(d["available"], d["allocation"], d["request"], [0])
    checks = [
        _check("Terminated process allocation cleared", [0], r["new_allocation"][0]),
        _check("Resource released to Available", [1], r["new_available"]),
        _check("Re-running detection: deadlocked set", [], r["detection_after"]["deadlocked"]),
        _check("Recovered", True, r["recovered"]),
        _check("Original deadlocked state untouched", before, d),
    ]
    return {"checks": checks, "output": r["message"], "steps": r["detection_after"]["steps"],
            "input": d, "explanation": "Termination released P1's instance; detection re-run on the new state shows P2 can finish."}


def tc8():
    order = ["R1", "R2", "R3"]
    good = validate_resource_order(order, ["R1", "R2", "R3"])
    bad = validate_resource_order(order, ["R2", "R1"])
    hw_ok = request_all_or_nothing([1, 1], [1, 1])
    hw_no = request_all_or_nothing([1, 0], [1, 1])
    checks = [
        _check("Ordered sequence R1,R2,R3 accepted", True, good["valid"]),
        _check("Sequence R2,R1 rejected", False, bad["valid"]),
        _check("All-or-nothing grants when everything is free", True, hw_ok["granted"]),
        _check("All-or-nothing grants NOTHING when one resource is missing", [0, 0], hw_no["held"]),
    ]
    return {"checks": checks, "output": bad["message"] + "\n" + hw_no["message"], "steps": [],
            "input": {"order": order, "valid": ["R1", "R2", "R3"], "invalid": ["R2", "R1"]},
            "explanation": "Ordering breaks circular wait; all-or-nothing allocation breaks hold-and-wait."}


def tc9():
    good = get_bankers_sample()
    bad_cases = {
        "negative Available": ([-1, 0, 0], good["allocation"], good["maximum"]),
        "inconsistent row length": ([3, 3, 2], [[0, 1], [2, 0, 0]], [[7, 5, 3], [3, 2, 2]]),
        "row-count mismatch": ([3, 3, 2], good["allocation"][:3], good["maximum"]),
        "Allocation > Maximum": ([3, 3, 2], [[9, 0, 0]], [[1, 1, 1]]),
        "empty input": ([], [], []),
    }
    checks = [_check("Valid sample has no errors", [], validate_state(good["available"], good["allocation"], good["maximum"]))]
    for label, (a, al, mx) in bad_cases.items():
        checks.append(_check(f"{label} rejected", True, bool(validate_state(a, al, mx))))
    try:
        safety_algorithm(*bad_cases["Allocation > Maximum"])
        blocked = False
    except ValidationError:
        blocked = True
    checks.append(_check("Malformed state cannot reach the safety algorithm", True, blocked))
    return {"checks": checks, "output": "; ".join(validate_state(*bad_cases["Allocation > Maximum"])),
            "steps": [], "input": {k: v for k, v in bad_cases.items()},
            "explanation": "Validation runs before every algorithm and raises a clear error instead of crashing."}


def tc10():
    d = CIRCULAR_3
    r = detect_deadlock(d["available"], d["allocation"], d["request"])
    cyc = find_wait_for_cycle(d["allocation"], d["request"])
    one = recover_by_terminating(d["available"], d["allocation"], d["request"], [0])
    allv = recover_by_terminating(d["available"], d["allocation"], d["request"], [0, 1, 2])
    checks = [_check("All three processes deadlocked", [0, 1, 2], r["deadlocked"]),
              _check("Wait-for cycle found", True, bool(cyc)),
              _check("Terminating P1 alone resolves it", True, one["recovered"]),
              _check("Terminating all resolves it", True, allv["recovered"]),
              _check("Terminate-all releases every resource", [1, 1, 1], allv["new_available"])]
    return {"checks": checks, "output": r["explanation"], "steps": r["steps"], "input": d,
            "explanation": "A multi-resource circular wait is detected; both recovery methods are verified by re-running detection."}


TESTS: List[Dict] = [
    {"id": "TC1", "name": "Safe state and safe sequence", "category": "Avoidance (Banker's)",
     "purpose": "Sample 5x3 state must be safe with a valid sequence.", "fn": tc1,
     "expected": "SAFE with a valid sequence covering all processes"},
    {"id": "TC2", "name": "Unsafe state", "category": "Avoidance (Banker's)",
     "purpose": "Unsafe state: no sequence, and not a current deadlock.", "fn": tc2,
     "expected": "UNSAFE, empty sequence, no current deadlock"},
    {"id": "TC3", "name": "Request granted", "category": "Avoidance (Banker's)",
     "purpose": "Valid request keeping the system safe is granted.", "fn": tc3,
     "expected": "granted; Allocation P2=[3,0,2]; Available=[2,3,0]"},
    {"id": "TC4", "name": "Request invalid / waiting / denied", "category": "Avoidance (Banker's)",
     "purpose": "Three failure modes are distinguished; state not corrupted.", "fn": tc4,
     "expected": "exceeds_need, waiting, denied_unsafe"},
    {"id": "TC5", "name": "Detection: no deadlock", "category": "Detection",
     "purpose": "Waiting process that will be unblocked is not deadlocked.", "fn": tc5,
     "expected": "No deadlocked processes"},
    {"id": "TC6", "name": "Detection: genuine deadlock", "category": "Detection",
     "purpose": "1 resource, 2 instances, 2 processes each holding 1 and wanting 1.", "fn": tc6,
     "expected": "P1 and P2 deadlocked"},
    {"id": "TC7", "name": "Recovery by termination", "category": "Recovery",
     "purpose": "Terminate P1 in the TC6 deadlock and verify the result.", "fn": tc7,
     "expected": "Resource released, detection re-run clean"},
    {"id": "TC8", "name": "Prevention: ordering and hold-and-wait", "category": "Prevention",
     "purpose": "Out-of-order requests rejected; all-or-nothing grants nothing when short.", "fn": tc8,
     "expected": "Ordered accepted, unordered rejected"},
    {"id": "TC9", "name": "Boundary validation", "category": "Validation",
     "purpose": "Malformed inputs are rejected before reaching algorithms.", "fn": tc9,
     "expected": "All malformed inputs rejected"},
    {"id": "TC10", "name": "Multi-resource circular wait + recovery", "category": "Detection + Recovery",
     "purpose": "3 processes, 3 resources, circular wait; both recovery modes.", "fn": tc10,
     "expected": "All three deadlocked; both recoveries succeed"},
]


def run_test(test: Dict) -> Dict:
    """Execute one test. Any unexpected exception is reported as a FAIL, never a crash."""
    try:
        out = test["fn"]()
        passed = all(c["passed"] for c in out["checks"])
        error = None
    except Exception as exc:  # noqa: BLE001 - surface any failure in the UI
        out = {"checks": [], "output": "", "steps": [], "input": {}, "explanation": ""}
        passed, error = False, f"{type(exc).__name__}: {exc}"
    return {"id": test["id"], "name": test["name"], "category": test["category"],
            "purpose": test["purpose"], "expected": test["expected"], "passed": passed,
            "error": error, **out}


def run_all() -> List[Dict]:
    return [run_test(t) for t in TESTS]
