import pytest

from app.worker import recover_processing_jobs


class FakeRedis:
    def __init__(self, lists=None):
        self.lists = {name: list(values) for name, values in (lists or {}).items()}
        self.deleted = []

    async def lpop(self, key):
        values = self.lists.setdefault(key, [])
        return values.pop(0) if values else None

    async def rpop(self, key):
        values = self.lists.setdefault(key, [])
        return values.pop() if values else None

    async def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)

    async def delete(self, key):
        self.deleted.append(key)


@pytest.mark.asyncio
async def test_worker_requeues_unacknowledged_jobs_and_clears_stale_locks():
    redis = FakeRedis({
        "assistant:processing": [
            '{"id":"job-2","type":"refresh_oauth_token"}',
            '{"id":"job-1","type":"refresh_oauth_token"}',
        ],
        "assistant:retry": [
            '{"id":"retry-1","type":"refresh_oauth_token"}',
            '{"id":"retry-2","type":"refresh_oauth_token"}',
        ],
    })

    recovered = await recover_processing_jobs(redis)

    assert recovered == 4
    assert redis.lists["assistant:processing"] == []
    assert len(redis.lists["assistant:jobs"]) == 4
    assert "assistant:processing:job-1" in redis.deleted
    assert "assistant:processing:job-2" in redis.deleted
    # BRPOPLPUSH consumes the right side; the oldest legacy retry is first.
    assert redis.lists["assistant:jobs"][-1].find("retry-1") >= 0
