from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path


def review_session_quality(report: Mapping[str, object]) -> dict[str, object]:
    turns = _list_of_mappings(report.get("turns"))
    speeches = [_turn_speech(turn) for turn in turns]
    non_empty_speeches = [speech for speech in speeches if speech]
    expression_ids = _expression_ids(turns)
    changed_fields = _changed_fields(report)
    reasons: list[str] = []

    if not turns:
        reasons.append("no_turns")
    repeated_speech_failed = False
    if len(non_empty_speeches) >= 3:
        distinct_speech_count = len(set(non_empty_speeches))
        repeated_speech_failed = distinct_speech_count < max(2, len(non_empty_speeches) // 2)
        if repeated_speech_failed:
            reasons.append("repeated_speech")
    low_expression_diversity = len(expression_ids) < min(3, max(1, len(turns)))
    if low_expression_diversity:
        reasons.append("low_expression_diversity")
    if changed_fields:
        reasons.append("state_mutated")
    if report.get("ok") is False or _text(report.get("reason")):
        reasons.append("source_report_failed")

    return {
        "ok": not reasons,
        "status": "passed" if not reasons else "needs_attention",
        "reasons": reasons,
        "turn_count": len(turns),
        "distinct_speech_count": len(set(non_empty_speeches)),
        "repeated_speech": "failed" if repeated_speech_failed else "passed",
        "expression_diversity_count": len(expression_ids),
        "expression_ids": expression_ids,
        "state_mutation": "failed" if changed_fields else "passed",
        "changed_fields": changed_fields,
        "next_action": _next_action(reasons),
    }


def render_session_quality_markdown(review: Mapping[str, object]) -> str:
    lines = [
        "# LLM Session Quality Review",
        "",
        f"- Status: `{_text(review.get('status')) or 'unknown'}`",
        f"- Turn count: `{_int(review.get('turn_count'))}`",
        f"- Distinct speech count: `{_int(review.get('distinct_speech_count'))}`",
        f"- Repeated speech: `{_text(review.get('repeated_speech')) or 'unknown'}`",
        f"- Expression diversity: `{_int(review.get('expression_diversity_count'))}`",
        f"- State mutation: `{_text(review.get('state_mutation')) or 'unknown'}`",
        f"- Reasons: `{', '.join(_string_list(review.get('reasons')))}`",
        f"- Next action: {_text(review.get('next_action')) or 'none'}",
        "",
    ]
    expression_ids = _string_list(review.get("expression_ids"))
    if expression_ids:
        lines.extend(["## Expression IDs", "", "- " + ", ".join(f"`{item}`" for item in expression_ids), ""])
    changed_fields = _string_list(review.get("changed_fields"))
    if changed_fields:
        lines.extend(["## Changed Fields", "", "- " + ", ".join(f"`{item}`" for item in changed_fields), ""])
    return "\n".join(lines)


def _next_action(reasons: list[str]) -> str:
    if not reasons:
        return "session quality gate passed"
    if "state_mutated" in reasons:
        return "inspect typed event and state guard output before rerunning"
    if "repeated_speech" in reasons or "low_expression_diversity" in reasons:
        return "tune prompts, character performance profile, or provider model"
    if "no_turns" in reasons:
        return "rerun dialogue smoke with player-like session turns"
    return "inspect source smoke report"


def _turn_speech(turn: Mapping[str, object]) -> str:
    for key in ("speech", "speech_preview"):
        value = turn.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _expression_ids(turns: list[Mapping[str, object]]) -> list[str]:
    ids: set[str] = set()
    for turn in turns:
        actions = _list_of_mappings(turn.get("visual_actions"))
        for action in actions:
            if action.get("type") != "expression":
                continue
            action_id = _text(action.get("id"))
            if action_id:
                ids.add(action_id)
    return sorted(ids)


def _changed_fields(report: Mapping[str, object]) -> list[str]:
    state_mutation = _mapping(report.get("state_mutation_check")) or _mapping(report.get("state_mutation"))
    return _string_list(state_mutation.get("changed_fields"))


def _load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid session quality input: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("session quality input must be a JSON object")
    return payload


def _write_json(path: str, payload: Mapping[str, object]) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: str, text: str) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list_of_mappings(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in (_text(item) for item in value) if item]


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review an LLM dialogue smoke report for short-session quality.")
    parser.add_argument("report")
    parser.add_argument("--json", default="", help="Optional JSON review output path.")
    parser.add_argument("--markdown", default="", help="Optional Markdown review output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        source = _load_json(Path(args.report))
        review = review_session_quality(source)
    except ValueError as exc:
        review = {
            "ok": False,
            "status": "invalid",
            "reasons": ["invalid_report"],
            "turn_count": 0,
            "distinct_speech_count": 0,
            "repeated_speech": "failed",
            "expression_diversity_count": 0,
            "expression_ids": [],
            "state_mutation": "unknown",
            "changed_fields": [],
            "next_action": str(exc),
        }
    _write_json(args.json, review)
    _write_text(args.markdown, render_session_quality_markdown(review))
    print(json.dumps(review, ensure_ascii=False, indent=2))
    return 0 if review.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
