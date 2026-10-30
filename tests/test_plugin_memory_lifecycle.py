from dataclasses import replace

from guanghe_companion.companion_story_runtime import CompanionStoryRuntime
from guanghe_companion.plugin_api import EventDispatchReport, MemoryProposal, MemoryProposalReport, PluginEvent
from guanghe_companion.plugin_story_bridge import PluginStoryBridge


def bridge(tmp_path, *, confirmation=False):
    proposal = MemoryProposal(proposal_id="sample:shared-star", kind="共同日常", title="一起看星星",
        summary="完成了一次观星", source="plugin:sample", source_ids=("star-event",),
        requires_user_confirmation=confirmation)
    class Plugins:
        def emit(self, event): return EventDispatchReport()
        def collect_memory_proposals(self, event): return MemoryProposalReport(proposals=(proposal,))
    story = CompanionStoryRuntime.create(user_data_root=tmp_path, character_id="xingxi")
    return PluginStoryBridge(story, Plugins(), "xingxi")


def event(**kwargs):
    return PluginEvent(event_type="plugin.sample.completed", event_id="star-event",
        character_id="xingxi", occurred_at=10, source_plugin_id="sample", durable=True, **kwargs)


def test_plugin_pending_proposal_can_actually_be_inspected_confirmed_and_forgotten(tmp_path):
    b = bridge(tmp_path, confirmation=True)
    result = b.process_plugin_event(event())
    assert result.pending_confirmation == ("sample:shared-star",)
    assert "sample:shared-star" in b.story.memory.pending_candidates
    memory = b.story.memory.confirm_candidate("sample:shared-star", now=11)
    assert memory.source_ids == ("star-event",) and memory.user_confirmed
    b.story.memory.forget(memory.memory_id, now=12)
    b.process_plugin_event(replace(event(), occurred_at=20))
    assert not b.story.memory.recall("星星", now=21)


def test_plugin_completed_event_has_provenance_but_not_fake_user_confirmation(tmp_path):
    b = bridge(tmp_path)
    result = b.process_plugin_event(event())
    assert len(result.memory_ids) == 1
    memory = b.story.memory.store.load_memories()[0]
    assert memory.source_ids == ("star-event",)
    assert not memory.user_confirmed


def test_transient_plugin_event_cannot_implicitly_become_a_shared_memory(tmp_path):
    b = bridge(tmp_path)
    result = b.process_plugin_event(replace(event(), durable=False))
    assert not result.memory_ids
    assert result.rejected_proposals


def test_plugin_from_another_character_does_not_write_memories(tmp_path):
    b = bridge(tmp_path)
    result = b.process_plugin_event(replace(event(), character_id="other"))
    assert not result.memory_ids
    assert not b.story.memory.store.load_memories()
