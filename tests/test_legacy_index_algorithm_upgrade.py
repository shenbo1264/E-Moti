from contextlib import closing
import json
import sqlite3

import pytest

from guanghe_companion.emotional_memory import EmotionalMemoryEntry, EmotionalMemoryStore
from guanghe_companion.memory_index import IndexedMemoryQuery


OLD_ALGORITHM = "typed-literal-v2:structured-value-v1:cn-grams-v1:fts-rowid-v1:structured-pk-v1:raw-diff-v1"


@pytest.mark.parametrize("title,summary,predicate,supersedes", [
    ("陶笛练习目标", "我正在练习山间序曲", "陶笛练习目标", ""),
    ("favorite mineral", "My favorite mineral is quartz.", "favorite mineral", ""),
    ("饮品偏好", "现在喜欢乌梅茶", "preference:饮料偏好:like", "prior-card"),
    ("工作城市", "工作城市已改为银杏城", "工作城市", "prior-card"),
])
def test_existing_v2_projection_rebuilds_without_mutating_authority(tmp_path, title, summary, predicate, supersedes):
    store = EmotionalMemoryStore(tmp_path, "pet")
    entry = EmotionalMemoryEntry(memory_id="saved-card", character_id="pet", owner_id=store.owner_id,
        kind="玩家希望被记住", title=title, summary=summary,
        source="user_correction" if supersedes else "explicit_user_request", user_confirmed=True,
        occurred_at=1, created_at=1, updated_at=1, supersedes=supersedes)
    store.save_memories((entry,))
    with closing(sqlite3.connect(store.state_path)) as connection:
        authority_before = connection.execute("SELECT payload FROM memory_state").fetchone()[0]
        old_generation = connection.execute("SELECT generation FROM memory_index_meta").fetchone()[0]
        old_digest = connection.execute("SELECT raw_digest FROM memory_index_entries").fetchone()[0]
        # 重现包基线的真实派生字段；权威JSON、指纹和raw_digest保持原样。
        connection.execute("UPDATE memory_index_entries SET subject='', entity_id='', predicate='', fact_slot='', fact_domain='', fact_value=''")
        connection.execute("UPDATE memory_index_meta SET algorithm_version=?,dirty=0", (OLD_ALGORITHM,))
        connection.commit()
    reopened = EmotionalMemoryStore(tmp_path, "pet")
    snapshot = reopened.read_indexed_snapshot(IndexedMemoryQuery(predicates=(predicate,), limit=4), now=2,
        include_chapters=False, include_profile_sources=False)
    assert [row.memory_id for row in snapshot.entries] == [entry.memory_id]
    assert snapshot.entries[0].evidence_fingerprint() == entry.evidence_fingerprint()
    with closing(sqlite3.connect(store.state_path)) as connection:
        assert connection.execute("SELECT payload FROM memory_state").fetchone()[0] == authority_before
        assert connection.execute("SELECT raw_digest FROM memory_index_entries").fetchone()[0] == old_digest
        assert connection.execute("SELECT generation FROM memory_index_meta").fetchone()[0] != old_generation
    assert snapshot.context_epoch == json.loads(authority_before)["context_epoch"]
