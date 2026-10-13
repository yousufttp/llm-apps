"""SQLAlchemy checkpoint saver: Oracle in deployment, SQLite only in unit tests."""

import asyncio
import json
from sqlalchemy import select, delete
from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple, WRITES_IDX_MAP
from .models import CheckpointRow, CheckpointWrite


_EMPTY_TYPE_PREFIX = "empty:"


def encode_payload(kind, payload):
    """Keep serialized empty values non-NULL in Oracle.

    Oracle treats zero-length binary values as NULL, including values bound to
    BLOB columns. Preserve that distinction with a tagged one-byte sentinel.
    """
    if payload == b"":
        return f"{_EMPTY_TYPE_PREFIX}{kind}", b"\x00"
    return kind, payload


def decode_payload(kind, payload):
    if kind.startswith(_EMPTY_TYPE_PREFIX):
        return kind[len(_EMPTY_TYPE_PREFIX) :], b""
    return kind, payload


def parts(config):
    c = config["configurable"]
    return c["thread_id"], c.get("checkpoint_ns") or "root", c.get("checkpoint_id")


def configuration(thread, namespace, checkpoint):
    return {
        "configurable": {
            "thread_id": thread,
            "checkpoint_ns": "" if namespace == "root" else namespace,
            "checkpoint_id": checkpoint,
        }
    }


class OracleSaver(BaseCheckpointSaver):
    def __init__(self, factory):
        super().__init__()
        self.factory = factory

    def _tuple(self, db, row):
        writes = db.scalars(
            select(CheckpointWrite)
            .where(
                CheckpointWrite.thread_id == row.thread_id,
                CheckpointWrite.namespace == row.namespace,
                CheckpointWrite.checkpoint_id == row.checkpoint_id,
            )
            .order_by(CheckpointWrite.task_id, CheckpointWrite.write_index)
        ).all()
        return CheckpointTuple(
            config=configuration(row.thread_id, row.namespace, row.checkpoint_id),
            checkpoint=self.serde.loads_typed(decode_payload(row.payload_type, row.payload)),
            metadata=json.loads(row.metadata_json),
            parent_config=configuration(row.thread_id, row.namespace, row.parent_id)
            if row.parent_id
            else None,
            pending_writes=[
                (w.task_id, w.channel, self.serde.loads_typed(decode_payload(w.payload_type, w.payload)))
                for w in writes
            ],
        )

    def get_tuple(self, config):
        thread, namespace, checkpoint = parts(config)
        with self.factory() as db:
            q = select(CheckpointRow).where(
                CheckpointRow.thread_id == thread, CheckpointRow.namespace == namespace
            )
            if checkpoint:
                q = q.where(CheckpointRow.checkpoint_id == checkpoint)
            row = db.scalars(q.order_by(CheckpointRow.checkpoint_id.desc()).limit(1)).first()
            return self._tuple(db, row) if row else None

    def list(self, config, *, filter=None, before=None, limit=None):
        with self.factory() as db:
            q = select(CheckpointRow)
            if config:
                thread, namespace, _ = parts(config)
                q = q.where(CheckpointRow.thread_id == thread, CheckpointRow.namespace == namespace)
            if before:
                q = q.where(CheckpointRow.checkpoint_id < parts(before)[2])
            count = 0
            for row in db.scalars(q.order_by(CheckpointRow.checkpoint_id.desc())):
                metadata = json.loads(row.metadata_json)
                if filter and any(metadata.get(k) != v for k, v in filter.items()):
                    continue
                if limit is not None and count >= limit:
                    break
                yield self._tuple(db, row)
                count += 1

    def put(self, config, checkpoint, metadata, new_versions):
        thread, namespace, parent = parts(config)
        kind, payload = self.serde.dumps_typed(checkpoint)
        kind, payload = encode_payload(kind, payload)
        with self.factory.begin() as db:
            row = db.scalar(
                select(CheckpointRow).where(
                    CheckpointRow.thread_id == thread,
                    CheckpointRow.namespace == namespace,
                    CheckpointRow.checkpoint_id == checkpoint["id"],
                )
            )
            if row is None:
                db.add(
                    CheckpointRow(
                        thread_id=thread,
                        namespace=namespace,
                        checkpoint_id=checkpoint["id"],
                        parent_id=parent,
                        payload_type=kind,
                        payload=payload,
                        metadata_json=json.dumps(metadata),
                    )
                )
        return configuration(thread, namespace, checkpoint["id"])

    def put_writes(self, config, writes, task_id, task_path=""):
        thread, namespace, checkpoint = parts(config)
        with self.factory.begin() as db:
            for index, (channel, value) in enumerate(writes):
                index = WRITES_IDX_MAP.get(channel, index)
                row = db.scalar(
                    select(CheckpointWrite).where(
                        CheckpointWrite.thread_id == thread,
                        CheckpointWrite.namespace == namespace,
                        CheckpointWrite.checkpoint_id == checkpoint,
                        CheckpointWrite.task_id == task_id,
                        CheckpointWrite.write_index == index,
                    )
                )
                kind, payload = self.serde.dumps_typed(value)
                kind, payload = encode_payload(kind, payload)
                if row is None:
                    db.add(
                        CheckpointWrite(
                            thread_id=thread,
                            namespace=namespace,
                            checkpoint_id=checkpoint,
                            task_id=task_id,
                            task_path=task_path or None,
                            write_index=index,
                            channel=channel,
                            payload_type=kind,
                            payload=payload,
                        )
                    )
                elif index < 0:
                    row.channel, row.payload_type, row.payload = channel, kind, payload

    def delete_thread(self, thread_id):
        with self.factory.begin() as db:
            for model in (CheckpointWrite, CheckpointRow):
                db.execute(delete(model).where(model.thread_id == thread_id))

    async def aget_tuple(self, config):
        return await asyncio.to_thread(self.get_tuple, config)

    async def alist(self, config, *, filter=None, before=None, limit=None):
        rows = await asyncio.to_thread(
            lambda: list(self.list(config, filter=filter, before=before, limit=limit))
        )
        for row in rows:
            yield row

    async def aput(self, config, checkpoint, metadata, new_versions):
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)

    async def adelete_thread(self, thread_id):
        await asyncio.to_thread(self.delete_thread, thread_id)
