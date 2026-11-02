"""Past execution evidence cannot prove that current reuse will succeed."""
from guanghe_companion.emotional_memory_service import EmotionalMemoryService


def task(service, app, version, cause):
    return service.remember(kind="任务经验", title=f"{app} 导出失败",
        summary=f"{app} {version} 导出因{cause}失败。", source="executor", source_ids=(app + ":run:1",),
        scope="task_experience", now=10,
        metadata={"app": app, "version": version, "outcome": "failed", "cause": cause,
                  "preconditions": ["离线模式", "本地已有文件"]})


def test_named_application_excludes_near_identical_other_executor(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="pet")
    right = task(service, "DraftBox", "2.0", "目录权限不足")
    task(service, "GraphBox", "2.0", "文件名冲突")
    result = service.retrieve("上次 DraftBox 2.0 导出为什么失败？", now=20)
    assert result.trace.selected_memory_ids == (right.memory_id,)


def test_past_task_is_not_current_applicability_proof(tmp_path):
    service = EmotionalMemoryService(root=tmp_path, character_id="pet")
    task(service, "DraftBox", "2.0", "目录权限不足")
    result = service.retrieve("这次 DraftBox 2.0 导出为什么失败，能保证按上次办法直接解决吗？", now=20)
    assert result.bundle.memories
    assert result.trace.status == "insufficient"
    task_states = [s for s in result.trace.intent_status if s["route"] == "task"]
    assert task_states and all(s["applicability"] == "requires_current_validation" for s in task_states)
    assert "不保证" in result.bundle.retrieval["instruction"]
