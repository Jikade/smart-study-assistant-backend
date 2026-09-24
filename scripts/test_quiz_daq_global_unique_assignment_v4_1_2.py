from __future__ import annotations

from types import SimpleNamespace
import inspect

from app.services import quiz_service


def check(
    label: str,
    condition: bool,
) -> None:
    if not condition:
        raise AssertionError(
            label
        )

    print(
        f"[PASS] {label}"
    )


def candidate(
    answer_text: str,
    *,
    priority_rank: int = 0,
):
    # priority shape mirrors DAQ runtime:
    # viability, reserved, current, structured, pool, norm
    priority = (
        0,
        0,
        priority_rank,
        0,
        0,
        answer_text,
    )

    row = {
        "answer_id": (
            "A_" + answer_text
        ),
        "answer_text": (
            answer_text
        ),
        "evidence_id": "E0",
        "evidence_text": (
            f"Evidence for {answer_text}"
        ),
    }

    return (
        priority,
        row,
        [],
        SimpleNamespace(
            domain="HISTORY",
            knowledge_type="DATE",
        ),
    )


def main() -> None:
    print(
        "=" * 116
    )
    print(
        "DAQ-V1.12 GLOBAL UNIQUE ASSIGNMENT REGRESSION"
    )
    print(
        "=" * 116
    )

    # Reproduce the live failure shape:
    #
    # slot 0 and 1 are flexible but greedily prefer the same
    # scarce values required by slot 3.
    #
    # A valid global solution exists:
    #   slot0 -> 1975
    #   slot1 -> 2/9/1945 (or 1986)
    #   slot2 -> 1954
    #   slot3 -> 1945
    #   slot4 -> 1986
    candidate_map = {
        "0": [
            candidate(
                "1945",
                priority_rank=0,
            ),
            candidate(
                "1975",
                priority_rank=1,
            ),
            candidate(
                "1986",
                priority_rank=2,
            ),
        ],
        "1": [
            candidate(
                "2/9/1945",
                priority_rank=0,
            ),
            candidate(
                "1986",
                priority_rank=1,
            ),
            candidate(
                "1954",
                priority_rank=2,
            ),
        ],
        "2": [
            candidate(
                "1954",
                priority_rank=0,
            ),
            candidate(
                "1975",
                priority_rank=1,
            ),
            candidate(
                "1986",
                priority_rank=2,
            ),
        ],
        "3": [
            candidate(
                "1945",
                priority_rank=0,
            ),
            candidate(
                "2/9/1945",
                priority_rank=1,
            ),
        ],
        "4": [
            candidate(
                "1975",
                priority_rank=0,
            ),
            candidate(
                "1986",
                priority_rank=1,
            ),
        ],
    }

    assignment = (
        quiz_service._daq_match_unique_viable_candidates(
            candidate_map
        )
    )

    check(
        "Global assignment exists for the live constrained-slot shape",
        assignment
        is not None,
    )

    chosen = {
        slot_id: str(
            item[
                1
            ][
                "answer_text"
            ]
        )
        for slot_id, item
        in (
            assignment
            or {}
        ).items()
    }

    print(
        f"[INFO] chosen={chosen!r}"
    )

    check(
        "Five slots receive five distinct correct answers",
        len(
            set(
                chosen.values()
            )
        )
        == 5,
    )

    check(
        "Constrained slot 3 keeps one of its only two viable answers",
        chosen[
            "3"
        ]
        in {
            "1945",
            "2/9/1945",
        },
    )

    # Demonstrate why greedy ordering is insufficient.
    greedy_used: set[str] = set()
    greedy_failed = False

    for slot_id in (
        "0",
        "1",
        "2",
        "3",
        "4",
    ):
        selected = None

        for item in candidate_map[
            slot_id
        ]:
            answer = str(
                item[
                    1
                ][
                    "answer_text"
                ]
            )

            if (
                answer
                not in greedy_used
            ):
                selected = answer
                break

        if selected is None:
            greedy_failed = True
            break

        greedy_used.add(
            selected
        )

    check(
        "Original greedy slot order fails on the same feasible candidate graph",
        greedy_failed,
    )

    # Reservation must still apply for isolated recovery.
    reserved_assignment = (
        quiz_service._daq_match_unique_viable_candidates(
            {
                "0": [
                    candidate(
                        "1945",
                        priority_rank=0,
                    ),
                    candidate(
                        "1954",
                        priority_rank=1,
                    ),
                ]
            },
            reserved_correct_norms={
                "1945"
            },
        )
    )

    check(
        "Reserved answer remains excluded from isolated recovery",
        (
            reserved_assignment
            is not None
            and reserved_assignment[
                "0"
            ][
                1
            ][
                "answer_text"
            ]
            == "1954"
        ),
    )

    # True capacity failure must still fail.
    impossible = (
        quiz_service._daq_match_unique_viable_candidates(
            {
                "0": [
                    candidate(
                        "1945"
                    )
                ],
                "1": [
                    candidate(
                        "1945"
                    )
                ],
            }
        )
    )

    check(
        "True uniqueness-capacity failure still returns no assignment",
        impossible
        is None,
    )

    helper_source = inspect.getsource(
        quiz_service._daq_match_unique_viable_candidates
    )

    check(
        "Global matcher uses constrained-slot ordering",
        "Minimum Remaining Values"
        in helper_source,
    )

    check(
        "Global matcher uses backtracking rather than greedy commitment",
        "def search("
        in helper_source,
    )

    rebalance_source = inspect.getsource(
        quiz_service._daq_rebalance_fixed_choices_for_viability
    )

    check(
        "Runtime rebalance invokes global assignment",
        "_daq_match_unique_viable_candidates("
        in rebalance_source,
    )

    check(
        "Runtime keeps request-wide recovery reservations",
        "reserved_correct_norms"
        in rebalance_source,
    )

    print(
        "-" * 116
    )
    print(
        "RESULT: PASS — DAQ-V1.12 solves request-wide unique answer allocation "
        "globally, protects constrained slots, preserves recovery reservations, "
        "and still rejects genuinely impossible capacity."
    )
    print(
        "=" * 116
    )


if __name__ == "__main__":
    main()
