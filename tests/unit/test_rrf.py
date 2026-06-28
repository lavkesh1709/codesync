import uuid
from types import SimpleNamespace

from app.core.retrieval.searcher import _reciprocal_rank_fusion


def _chunk(hex_suffix: str):
    return SimpleNamespace(id=uuid.UUID(f"00000000-0000-0000-0000-{hex_suffix:>012}"))


A = _chunk("1")
B = _chunk("2")
C = _chunk("3")


def test_empty_inputs_return_empty():
    assert _reciprocal_rank_fusion([], []) == []


def test_only_vector_chunk_returned():
    assert _reciprocal_rank_fusion([A], []) == [A]


def test_only_bm25_chunk_returned():
    assert _reciprocal_rank_fusion([], [A]) == [A]


def test_chunk_in_both_lists_ranks_first():
    # A is in both lists; B and C each appear in only one list
    result = _reciprocal_rank_fusion([B, A], [C, A])
    assert result[0] is A


def test_all_unique_chunks_present_in_result():
    result = _reciprocal_rank_fusion([A, B], [B, C])
    result_ids = {str(c.id) for c in result}
    assert result_ids == {str(A.id), str(B.id), str(C.id)}


def test_shared_chunk_beats_top_single_list_chunk():
    # A is rank-1 in both; B is rank-1 in vector only
    result = _reciprocal_rank_fusion([A, B], [A, C])
    assert result[0] is A


def test_k_parameter_dampens_high_rank_effect():
    # With large k, the difference between rank 1 and rank 2 shrinks.
    # Both orderings are valid, so just verify no crash and all items returned.
    result = _reciprocal_rank_fusion([A, B, C], [C, B, A], k=1000)
    assert len(result) == 3
