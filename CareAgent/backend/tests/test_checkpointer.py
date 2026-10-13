import asyncio
from langgraph.checkpoint.base import empty_checkpoint
from careagent.checkpointer import OracleSaver


def exercise_saver(factory):
    saver = OracleSaver(factory)
    config = {"configurable": {"thread_id": "checkpoint-test"}}
    checkpoint = empty_checkpoint()
    checkpoint["channel_values"] = {"message": "Hello", "binary": b"\x00\xff", "nested": {"values": [1, 2]}}
    first = saver.put(config, checkpoint, {"source": "input", "step": 0, "parents": {}}, {})
    saver.put_writes(first, [("output", {"ok": True}), ("branch:to:account", None)], "task-1")
    saver.put_writes(first, [("output", {"ok": False})], "task-1")
    restored = saver.get_tuple(first)
    assert restored.checkpoint["channel_values"] == checkpoint["channel_values"]
    assert restored.pending_writes == [
        ("task-1", "output", {"ok": True}),
        ("task-1", "branch:to:account", None),
    ]
    checkpoint2 = empty_checkpoint()
    second = saver.put(first, checkpoint2, {"source": "loop", "step": 1, "parents": {}}, {})
    assert saver.get_tuple(second).parent_config == first
    assert len(list(saver.list(config))) == 2
    assert len(list(saver.list(config, filter={"source": "input"}))) == 1
    assert len(list(saver.list(config, before=second))) == 1
    assert len(list(saver.list(config, limit=1))) == 1

    async def async_ops():
        assert (await saver.aget_tuple(second)).checkpoint["id"] == checkpoint2["id"]
        assert len([row async for row in saver.alist(config)]) == 2
        await saver.aput_writes(second, [("result", 42)], "task-2")
        assert (await saver.aget_tuple(second)).pending_writes[0][2] == 42
        await saver.adelete_thread("checkpoint-test")

    asyncio.run(async_ops())
    assert saver.get_tuple(config) is None


def test_checkpoint_roundtrip(factory):
    exercise_saver(factory)
