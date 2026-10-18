
def detect_deadlock(available, allocation, request):
    """
    Multi-instance deadlock detection.

    Request[i][j] is the current outstanding request of process i,
    not its maximum declared demand.
    """
    if not isinstance(available, list) or not available:
        raise ValueError("Available must contain at least one resource type.")

    if not isinstance(allocation, list) or not allocation:
        raise ValueError("Allocation must contain at least one process.")

    if not isinstance(request, list) or len(request) != len(allocation):
        raise ValueError("Request must have one row per process.")

    r = len(available)
    if any(not isinstance(row, list) or len(row) != r
           for row in allocation + request):
        raise ValueError("Matrix dimensions do not match Available.")

    values = [available] + allocation + request
    if any(type(x) is not int or x < 0 for row in values for x in row):
        raise ValueError("Resource values must be non-negative integers.")

    work = available.copy()

    # Processes holding no resources can finish without causing a deadlock.
    finish = [
        all(value == 0 for value in row)
        for row in allocation
    ]

    sequence = []
    trace = []

    while True:
        found = False

        for i in range(len(allocation)):
            if finish[i]:
                continue

            if all(request[i][j] <= work[j] for j in range(r)):
                before = work.copy()
                work = [
                    work[j] + allocation[i][j] for j in range(r)
                ]
                finish[i] = True
                sequence.append(f"P{i}")
                trace.append({
                    "process": f"P{i}",
                    "work_before": before,
                    "request": request[i].copy(),
                    "released_allocation": allocation[i].copy(),
                    "work_after": work.copy(),
                })
                found = True
                break

        if not found:
            break

    deadlocked = [
        f"P{i}" for i, done in enumerate(finish) if not done
    ]

    return {
        "deadlocked": bool(deadlocked),
        "deadlocked_processes": deadlocked,
        "completed_sequence": sequence,
        "trace": trace,
        "work_remaining": work,
    }


def recover_by_terminating(process_id, available, allocation, request):
    """Terminate one selected process and release its held resources."""
    if not allocation or not 0 <= process_id < len(allocation):
        raise ValueError("Invalid process ID.")

    result_available = available.copy()
    result_allocation = [row.copy() for row in allocation]
    result_request = [row.copy() for row in request]

    for j, held in enumerate(result_allocation[process_id]):
        result_available[j] += held

    result_allocation[process_id] = [0] * len(available)
    result_request[process_id] = [0] * len(available)

    return {
        "available": result_available,
        "allocation": result_allocation,
        "request": result_request,
        "terminated": f"P{process_id}",
    }
