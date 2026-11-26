"""Redis worker for bounded, allowlisted maintenance jobs."""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone

import redis.asyncio as redis
from sqlalchemy import delete
from app.config import settings
from app.db import SessionLocal, OAuthState
from app.oauth_integrations import _access_token

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("assistant.worker")
MAX_ATTEMPTS = 3


async def handle_job(job: dict):
    job_type = job.get("type")
    if job_type == "cleanup_oauth_states":
        async with SessionLocal() as db:
            result = await db.execute(
                delete(OAuthState).where(OAuthState.expires_at < datetime.now(timezone.utc))
            )
            await db.commit()
            return {"deleted": result.rowcount or 0}

    if job_type == "refresh_oauth_token":
        user_id = job.get("user_id")
        provider = job.get("provider")
        if not isinstance(user_id, str) or not user_id or provider not in {"google", "todoist"}:
            raise ValueError("Invalid OAuth refresh job")
        async with SessionLocal() as db:
            await _access_token(db, user_id, provider)
        return {"refreshed": provider}

    raise ValueError("Unsupported job type")


async def recover_processing_jobs(client):
    """Requeue unacknowledged jobs left behind by a crashed worker."""
    recovered = 0
    # Migrate jobs left in the legacy retry list before recovering in-flight work.
    while True:
        raw = await client.rpop("assistant:retry")
        if raw is None:
            break
        await client.lpush("assistant:jobs", raw)
        recovered += 1
    # One worker replica is expected. A process restart means the old worker is gone,
    # so its in-flight locks can safely be cleared before the jobs are retried.
    while True:
        raw = await client.rpop("assistant:processing")
        if raw is None:
            break
        try:
            job = json.loads(raw)
            job_id = str(job.get("id", "")) if isinstance(job, dict) else ""
            if job_id:
                await client.delete("assistant:processing:" + job_id)
        except Exception:
            pass
        await client.lpush("assistant:jobs", raw)
        recovered += 1
    return recovered


async def run():
    client = redis.from_url(settings.redis_url, decode_responses=True)
    next_cleanup = 0.0
    try:
        recovered = await recover_processing_jobs(client)
        if recovered:
            log.warning("Recovered %s unacknowledged job(s) after worker restart", recovered)
        while True:
            if time.monotonic() >= next_cleanup:
                try:
                    await handle_job({"type": "cleanup_oauth_states"})
                except Exception:
                    log.exception("OAuth state cleanup failed")
                next_cleanup = time.monotonic() + 300

            # BRPOPLPUSH atomically moves a job into the processing list. If this
            # process dies before acknowledging it, the next worker startup recovers it.
            raw = await client.brpoplpush("assistant:jobs", "assistant:processing", timeout=5)
            if raw is None:
                continue
            try:
                job = json.loads(raw)
                if not isinstance(job, dict):
                    raise ValueError("Job payload must be an object")
                job_id = str(job.get("id", ""))
                if not job_id or len(job_id) > 128:
                    raise ValueError("Job id is missing or invalid")
            except Exception:
                log.exception("Discarding malformed job payload")
                await client.rpush("assistant:dead", raw)
                await client.lrem("assistant:processing", 1, raw)
                continue

            if await client.exists("assistant:done:" + job_id):
                await client.lrem("assistant:processing", 1, raw)
                continue
            lock_key = "assistant:processing:" + job_id
            locked = await client.set(lock_key, "1", nx=True, ex=300)
            if not locked:
                # Another worker owns this id; don't leave a duplicate in-flight copy.
                await client.lrem("assistant:processing", 1, raw)
                continue

            try:
                result = await handle_job(job)
                await client.set("assistant:done:" + job_id, "1", ex=86400)
                log.info("Completed job %s type=%s result=%s", job_id, job.get("type"), result)
            except Exception:
                attempts = int(job.get("attempts", 0)) + 1
                job["attempts"] = attempts
                log.exception("Job %s failed on attempt %s", job_id, attempts)
                if attempts < MAX_ATTEMPTS:
                    await asyncio.sleep(min(2 ** attempts, 30))
                    await client.rpush("assistant:jobs", json.dumps(job))
                else:
                    await client.rpush("assistant:dead", json.dumps(job))
            finally:
                await client.lrem("assistant:processing", 1, raw)
                await client.delete(lock_key)
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(run())
