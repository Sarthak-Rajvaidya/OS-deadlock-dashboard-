"""Predefined scenarios. Treat as read-only; always deepcopy before use."""
from copy import deepcopy

# Banker's Algorithm sample (classic 5-process, 3-resource example)
BANKERS_SAMPLE = {
    "name": "Sample: 5 processes, 3 resource types",
    "available": [3, 3, 2],
    "allocation": [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]],
    "maximum": [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]],
}

# Deadlock Lab scenarios. `events` are applied in order by the engine:
#   ("request", process_index, [units per resource])
SIM_SCENARIOS = {
    "one_resource": {
        "name": "Simple: 1 resource (2 instances), 2 processes",
        "description": ("R1 has two instances. P1 and P2 each get one, then each asks for "
                        "one more. Nothing is free, so both wait forever."),
        "resources": ["R1"], "total": [2], "processes": ["P1", "P2"],
        "events": [("request", 0, [1]), ("request", 1, [1]),
                   ("request", 0, [1]), ("request", 1, [1])],
        "can_deadlock": True,
    },
    "circular_three": {
        "name": "Circular wait: 3 resources (1 instance each), 3 processes",
        "description": ("P1 holds R1 and wants R2, P2 holds R2 and wants R3, P3 holds R3 "
                        "and wants R1: a cycle of waiting."),
        "resources": ["R1", "R2", "R3"], "total": [1, 1, 1],
        "processes": ["P1", "P2", "P3"],
        "events": [("request", 0, [1, 0, 0]), ("request", 1, [0, 1, 0]),
                   ("request", 2, [0, 0, 1]), ("request", 0, [0, 1, 0]),
                   ("request", 1, [0, 0, 1]), ("request", 2, [1, 0, 0])],
        "can_deadlock": True,
    },
    "waiting_only": {
        "name": "Waiting but NOT deadlocked: 1 resource (2 instances), 2 processes",
        "description": ("P1 must wait for a second R1, but P2 asks for nothing more and will "
                        "finish and release its instance. Waiting is not deadlock."),
        "resources": ["R1"], "total": [2], "processes": ["P1", "P2"],
        "events": [("request", 0, [1]), ("request", 1, [1]), ("request", 0, [1])],
        "can_deadlock": False,
    },
}


def get_sim_scenario(key):
    return deepcopy(SIM_SCENARIOS[key])


def get_bankers_sample():
    return deepcopy(BANKERS_SAMPLE)
