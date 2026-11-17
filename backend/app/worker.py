"""Minimal Redis queue worker. Jobs must be idempotent; retries are bounded."""
import asyncio
import json
import os
import time
import logging
import redis.asyncio as redis

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("assistant.worker")

async def main():
    client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
    while True:
        item = await client.blpop("assistant:jobs", timeout=5)
        if not item:
            continue
        _, raw = item
        job = json.loads(raw)
        job_id = str(job.get("id", ""))
        if not job_id:
            log.warning("Discarding job without id")
            continue
        lock = await client.set("assistant:done:" + job_id, "1", nx=True, ex=86400)
        if not lock:
            continue
        try:
            log.info("Accepted job %s type=%s", job_id, job.get("type"))
            # Register concrete task handlers here. Do not execute arbitrary code from queue payloads.
        except Exception:
            await client.delete("assistant:done:" + job_id)
            log.exception("Job %s failed", job_id)
            await client.rpush("assistant:retry", raw)
        await asyncio.sleep(0.05)

if __name__ == "__main__":
    asyncio.run(main())
