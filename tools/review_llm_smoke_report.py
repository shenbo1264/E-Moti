from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LLMSmokeReviewIssue:
    kind: str
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class LLMSmokeReview:
    ok: bool
    status: str
    provider: str
    model: str
    reason: str
    turn_count: int
    fallback_count: int
    issue_count: int
    speech_quality: dict[str, object]
    visual_action_coverage: dict[str, object]
    state_mutation_check: dict[str, object]
    issues: tuple[LLMSmokeReviewIssue, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "status": self.status,
            "provider": self.provider,
            "model": self.model,
            "reason": self.reason,
            "turn_count": self.turn_count,
            "fallback_count": self.fallback_count,
            "issue_count": self.issue_count,
            "speech_quality": dict(self.speech_quality),
            "visual_action_coverage": dict(self.visual_action_coverage),
            "state_mutation_check": dict(self.state_mutation_check),
            "issues": [issue.to_dict() for issue in self.issues],
        }


def review_llm_smoke_report(report: Mapping[str, object]) -> LLMSmokeReview:
    diagnostic = _mapping(report.get("diagnostic"))
    turns = _list_of_mappings(report.get("turns"))
    speech_quality = _speech_quality_summary(report.get("speech_quality"))
    visual_action_coverage = _mapping(report.get("visual_action_coverage"))
    state_mutation_check = _mapping(report.get("state_mutation_check")) or {"ok": True, "changed_fields": []}
    reason = _string(report.get("reason"))

    issues: list[LLMSmokeReviewIssue] = []
    if report.get("ok") is not True or reason:
        issues.append(LLMSmokeReviewIssue("report_failed", reason or "llm smoke report is not ok"))

    if diagnostic and diagnostic.get("ok") is False:
        stage = _string(diagnostic.get("stage")) or "unknown"
        diagnostic_reason = _string(diagnostic.get("reason")) or "failed"
        issues.append(LLMSmokeReviewIssue("diagnostic", f"{stage}: {diagnostic_reason}"))

    fallback_issues = _fallback_issues(turns)
    issues.extend(fallback_issues)

    if report.get("speech_quality") is None:
        issues.append(
            LLMSmokeReviewIssue(
                "speech_quality_missing",
                "speech_quality missing; rerun tools/llm_dialogue_smoke.py with the current smoke tool",
            )
        )
    elif speech_quality["violation_count"]:
        issues.append(LLMSmokeReviewIssue("speech_quality", _speech_quality_message(speech_quality)))

    if state_mutation_check.get("ok") is False:
        changed_fields = _string_list(state_mutation_check.get("changed_fields"))
        issues.append(LLMSmokeReviewIssue("state_mutation", "changed fields: " + ", ".join(changed_fields)))

    review_ok = not issues
    provider = _string(diagnostic.get("provider"))
    model = _string(diagnostic.get("model"))
    return LLMSmokeReview(
        ok=review_ok,
        status="passed" if review_ok else "needs_attention",
        provider=provider,
        model=model,
        reason=reason,
        turn_count=len(turns),
        fallback_count=len(fallback_issues),
        issue_count=len(issues),
        speech_quality=speech_quality,
        visual_action_coverage=dict(visual_action_coverage),
        state_mutation_check=dict(state_mutation_check),
        issues=tuple(issues),
    )


