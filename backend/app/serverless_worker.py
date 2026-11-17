"""SQS worker. It validates message shape and never executes arbitrary payloads."""
import json
import logging
import os

log = logging.getLogger()
log.setLevel(os.getenv("LOG_LEVEL", "INFO"))
ALLOWED_TYPES = {"integration_sync", "notification"}

def handler(event, context):
    failures = []
    for record in event.get("Records", []):
        message_id = record.get("messageId", "unknown")
        try:
            body = json.loads(record.get("body", "{}"))
            if not isinstance(body, dict) or not body.get("id") or body.get("type") not in ALLOWED_TYPES:
                raise ValueError("Unsupported task message")
            # Concrete task handlers are intentionally disabled until each action
            # has an explicit implementation, idempotency key, and scope check.
            log.info("Validated task id=%s type=%s; no external action executed",
                     body["id"], body["type"])
        except Exception:
            log.exception("Rejecting invalid task message id=%s", message_id)
            failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}
