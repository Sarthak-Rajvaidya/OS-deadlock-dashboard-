from copy import deepcopy

import pytest

from algorithms.bankers import (ValidationError, calculate_need, request_resources,
                                safety_algorithm, validate_state)
from simulation.scenarios import get_bankers_sample

S = get_bankers_sample()


def test_need_matrix_sample():
    assert calculate_need(S["maximum"], S["allocation"]) == [
        [7, 4, 3], [1, 2, 2], [6, 0, 0], [0, 1, 1], [4, 3, 1]]


def test_sample_is_safe_and_sequence_replays():
    r = safety_algorithm(S["available"], S["allocation"], S["maximum"])
    assert r["safe"] and sorted(r["safe_sequence"]) == [0, 1, 2, 3, 4]
    work, need = list(S["available"]), r["need"]
    for i in r["safe_sequence"]:
        assert all(n <= w for n, w in zip(need[i], work))
        work = [w + a for w, a in zip(work, S["allocation"][i])]


def test_unsafe_state():
    r = safety_algorithm([1], [[2], [2]], [[4], [4]])
    assert not r["safe"] and r["safe_sequence"] == [] and r["unfinished"] == [0, 1]


def test_zero_need_state_is_safe():
    # Need = Max - Alloc = 0 for every process: all can finish immediately.
    mx = [[2, 1], [1, 3]]
    r = safety_algorithm([0, 0], mx, mx)
    assert r["need"] == [[0, 0], [0, 0]]
    assert r["safe"] and r["safe_sequence"] == [0, 1]


def test_one_resource_type_and_multiple_types():
    assert safety_algorithm([1], [[1], [1]], [[2], [2]])["safe"]
    assert safety_algorithm(S["available"], S["allocation"], S["maximum"])["safe"]


def test_inputs_not_mutated():
    before = deepcopy(S)
    safety_algorithm(S["available"], S["allocation"], S["maximum"])
    request_resources(S["available"], S["allocation"], S["maximum"], 1, [1, 0, 2])
    assert S == before


def test_request_granted():
    r = request_resources(S["available"], S["allocation"], S["maximum"], 1, [1, 0, 2])
    assert r["status"] == "granted" and r["new_available"] == [2, 3, 0]
    assert r["new_allocation"][1] == [3, 0, 2]


def test_request_exceeds_need():
    r = request_resources(S["available"], S["allocation"], S["maximum"], 0, [8, 0, 0])
    assert r["status"] == "exceeds_need" and not r["granted"]


def test_request_exceeds_available_is_waiting_not_unsafe():
    r = request_resources(S["available"], S["allocation"], S["maximum"], 2, [4, 0, 0])
    assert r["status"] == "waiting"


def test_request_unsafe_denied_and_rolled_back():
    before = deepcopy(S)
    r = request_resources(S["available"], S["allocation"], S["maximum"], 4, [3, 3, 0])
    assert r["status"] == "denied_unsafe" and not r["granted"]
    assert S == before and r["new_available"] == S["available"]


@pytest.mark.parametrize("proc,vec", [(0, [-1, 0, 0]), (9, [0, 0, 0]), (0, [1, 1]), (-1, [0, 0, 0])])
def test_invalid_requests(proc, vec):
    assert request_resources(S["available"], S["allocation"], S["maximum"], proc, vec)["status"] == "invalid"


def test_validation_errors():
    assert validate_state(S["available"], S["allocation"], S["maximum"]) == []
    assert validate_state([-1], [[0]], [[1]])
    assert validate_state([1, 1], [[0]], [[1, 1]])
    assert validate_state([1], [[0], [0]], [[1]])
    assert validate_state([1], [[3]], [[1]])
    assert validate_state([], [], [])
    assert validate_state([1], [[1.5]], [[2]])


def test_malformed_state_raises_validation_error():
    with pytest.raises(ValidationError):
        safety_algorithm([1], [[3]], [[1]])
