import pytest

from guanghe_companion.emotional_memory_service import EmotionalMemoryService
from guanghe_companion.memory_evidence_judgment import MemoryEvidenceJudge
from guanghe_companion.semantic_memory import SemanticMemoryRetriever


class CountingRetriever(SemanticMemoryRetriever):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.prepare_calls = 0

    def prepare_indexed(self, *args, **kwargs):
        self.prepare_calls += 1
        return super().prepare_indexed(*args, **kwargs)


class CountingJudge(MemoryEvidenceJudge):
    def __init__(self):
        super().__init__(self.unexpected_model_call)
        self.prepare_calls = 0

    @staticmethod
    def unexpected_model_call(prompt):
        raise AssertionError("empty independent archive must not request a model")

    def prepare(self, *args, **kwargs):
        self.prepare_calls += 1
        return super().prepare(*args, **kwargs)


@pytest.fixture
def service(tmp_path):
    # 使用真实空SQLite及真实异步准备；只计数入口，不提供模型假答案。
    instance = EmotionalMemoryService(root=tmp_path, character_id="xingxi_pixel_pet")
    instance.semantic_retriever = CountingRetriever(
        cache_dir=tmp_path / "models", character_id=instance.character_id,
        owner_id=instance.owner_id, local_files_only=True,
    )
    instance.evidence_judge = CountingJudge()
    yield instance
    instance.close(wait=True)


def finish(future):
    if future is not None:
        future.result(timeout=10)


@pytest.mark.parametrize("query", ["", "   ", "你好呀！", "谢谢你", "今天有点累", "陪我待一会儿"])
def test_whole_casual_sentence_skips_all_candidate_preparation(service, query):
    judge = service.evidence_judge
    generation = judge._generation
    judge.prepare_rows_loaded = 5
    judge.prepare_retrieval_calls = 2
    finish(service.prepare_retrieval(query, now=10, history=(
        {"role": "user", "text": "我的修理预约是什么时候？"},
    )))
    assert service.semantic_retriever.prepare_calls == 0
    assert judge.prepare_calls == 0
    assert judge._generation > generation
    assert judge.status == "not_needed"
    assert judge.prepare_rows_loaded == 0
    assert judge.prepare_retrieval_calls == 0


@pytest.mark.parametrize("query,history", [
    ("你好，我的维修预约是什么时候？", ()),
    ("谢谢，肩带长度再报一遍", ()),
    ("别提以前的经历，我的过敏食物是什么？", ()),
    ("假如按我之前的预约时间，我要几点出门？", ()),
    ("白色温度探针校准时偏了多少？", ()),
    ("那结尾停在哪儿，不往后写到哪儿？", (
        {"role": "user", "text": "我们继续整理小说的大纲。"},
    )),
    ("那我的呢？", ({"role": "user", "text": "我的同事住在哪儿？"},)),
])
def test_mixed_or_ambiguous_chat_still_enters_evidence_preparation(service, query, history):
    finish(service.prepare_retrieval(query, now=10, history=history))
    assert service.semantic_retriever.prepare_calls == 1
    assert service.evidence_judge.prepare_calls == 1
