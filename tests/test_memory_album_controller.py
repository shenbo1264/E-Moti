from pathlib import Path
from guanghe_companion.companion_story_runtime import CompanionStoryRuntime
from guanghe_companion.memory_album_controller import MemoryAlbumController


def setup(tmp_path: Path):
    story=CompanionStoryRuntime.create(user_data_root=tmp_path,character_id='xingxi_pixel_pet')
    memory=story.memory.remember(kind='投喂',title='第一次热牛奶',summary='喝下第一杯热牛奶。',source='test',now=10,tags=('第一次',),user_confirmed=True)
    return story,MemoryAlbumController(story),memory


def test_album_snapshot(tmp_path: Path):
    story,c,m=setup(tmp_path); snap=c.snapshot(); assert snap['title']=='星屑回忆册' and snap['sections'][0]['cards'][0]['title']=='第一次热牛奶'


def test_album_pin_and_forget(tmp_path: Path):
    story,c,m=setup(tmp_path); c.pin(m.memory_id,True,now=20); assert next(row for row in story.memory.store.load_memories() if row.memory_id==m.memory_id).pinned
    c.forget(m.memory_id,now=30); assert next(row for row in story.memory.store.load_memories() if row.memory_id==m.memory_id).deleted


def test_album_correct_supersedes(tmp_path: Path):
    story,c,m=setup(tmp_path); c.correct(m.memory_id,title='第一杯热牛奶',summary='那晚一起喝过热牛奶。',now=40)
    rows=story.memory.store.load_memories(); assert any(row.supersedes==m.memory_id and row.title=='第一杯热牛奶' for row in rows)


def test_album_missing_memory_raises(tmp_path: Path):
    story,c,m=setup(tmp_path)
    try: c.pin('missing')
    except KeyError: pass
    else: raise AssertionError('expected KeyError')


def test_album_source_view_is_traceable_without_raw_metadata(tmp_path: Path):
    story, controller, memory = setup(tmp_path)

    source = controller.source_details(memory.memory_id)

    assert source["source"] == "test"
    assert source["memory_id"] == memory.memory_id
    assert "metadata" not in source
    assert "raw_text" not in source
