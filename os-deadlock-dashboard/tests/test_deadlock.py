from copy import deepcopy

import pytest

from algorithms.bankers import ValidationError
from algorithms.deadlock import detect_deadlock, find_wait_for_cycle, recover_by_terminating
from algorithms.prevention import request_all_or_nothing, validate_resource_order


def test_genuine_deadlock_one_resource():
    r = detect_deadlock([0], [[1], [1]], [[1], [1]])
    assert r["deadlocked"] == [0, 1] and r["has_deadlock"]
    assert find_wait_for_cycle([[1], [1]], [[1], [1]])


def test_waiting_is_not_deadlock():
    r = detect_deadlock([0], [[1], [1]], [[1], [0]])
    assert r["deadlocked"] == [] and r["finish_order"] == [1, 0]


def test_available_resource_means_no_deadlock():
    assert not detect_deadlock([1], [[1], [1]], [[1], [1]])["has_deadlock"]


def test_circular_three_resources():
    alloc = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    req = [[0, 1, 0], [0, 0, 1], [1, 0, 0]]
    assert detect_deadlock([0, 0, 0], alloc, req)["deadlocked"] == [0, 1, 2]


def test_partial_deadlock_leaves_free_process():
    alloc = [[1], [1], [0]]
    req = [[1], [1], [0]]
    assert detect_deadlock([0], alloc, req)["deadlocked"] == [0, 1]


def test_recovery_one_victim():
    before = ([0], [[1], [1]], [[1], [1]])
    snap = deepcopy(before)
    r = recover_by_terminating(*before, [0])
    assert r["new_allocation"] == [[0], [1]] and r["new_available"] == [1]
    assert r["recovered"] and r["detection_after"]["finish_order"] == [1]
    assert before == snap


def test_recovery_all_victims():
    r = recover_by_terminating([0], [[1], [1]], [[1], [1]], [0, 1])
    assert r["new_available"] == [2] and r["recovered"]


def test_recovery_can_fail_when_still_deadlocked():
    alloc = [[1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 0]]
    req = [[0, 1, 0], [0, 0, 1], [1, 0, 0], [0, 0, 0]]
    r = recover_by_terminating([0, 0, 0], alloc, req, [3])
    assert not r["recovered"]


def test_invalid_inputs_raise():
    with pytest.raises(ValidationError):
        detect_deadlock([0], [[1], [1]], [[1]])
    with pytest.raises(ValidationError):
        detect_deadlock([-1], [[1]], [[1]])
    with pytest.raises(ValidationError):
        recover_by_terminating([0], [[1], [1]], [[1], [1]], [])
    with pytest.raises(ValidationError):
        recover_by_terminating([0], [[1], [1]], [[1], [1]], [5])


def test_resource_ordering():
    order = ["R1", "R2", "R3"]
    assert validate_resource_order(order, ["R1", "R3"])["valid"]
    assert not validate_resource_order(order, ["R2", "R1"])["valid"]
    assert not validate_resource_order(order, ["R1", "R1"])["valid"]
    assert not validate_resource_order(order, ["R9"])["valid"]
    assert validate_resource_order(order, [])["valid"]


def test_all_or_nothing():
    assert request_all_or_nothing([1, 1], [1, 1])["granted"]
    r = request_all_or_nothing([1, 0], [1, 1])
    assert not r["granted"] and r["held"] == [0, 0]
    with pytest.raises(ValueError):
        request_all_or_nothing([1], [1, 1])
