
import unittest
from copy import deepcopy

from algorithms.bankers import (
    calculate_need,
    safety_algorithm,
    request_resources,
)
from algorithms.deadlock import (
    detect_deadlock,
    recover_by_terminating,
)


class BankersAlgorithmTests(unittest.TestCase):

    def setUp(self):
        self.available = [3, 3, 2]

        self.allocation = [
            [0, 1, 0],
            [2, 0, 0],
            [3, 0, 2],
            [2, 1, 1],
            [0, 0, 2],
        ]

        self.maximum = [
            [7, 5, 3],
            [3, 2, 2],
            [9, 0, 2],
            [2, 2, 2],
            [4, 3, 3],
        ]

    def test_need_matrix(self):
        expected_need = [
            [7, 4, 3],
            [1, 2, 2],
            [6, 0, 0],
            [0, 1, 1],
            [4, 3, 1],
        ]

        self.assertEqual(
            calculate_need(self.allocation, self.maximum),
            expected_need,
        )

    def test_known_safe_sequence(self):
        result = safety_algorithm(
            self.available,
            self.allocation,
            self.maximum,
        )

        self.assertTrue(result["safe"])
        self.assertEqual(len(result["sequence"]), len(self.allocation))
        self.assertEqual(
            set(result["sequence"]),
            {"P0", "P1", "P2", "P3", "P4"},
        )

        # Independently verify each process can finish in the
        # exact order returned by the algorithm.
        need = calculate_need(self.allocation, self.maximum)
        work = self.available.copy()

        for process in result["sequence"]:
            self.assertRegex(process, r"^P[0-4]$")
            process_id = int(process[1:])

            self.assertTrue(
                all(
                    need[process_id][j] <= work[j]
                    for j in range(len(work))
                ),
                f"{process} cannot finish with Work={work}",
            )

            work = [
                work[j] + self.allocation[process_id][j]
                for j in range(len(work))
            ]

    def test_request_exceeds_available(self):
        before = deepcopy(
            (self.available, self.allocation, self.maximum)
        )

        result = request_resources(
            0,
            [0, 0, 3],
            self.available,
            self.allocation,
            self.maximum,
        )

        self.assertEqual(result["status"], "WAIT")
        self.assertEqual(
            (self.available, self.allocation, self.maximum),
            before,
        )

    def test_unsafe_request_is_rejected_atomically(self):
        before = deepcopy(
            (self.available, self.allocation, self.maximum)
        )

        result = request_resources(
            4,
            [3, 3, 0],
            self.available,
            self.allocation,
            self.maximum,
        )

        self.assertEqual(result["status"], "DENIED_UNSAFE")
        self.assertEqual(
            (self.available, self.allocation, self.maximum),
            before,
        )

    def test_request_exceeds_need(self):
        result = request_resources(
            1,
            [2, 0, 0],
            self.available,
            self.allocation,
            self.maximum,
        )

        self.assertEqual(result["status"], "INVALID")

    def test_negative_request(self):
        result = request_resources(
            0,
            [-1, 0, 0],
            self.available,
            self.allocation,
            self.maximum,
        )

        self.assertEqual(result["status"], "INVALID")

    def test_invalid_process(self):
        result = request_resources(
            10,
            [0, 0, 0],
            self.available,
            self.allocation,
            self.maximum,
        )

        self.assertEqual(result["status"], "INVALID")

    def test_valid_request_granted(self):
        before = deepcopy(
            (self.available, self.allocation, self.maximum)
        )

        result = request_resources(
            1,
            [1, 0, 2],
            self.available,
            self.allocation,
            self.maximum,
        )

        self.assertEqual(result["status"], "GRANTED")
        self.assertTrue(result["safety_check"]["safe"])

        # Request validation must not mutate caller-owned inputs.
        self.assertEqual(
            (self.available, self.allocation, self.maximum),
            before,
        )

        # Verify the returned allocation reflects the grant.
        self.assertEqual(result["available"], [2, 3, 0])
        self.assertEqual(result["allocation"][1], [3, 0, 2])

    def test_allocation_cannot_exceed_maximum(self):
        invalid_allocation = deepcopy(self.allocation)
        invalid_allocation[0][0] = 8

        with self.assertRaises(ValueError):
            safety_algorithm(
                self.available,
                invalid_allocation,
                self.maximum,
            )

    def test_deadlock_detection(self):
        result = detect_deadlock(
            [0],
            [[1], [1]],
            [[1], [1]],
        )

        self.assertTrue(result["deadlocked"])
        self.assertEqual(
            result["deadlocked_processes"],
            ["P0", "P1"],
        )

    def test_zero_allocation_process_is_not_deadlocked(self):
        result = detect_deadlock(
            [0],
            [[0], [1]],
            [[0], [1]],
        )

        self.assertTrue(result["deadlocked"])
        self.assertEqual(
            result["deadlocked_processes"],
            ["P1"],
        )

    def test_deadlock_recovery(self):
        result = recover_by_terminating(
            0,
            [0],
            [[1], [1]],
            [[1], [1]],
        )

        self.assertEqual(result["available"], [1])
        self.assertEqual(result["terminated"], "P0")
        self.assertEqual(result["allocation"][0], [0])
        self.assertEqual(result["request"][0], [0])

    def test_zero_request_is_valid_if_state_is_safe(self):
        result = request_resources(
            0,
            [0, 0, 0],
            self.available,
            self.allocation,
            self.maximum,
        )

        self.assertEqual(result["status"], "GRANTED")
        self.assertTrue(result["safety_check"]["safe"])

    def test_wrong_request_dimensions(self):
        result = request_resources(
            0,
            [1, 0],
            self.available,
            self.allocation,
            self.maximum,
        )

        self.assertEqual(result["status"], "INVALID")


if __name__ == "__main__":
    unittest.main()
