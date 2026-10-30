from __future__ import annotations

import pytest

from guanghe_companion.memory_fusion import reciprocal_rank_fusion


def test_empty_rankings_return_no_candidates() -> None:
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_agreement_between_retrievers_promotes_the_shared_memory() -> None:
    result = reciprocal_rank_fusion([["lexical", "shared"], ["semantic", "shared"]])

    assert [memory_id for memory_id, _ in result] == ["shared", "lexical", "semantic"]
    assert result[0][1] == pytest.approx(2 / 62)
    assert result[1][1] == pytest.approx(1 / 61)


def test_duplicate_ids_in_one_retriever_do_not_inflate_scores_or_shift_ranks() -> None:
    assert reciprocal_rank_fusion([["a", "a", "b"], ["b"]]) == reciprocal_rank_fusion(
        [["a", "b"], ["b"]]
    )


def test_ties_keep_first_seen_order_for_reproducible_context() -> None:
    result = reciprocal_rank_fusion([["z"], ["a"], ["m"]])

    assert [memory_id for memory_id, _ in result] == ["z", "a", "m"]


def test_rank_constant_changes_scores_without_changing_single_list_order() -> None:
    result = reciprocal_rank_fusion([["first", "second", "third"]], rank_constant=1)

    assert result == [("first", 1 / 2), ("second", 1 / 3), ("third", 1 / 4)]


@pytest.mark.parametrize("rank_constant", [0, -1, 1.5, True])
def test_rank_constant_must_be_a_positive_integer(rank_constant: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        reciprocal_rank_fusion([["a"]], rank_constant=rank_constant)
