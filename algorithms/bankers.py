
from copy import deepcopy


def validate_state(available, allocation, maximum):
    """Validate dimensions, non-negative values, and Allocation <= Maximum."""
    if not isinstance(available, list) or not isinstance(allocation, list):
        raise ValueError("Available and Allocation must be lists.")
    if not isinstance(maximum, list):
        raise ValueError("Maximum must be a list.")
    if not allocation or len(allocation) != len(maximum):
        raise ValueError("Allocation and Maximum must have the same nonzero process count.")

    resource_count = len(available)
    if resource_count == 0:
        raise ValueError("At least one resource type is required.")

    if any(not isinstance(row, list) or len(row) != resource_count
           for row in allocation + maximum):
        raise ValueError("All matrix rows must match the resource count.")

    matrices = [available] + allocation + maximum
    if any(type(x) is not int or x < 0 for row in matrices for x in row):
        raise ValueError("Resource values must be non-negative integers.")

    for i in range(len(allocation)):
        for j in range(resource_count):
            if allocation[i][j] > maximum[i][j]:
                raise ValueError(f"P{i}: Allocation cannot exceed Maximum.")

    return True


def calculate_need(allocation, maximum):
    """Need = Maximum - Allocation."""
    if len(allocation) != len(maximum):
        raise ValueError("Allocation and Maximum row counts differ.")
    if any(len(a) != len(m) for a, m in zip(allocation, maximum)):
        raise ValueError("Allocation and Maximum dimensions differ.")

    return [
        [maximum[i][j] - allocation[i][j]
         for j in range(len(maximum[i]))]
        for i in range(len(allocation))
    ]


def safety_algorithm(available, allocation, maximum):
    """Return whether the state is safe and a valid safe sequence, if one exists."""
    validate_state(available, allocation, maximum)
    need = calculate_need(allocation, maximum)

    work = available.copy()
    finish = [False] * len(allocation)
    sequence = []
    trace = []

    while len(sequence) < len(allocation):
        found = False

        for i in range(len(allocation)):
            if finish[i]:
                continue

            if all(need[i][j] <= work[j] for j in range(len(work))):
                before = work.copy()
                work = [work[j] + allocation[i][j]
                        for j in range(len(work))]
                finish[i] = True
                sequence.append(i)
                trace.append({
                    "process": f"P{i}",
                    "need": need[i].copy(),
                    "work_before": before,
                    "released_allocation": allocation[i].copy(),
                    "work_after": work.copy(),
                })
                found = True
                break

        if not found:
            break

    safe = all(finish)
    return {
        "safe": safe,
        "sequence": [f"P{i}" for i in sequence] if safe else [],
        "partial_sequence": [f"P{i}" for i in sequence],
        "need": need,
        "trace": trace,
        "work_remaining": work,
        "unfinished": [
            f"P{i}" for i, done in enumerate(finish) if not done
        ],
    }


def request_resources(process_id, request, available, allocation, maximum):
    """
    Check a request without mutating the original state.

    Status values:
      GRANTED
      INVALID
      WAIT
      DENIED_UNSAFE
    """
    validate_state(available, allocation, maximum)

    if type(process_id) is not int or not 0 <= process_id < len(allocation):
        return {"status": "INVALID", "reason": "Invalid process ID."}

    if not isinstance(request, list) or len(request) != len(available):
        return {
            "status": "INVALID",
            "reason": "Request must contain one value per resource type."
        }

    if any(type(x) is not int or x < 0 for x in request):
        return {
            "status": "INVALID",
            "reason": "Request values must be non-negative integers."
        }

    need = calculate_need(allocation, maximum)

    if any(request[j] > need[process_id][j]
           for j in range(len(available))):
        return {
            "status": "INVALID",
            "reason": "Request exceeds the process's remaining Need."
        }

    if any(request[j] > available[j] for j in range(len(available))):
        return {
            "status": "WAIT",
            "reason": "Request exceeds Available; allocation unchanged."
        }

    # Work only on copies. The caller's state is never modified here.
    new_available = [
        available[j] - request[j] for j in range(len(available))
    ]
    new_allocation = deepcopy(allocation)
    new_allocation[process_id] = [
        new_allocation[process_id][j] + request[j]
        for j in range(len(available))
    ]

    result = safety_algorithm(new_available, new_allocation, maximum)

    if not result["safe"]:
        return {
            "status": "DENIED_UNSAFE",
            "reason": "Granting this request would produce an unsafe state.",
            "safety_check": result,
        }

    return {
        "status": "GRANTED",
        "reason": "Request granted; the resulting state is safe.",
        "available": new_available,
        "allocation": new_allocation,
        "safety_check": result,
    }
