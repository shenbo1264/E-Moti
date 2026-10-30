from dataclasses import asdict, replace
import json
import os
from pathlib import Path
from time import perf_counter

import pytest

from guanghe_companion.chat_memory_extraction import ChatMemoryExtraction, extract_memory
from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.expression_clients import client_config_from_settings
from guanghe_companion.expression_settings import ExpressionSettingsStore


@pytest.mark.skipif(os.environ.get("EMOTI_EXTRACTION_PROVIDER_TEST") != "1", reason="explicit real provider test")
@pytest.mark.parametrize("text,expected", [
    ("平时大家都管我叫青禾，这个称呼我很喜欢", "saved"),
    ("我家养的小狗名字是布丁", "saved"),
    ("如果我以后住在大理，那该多好", "ignored"),
    ("她说她对杏仁过敏", "ignored"),
], ids=["nickname", "pet", "hypothetical", "reported"])
def test_real_provider_extraction(tmp_path, text, expected):
    settings = ExpressionSettingsStore(Path(os.environ["LOCALAPPDATA"]) / "E-Moti" / "expression_settings.json").load()
    config = client_config_from_settings(replace(settings, timeout_seconds=60))
    assert config.client is not None, "real provider is not configured"
    config.client.max_tokens = int(os.environ.get("EMOTI_EXTRACTION_TOKEN_BUDGET", "4096"))
    transport = config.client.transport
    usage = {}
    def measured_transport(request, timeout):
        raw = transport(request, timeout)
        usage.update(json.loads(raw).get("usage", {}))
        return raw
    config.client.transport = measured_transport
    memory = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    extractor = ChatMemoryExtraction(memory)
    envelope = extractor.prepare(text, now=10, mode="auto", generation=0)
    started = perf_counter()
    report = {"text": text, "model": settings.model, "usage": usage,
              "max_tokens": config.client.max_tokens, "expected": expected}
    path = Path("artifacts/codex_handoff/semantic-extraction-provider.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        proposals = extract_memory(envelope, config.client)
        report["proposals"] = [asdict(p) for p in proposals]
        result = extractor.apply(envelope, proposals, now=11, mode="auto", generation=0)
        report["actual"] = result.status
    except Exception as exc:
        report["error"] = type(exc).__name__
        raise
    finally:
        report["latency_seconds"] = perf_counter() - started
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(report, ensure_ascii=False) + "\n")
    assert result.status == expected
