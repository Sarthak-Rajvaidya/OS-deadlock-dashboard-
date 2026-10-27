from copy import deepcopy

import testbench
from simulation import engine
from simulation.scenarios import SIM_SCENARIOS, get_sim_scenario


def test_one_resource_scenario_reaches_real_deadlock():
    s = engine.new_state("one_resource")
    s, msg = engine.run_to_deadlock(s)
    assert s["available"] == [0] and s["allocation"] == [[1], [1]] and s["request"] == [[1], [1]]
    assert engine.live_detection(s)["deadlocked"] == [0, 1]
    s, _ = engine.detect(s)
    assert s["status"] == [engine.BLOCKED, engine.BLOCKED]


def test_recover_one_then_survivor_progresses():
    s, _ = engine.run_to_deadlock(engine.new_state("one_resource"))
    s, _ = engine.detect(s)
    s, msg = engine.recover(s, "one", 0)
    assert s["status"][0] == engine.TERMINATED and s["recovered"]
    # released instance was immediately granted to the waiting survivor
    assert s["status"][1] == engine.RUNNING and s["allocation"][1] == [2]
    assert s["available"] == [0]
    s, _, _ = engine.step(s)
    assert s["status"][1] == engine.COMPLETED and s["available"] == [2]


def test_recover_all():
    s, _ = engine.run_to_deadlock(engine.new_state("circular_three"))
    s, _ = engine.detect(s)
    s, _ = engine.recover(s, "all")
    assert s["status"] == [engine.TERMINATED] * 3 and s["available"] == [1, 1, 1]


def test_recovery_refused_without_deadlock():
    s = engine.new_state("one_resource")
    s2, msg = engine.recover(s, "all")
    assert s2 == s and "no deadlock" in msg.lower()


def test_waiting_scenario_never_deadlocks():
    s, msg = engine.run_to_deadlock(engine.new_state("waiting_only"))
    assert "without reaching" in msg
    assert not engine.live_detection(s)["has_deadlock"]
    assert s["status"][0] == engine.COMPLETED or s["status"][1] == engine.COMPLETED


def test_step_does_not_mutate_input_and_reset_is_exact():
    s0 = engine.new_state("one_resource")
    snap = deepcopy(s0)
    s1, _, _ = engine.step(s0)
    assert s0 == snap and s1 != s0
    assert engine.new_state("one_resource") == snap


def test_step_at_stall_is_safe_to_repeat():
    s, _ = engine.run_to_deadlock(engine.new_state("one_resource"))
    for _ in range(3):
        s, ok, _ = engine.step(s)
        assert not ok
    assert sum(1 for e in s["log"] if e["event"] == "No process can progress") == 1


def test_detect_before_anything_happens():
    s, msg = engine.detect(engine.new_state("circular_three"))
    assert "No deadlock" in msg


def test_all_scenarios_run_to_completion_without_error():
    for key in SIM_SCENARIOS:
        s = engine.new_state(key)
        for _ in range(50):
            s, ok, _ = engine.step(s)
            if not ok:
                break


def test_scenario_fixtures_not_mutated():
    snap = deepcopy(SIM_SCENARIOS)
    s = engine.new_state("one_resource")
    engine.run_to_deadlock(s)
    assert SIM_SCENARIOS == snap
    get_sim_scenario("one_resource")["events"].clear()
    assert SIM_SCENARIOS == snap


def test_testbench_all_pass_and_are_independent_of_each_other():
    first = testbench.run_all()
    second = testbench.run_all()
    assert len(first) >= 8
    assert all(r["passed"] for r in first), [r["id"] for r in first if not r["passed"]]
    assert [r["passed"] for r in first] == [r["passed"] for r in second]


def test_testbench_reports_failure_honestly(monkeypatch):
    def broken():
        return {"checks": [testbench._check("deliberate", 1, 2)], "output": "", "steps": [],
                "input": {}, "explanation": ""}
    r = testbench.run_test({"id": "X", "name": "x", "category": "c", "purpose": "p",
                            "expected": "e", "fn": broken})
    assert r["passed"] is False
    def boom():
        raise RuntimeError("boom")
    r = testbench.run_test({"id": "Y", "name": "y", "category": "c", "purpose": "p",
                            "expected": "e", "fn": boom})
    assert r["passed"] is False and "boom" in r["error"]
