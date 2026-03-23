"""Redis queue client used by worker tasks."""

from __future__ import annotations

import json
from typing import Any

from redis import Redis

from jobscout_shared.settings import Settings


class RedisQueue:
    def __init__(self, client: Redis, queue_key: str) -> None:
        self.client = client
        self.queue_key = queue_key

    @classmethod
    def from_settings(cls, settings: Settings) -> "RedisQueue":
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        return cls(client=client, queue_key=settings.worker_queue_key)

    def ping(self) -> bool:
        return bool(self.client.ping())

    def enqueue(self, payload: dict[str, Any]) -> None:
        self.client.rpush(self.queue_key, json.dumps(payload))

    def dequeue(self) -> dict[str, Any] | None:
        raw = self.client.lpop(self.queue_key)
        if raw is None:
            return None
        if isinstance(raw, list):
            return None
        if not isinstance(raw, str):
            raw = str(raw)
        return json.loads(raw)
