import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path


def build(dataset, generation):
    memories = {row["id"]: row for row in dataset["memories"]}
    queries = {row["id"]: row for row in dataset["queries"]}
    packets, mapping = defaultdict(list), {}
    for result in generation["rows"]:
        query = queries[result["query_id"]]
        key = result["review_id"]
        label = sha256(("blind-20261101:" + key).encode()).hexdigest()[:12]
        mapping[label] = {"review_id": key, "method": result["method"], "query_id": result["query_id"]}
        facts = [memories[key]["summary"] for key in query.get("gold_ids", [])]
        forbidden = [memories[key]["summary"] for key in query.get("forbidden_ids", []) if key in memories]
        persona_line = next((line for line in result.get("final_prompt", "").splitlines() if line.startswith("persona: ")), "")
        packets[result["story_id"]].append({"blind_id": label, "query_id": result["query_id"],
            "query": result["query"], "history": query.get("history", []),
            "gold_facts": facts, "forbidden_facts": forbidden,
            "expected_status": query.get("expected_status"), "persona": persona_line.removeprefix("persona: "),
            "generation_status": result["status"], "schema_status": result.get("schema_status"),
            "answer": result.get("answer"), "reason_if_failed": result.get("reason")})
    for rows in packets.values():
        rows.sort(key=lambda row: (row["query_id"], row["blind_id"]))
    return packets, mapping


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--generation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    packets, mapping = build(json.loads(args.dataset.read_text(encoding="utf-8")),
        json.loads(args.generation.read_text(encoding="utf-8")))
    args.output.mkdir(parents=True, exist_ok=True)
    rubric = {"reviewer_type": "independent_AI_text_review_not_human_acceptance",
        "accuracy": "pass=所问全部有据事实正确，未知不猜；partial=有据部分正确但漏答；fail=答错、无端拒绝已知事实或编造。失败请求标not_run。",
        "persona": "pass=符合给定角色，自然简短有独立语气；partial=套话/多余建议或解释/突兀点名；fail=明显角色违背、关系施压或虚构亲历。",
        "unsupported_claims": "逐条指出原句和缺乏的依据；普通不涉及事实的安慰/玩笑不算编造。",
        "natural_unknown": "只评gold为空且需要事实的题；简短自然未知为pass，追问重告刚忘信息/虚构从未说过为fail。其余not_applicable。",
        "output": "每个blind_id一条，accuracy/persona/unsupported_claims/natural_unknown/reason；保留所有失败和完整分母。"}
    for story, rows in packets.items():
        (args.output / f"{story}.json").write_text(json.dumps({"rubric": rubric, "rows": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "mapping-private.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"stories": len(packets), "cases": len(mapping), "output": str(args.output)}))


if __name__ == "__main__":
    main()
