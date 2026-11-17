from app.serverless_worker import handler


def test_worker_rejects_unknown_task_type_for_retry_or_dlq():
    result = handler({"Records": [{
        "messageId": "msg-1",
        "body": '{"id":"job-1","type":"arbitrary_code","userId":"user-1"}'
    }]}, None)
    assert result == {"batchItemFailures": [{"itemIdentifier": "msg-1"}]}


def test_worker_rejects_invalid_json():
    result = handler({"Records": [{"messageId": "msg-2", "body": "not-json"}]}, None)
    assert result == {"batchItemFailures": [{"itemIdentifier": "msg-2"}]}


def test_worker_acknowledges_valid_but_not_yet_executed_task():
    result = handler({"Records": [{
        "messageId": "msg-3",
        "body": '{"id":"job-2","type":"notification","userId":"user-1","payload":{}}'
    }]}, None)
    assert result == {"batchItemFailures": []}
