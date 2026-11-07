from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import sys
from threading import Event
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from eval_chat_memory_formal import load_inputs, read_json, save_json, sha, journal_requires_payment
from persona_behavior_eval import FlashMeter, measured_usage
from guanghe_companion.expression_clients import _chat_completions_url, _json_request_headers
from guanghe_companion.expression_settings import ExpressionSettingsStore, provider_api_style


def parse_review_batch(raw, packets):
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        rows = [json.loads(line) for line in raw.strip().splitlines() if line.strip()]
    else:
        rows = value["reviews"] if isinstance(value, dict) and "reviews" in value else [value]
    expected = {row["id"]: row for row in packets}
    if (not isinstance(rows, list) or len(rows) != len(packets) or any(not isinstance(row, dict) for row in rows)
            or {row.get("id") for row in rows} != set(expected)):
        raise ValueError("judge must return exactly the supplied question IDs")
    # 哈希只绑定已冻结的实际答卷；不让模型改写版本，也不推断缺失的语义判断。
    return [{**row, "answer_sha256": expected[row["id"]]["answer_sha256"],
             "rubric_sha256": expected[row["id"]]["rubric_sha256"]} for row in rows]


def write_jsonl(path, rows):
    temporary = path.with_suffix(path.suffix + ".pending")
    temporary.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    temporary.replace(path)


def run(args):
    # 与作答进程分开：只有这个入口加载标准答案与上游评分材料。
    load_inputs(args.benchmark_root)
    spec = importlib.util.spec_from_file_location("emoti_upstream_grader", args.benchmark_root / "grading/grade.py")
    grader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(grader)
    answers = grader.indexed(grader.read_rows(args.answers))
    packets = list(grader.prepare(answers.values()))
    instructions_path = args.benchmark_root / "grading/judge-prompt.md"
    instructions = instructions_path.read_text(encoding="utf-8")
    settings = ExpressionSettingsStore(args.app_settings).load()
    if settings.model != "deepseek-flash":
        raise ValueError("grading requires configured deepseek-flash")
    config = {"answer_sha256": sha(args.answers), "model": settings.model, "base_url": settings.base_url,
              "provider": settings.provider, "timeout_seconds": settings.timeout_seconds, "max_output_tokens": 4096,
              "grader_sha256": sha(args.benchmark_root / "grading/grade.py"),
              "prompt_sha256": sha(instructions_path), "adapter_sha256": sha(Path(__file__)),
              "batch_size": args.batch_size, "grading": "real_model_semantic_review_not_human"}
    args.output.mkdir(parents=True, exist_ok=True)
    config_path = args.output / "config.json"
    if config_path.exists():
        if not args.resume:
            raise FileExistsError(config_path)
        if read_json(config_path) != config:
            raise ValueError("grading resume configuration changed")
    else:
        save_json(config_path, config)
    write_jsonl(args.output / "packets.jsonl", packets)
    batches = [packets[index:index + args.batch_size] for index in range(0, len(packets), args.batch_size)]
    if len(batches) > args.max_requests and not args.resume:
        raise ValueError("grading request cap smaller than required batch count")
    payment_required = Event()

    def review(index_packet):
        index, packet = index_packet
        path = args.output / "batches" / f"{index:04d}.json"
        if path.exists():
            result = read_json(path)
            if result["status"] == "inflight":
                result.update(status="not_run", error="interrupted semantic judgment; not automatically retried")
                save_json(path, result)
            return result
        result = {"ids": [row["id"] for row in packet], "status": "inflight"}
        save_json(path, result)
        if index >= args.max_requests or payment_required.is_set():
            result.update(status="not_run", error="provider HTTP 402" if payment_required.is_set() else "request budget")
            save_json(path, result)
            return result
        meter = FlashMeter(1, api_style=provider_api_style(settings.provider),
            journal_path=args.output / "batches" / f"{index:04d}-provider.json", secret=settings.api_key)
        try:
            # 离线评分材料不适用桌面单条8192字符限制；复用现有真实HTTP传输及逐请求日志。
            payload = {"model": settings.model, "max_tokens": 4096, "reasoning_effort": "low",
                "response_format": {"type": "json_object"}, "messages": [
                    {"role": "system", "content": instructions + '\n本批输出一个JSON对象，格式为{"reviews":[逐题判断对象]}。哈希字段由宿主绑定不可变材料，可以省略。'},
                    {"role": "user", "content": json.dumps(packet, ensure_ascii=False)}]}
            request = Request(_chat_completions_url(settings.base_url),
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=_json_request_headers(settings.api_key), method="POST")
            response = json.loads(meter(request, settings.timeout_seconds))
            raw = response["choices"][0]["message"]["content"]
            result["raw_judgment"] = raw
            reviews = parse_review_batch(raw, packet)
            # 使用上游原评分器校验每项布尔值/数量/边界，再接受该批语义评审。
            scored = list(grader.score(grader.indexed(packet), grader.indexed(reviews)))
            result.update(status="completed", reviews=reviews, judgments=scored)
        except Exception as exc:
            result.update(status="not_run", error=type(exc).__name__ + ": " + str(exc))
        finally:
            result["usage"] = measured_usage(meter)
            if journal_requires_payment(args.output / "batches" / f"{index:04d}-provider.json"):
                payment_required.set()
            save_json(path, result)
        return result

    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        results = list(executor.map(review, enumerate(batches)))
    reviews = [row for result in results if result["status"] == "completed" for row in result["reviews"]]
    judgments = [row for result in results if result["status"] == "completed" for row in result["judgments"]]
    write_jsonl(args.output / "reviews.jsonl", reviews)
    write_jsonl(args.output / "judgments.jsonl", judgments)
    report = grader.summarize(judgments)
    report.update(available_answers=len(answers), not_run_ids=[ident for result in results
        if result["status"] != "completed" for ident in result["ids"]],
        reviewer="deepseek-flash real semantic judgments; not human acceptance",
        requests=sum(result.get("usage", {}).get("calls", 0) for result in results),
        input_tokens=sum(result.get("usage", {}).get("input_tokens", 0) for result in results),
        output_tokens=sum(result.get("usage", {}).get("output_tokens", 0) for result in results))
    save_json(args.output / "summary.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Separate real Flash semantic grading using the fixed upstream rubric and scorer.")
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--app-settings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--jobs", type=int, choices=range(1, 7), default=3)
    parser.add_argument("--max-requests", type=int, default=200)
    parser.add_argument("--resume", action="store_true")
    print(json.dumps(run(parser.parse_args()), ensure_ascii=False))