def render_llm_smoke_review_markdown(review: LLMSmokeReview) -> str:
    lines = [
        "# LLM Smoke Review",
        "",
        f"- Status: `{review.status}`",
        f"- Provider: `{review.provider or 'unknown'}`",
        f"- Model: `{review.model or 'unknown'}`",
        f"- Reason: `{review.reason or ''}`",
        f"- Turns: `{review.turn_count}`",
        f"- Fallback turns: `{review.fallback_count}`",
        f"- Speech quality violations: `{review.speech_quality['violation_count']}`",
        f"- State guard: `{'passed' if review.state_mutation_check.get('ok') is not False else 'failed'}`",
        "",
        "## Visual Action Coverage",
        "",
        f"- Expressions: `{review.visual_action_coverage.get('expression_count', 0)}` "
        f"{_inline_code_list(review.visual_action_coverage.get('expression_ids'))}",
        f"- Motions: `{review.visual_action_coverage.get('motion_count', 0)}` "
        f"{_inline_code_list(review.visual_action_coverage.get('motion_ids'))}",
    ]
    speech_violations = _list_of_mappings(review.speech_quality.get("violations"))
    if speech_violations:
        lines.extend(["", "## Speech Quality Violations", ""])
        for item in speech_violations:
            lines.append(
                f"- turn {item.get('turn')}: {_string(item.get('kind'))} speech_len={item.get('speech_len')}"
            )
    if review.issues:
        lines.extend(["", "## Issues", ""])
        for issue in review.issues:
            lines.append(f"- `{issue.kind}`: {issue.message}")
    lines.append("")
    return "\n".join(lines)


def _speech_quality_summary(value: object) -> dict[str, object]:
    source = _mapping(value)
    violations = _list_of_mappings(source.get("violations"))
    return {
        "min_speech_chars": _int(source.get("min_speech_chars")),
        "max_speech_chars": _int(source.get("max_speech_chars")),
        "empty_count": _int(source.get("empty_count")),
        "short_count": _int(source.get("short_count")),
        "long_count": _int(source.get("long_count")),
        "violation_count": len(violations),
        "violations": [dict(item) for item in violations],
    }


def _speech_quality_message(speech_quality: Mapping[str, object]) -> str:
    return (
        f"empty={speech_quality.get('empty_count', 0)},"
        f"short={speech_quality.get('short_count', 0)},"
        f"long={speech_quality.get('long_count', 0)}"
    )


def _fallback_issues(turns: tuple[Mapping[str, object], ...]) -> list[LLMSmokeReviewIssue]:
    issues: list[LLMSmokeReviewIssue] = []
    for turn in turns:
        fallback = _string(turn.get("fallback_reason"))
        if fallback:
            issues.append(LLMSmokeReviewIssue("turn_fallback", f"turn {turn.get('turn')}: {fallback}"))
    return issues


def _inline_code_list(value: object) -> str:
    items = _string_list(value)
    if not items:
        return "`[]`"
    return "`[" + ", ".join(items) + "]`"


def _mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list_of_mappings(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in (_string(item) for item in value) if item]


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""


def _int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _load_report(path: Path) -> tuple[dict[str, object], tuple[str, ...]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {}, (f"llm smoke report invalid: {exc}",)
    if not isinstance(payload, dict):
        return {}, ("llm smoke report must be a JSON object",)
    return payload, ()


def _write_text(path: str, text: str) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review an existing LLM smoke JSON report.")
    parser.add_argument("report")
    parser.add_argument("--json", default="", help="Optional JSON review output path.")
    parser.add_argument("--markdown", default="", help="Optional Markdown review output path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    payload, errors = _load_report(Path(args.report))
    if errors:
        review = LLMSmokeReview(
            ok=False,
            status="invalid_report",
            provider="",
            model="",
            reason=errors[0],
            turn_count=0,
            fallback_count=0,
            issue_count=len(errors),
            speech_quality=_speech_quality_summary({}),
            visual_action_coverage={},
            state_mutation_check={"ok": True, "changed_fields": []},
            issues=tuple(LLMSmokeReviewIssue("invalid_report", error) for error in errors),
        )
    else:
        review = review_llm_smoke_report(payload)
    review_payload = json.dumps(review.to_dict(), ensure_ascii=False, indent=2)
    _write_text(args.json, review_payload + "\n")
    _write_text(args.markdown, render_llm_smoke_review_markdown(review))
    print(review_payload)
    return 0 if review.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
