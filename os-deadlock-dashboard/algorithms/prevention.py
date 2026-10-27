"""Deadlock prevention helpers: resource ordering (breaks circular wait) and
all-or-nothing allocation (breaks hold-and-wait)."""
from typing import Dict, List, Sequence


def validate_resource_order(order: Sequence[str], sequence: Sequence[str]) -> Dict:
    """Check that a process requests resources in strictly increasing `order`.

    `order` is the global ranking, e.g. ["R1", "R2", "R3"] (R1 has rank 1).
    `sequence` is the list of resources one process requests, in time order.
    """
    rank = {r: i for i, r in enumerate(order)}
    violations: List[str] = []
    unknown = [r for r in sequence if r not in rank]
    if unknown:
        return {"valid": False, "violations": [f"Unknown resource(s): {unknown}."],
                "message": f"Rejected: unknown resource(s) {unknown}."}
    for prev, cur in zip(sequence, sequence[1:]):
        if rank[cur] <= rank[prev]:
            violations.append(
                f"Requested {cur} (rank {rank[cur] + 1}) after {prev} (rank {rank[prev] + 1}); "
                "resources must be requested in increasing rank.")
    if violations:
        return {"valid": False, "violations": violations,
                "message": "Rejected: " + " ".join(violations)}
    return {"valid": True, "violations": [],
            "message": "Accepted: " + " -> ".join(sequence)
                       + " follows the global order, so a circular wait cannot form."}


def request_all_or_nothing(available: Sequence[int], need: Sequence[int]) -> Dict:
    """Hold-and-wait prevention: a process gets everything it needs at once or nothing."""
    if len(available) != len(need):
        raise ValueError("Available and need must have the same length.")
    if any(x < 0 for x in need) or any(x < 0 for x in available):
        raise ValueError("Values must be non-negative.")
    if all(n <= a for n, a in zip(need, available)):
        return {"granted": True, "held": list(need),
                "new_available": [a - n for a, n in zip(available, need)],
                "message": "Granted all requested resources at once; the process never holds "
                           "some while waiting for others."}
    return {"granted": False, "held": [0] * len(need), "new_available": list(available),
            "message": "Not all resources are free, so NOTHING is granted. The process waits "
                       "while holding no resources (hold-and-wait is impossible)."}
