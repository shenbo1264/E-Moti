import json

import pytest

from tools.eval_chat_memory_formal import ordered_questions, load_checkpoint, save_json, collect_answers
from tools.grade_chat_memory_formal import parse_review_batch


def question(ident, now, cutoff, persona="P01"):
    return {"id": ident, "persona": persona, "now": now, "cutoff_turn": cutoff}


def test_schedule_orders_exam_time_without_advancing_history_cutoff():
    rows = [question("late", "2026-01-04T12:00:00+08:00", 3),
            question("early", "2026-01-03T12:00:00+08:00", 3),
            question("first", "2026-01-01T12:00:00+08:00", 1)]
    ordered = ordered_questions(rows, "P01")
    assert [row["id"] for row in ordered] == ["first", "early", "late"]
    assert [row["cutoff_turn"] for row in ordered] == [1, 3, 3]


def test_schedule_rejects_backwards_cutoff():
    with pytest.raises(ValueError, match="cutoff"):
        ordered_questions([question("a", "2026-01-01T12:00:00+08:00", 3),
            question("b", "2026-01-02T12:00:00+08:00", 2)], "P01")


def test_checkpoint_rejects_changed_source_or_uncertain_replay(tmp_path):
    path = tmp_path / "checkpoint.json"
    config = {"source": "one", "persona": "P01"}
    state = load_checkpoint(path, config, resume=False)
    state["inflight"] = {"kind": "replay", "turn": 4}
    save_json(path, state)
    with pytest.raises(RuntimeError, match="uncertain replay"):
        load_checkpoint(path, config, resume=True)
    state["inflight"] = None
    save_json(path, state)
    with pytest.raises(ValueError, match="configuration"):
        load_checkpoint(path, {**config, "source": "two"}, resume=True)


def test_answer_export_preserves_failures_separately(tmp_path):
    folder = tmp_path / "P01" / "answers"
    folder.mkdir(parents=True)
    save_json(folder / "a.json", {"id": "a", "model_status": "completed", "answer": {"reply": ["答复"]}})
    save_json(folder / "b.json", {"id": "b", "model_status": "failed", "answer": {"reply": ["本地占位"]}})
    report = collect_answers(tmp_path)
    assert report["answered"] == 1
    assert report["failed"] == 1
    answers = [json.loads(line) for line in (tmp_path / "answers.jsonl").read_text(encoding="utf-8").splitlines()]
    assert answers == [{"id": "a", "answer": "答复"}]


def test_missing_judgment_is_not_filled_with_false():
    with pytest.raises(ValueError, match="exactly"):
        parse_review_batch('{"id":"a"}', [{"id": "a"}, {"id": "b"}])


def test_judgment_binds_actual_answer_hash_without_model_rewriting():
    packet = {"id": "a", "answer_sha256": "answer-version", "rubric_sha256": "rubric-version"}
    row = parse_review_batch('{"id":"a","required":[true],"answer_sha256":"invented"}', [packet])[0]
    assert row["required"] == [True]
    assert row["answer_sha256"] == "answer-version"


def test_judgment_accepts_pretty_json_wrapper_and_preserves_reason():
    packet = {"id": "a", "answer_sha256": "answer", "rubric_sha256": "rubric"}
    raw = json.dumps({"reviews": [{"id": "a", "required": [True], "reason": "有明确证据"}]}, indent=2)
    assert parse_review_batch(raw, [packet])[0]["reason"] == "有明确证据"
