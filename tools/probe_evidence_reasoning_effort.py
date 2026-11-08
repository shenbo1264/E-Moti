import argparse
import json
from pathlib import Path

from tools.eval_ondemand_generation import recorded_app_client, redact


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output already exists")
    client, meter, metadata, secret = recorded_app_client(args.settings, max_requests=4, max_output_tokens=4096)
    if metadata["base_url"].rstrip("/") != "https://api.deepseek.com":
        raise ValueError("probe requires official DeepSeek endpoint")
    report = {"provider": metadata, "comparison": "saved default-high versus new low; seen regression only", "rows": []}
    suffix = (
        "Return exactly one JSON object using the fields requested in the task. "
        "All generated text belongs inside JSON string values. "
        "Do not output Markdown fences or any text outside the JSON object."
    )
    for method, query_id in [("routed", "v5_board_q1"), ("layered", "v5_board_q1"),
                             ("layered", "v5_board_q2"), ("layered", "v5_board_q6")]:
        source = args.source_dir / f"{method}-300.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        row = next(row for row in data["rows"] if row["query_id"] == query_id)
        before = row["evidence_judgment"]["requests"][0]
        wire = before["wire_payload"]
        system, user = wire["messages"]
        assert system["role"] == "system" and user["role"] == "user"
        assert system["content"].endswith(suffix)
        expected = {**wire, "reasoning_effort": "low"}

        def checked_transport(request, timeout):
            assert json.loads(request.data) == expected, "wire changed beyond reasoning_effort"
            return meter(request, timeout)

        client.transport = checked_transport
        result = {"method": method, "query_id": query_id, "query": row["query"], "before": before}
        try:
            result["content"] = client.complete(
                user["content"], system_prompt=system["content"][:-len(suffix)].rstrip("\n"),
                reasoning_effort="low",
            )
            result["parsed"] = json.loads(result["content"])
        except Exception as exc:
            # 诊断工具保留真实失败，不重试，也不将失败计成成功。
            result["error"] = f"{type(exc).__name__}: {exc}"
        result["after"] = meter.last
        report["rows"].append(result)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(redact(report, secret), ensure_ascii=False, indent=2), encoding="utf-8")
        print(method, query_id, "error" if "error" in result else "json_received", flush=True)
    client.close()


if __name__ == "__main__":
    main()
