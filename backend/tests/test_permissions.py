from fastapi.testclient import TestClient
from uuid import uuid4
from app.main import app, READ_TOOLS, SEND_TOOLS

def test_read_and_send_allowlists_are_separate():
    assert READ_TOOLS.isdisjoint(SEND_TOOLS)

def test_approval_is_per_user_and_per_scope():
    headers = {"X-User-ID": "pytest-" + uuid4().hex}
    with TestClient(app) as client:
        created = client.post("/api/v1/approval-requests",
                              headers=headers,
                              json={"integration_id": "blueticks_whatsapp", "scope": "read"})
        assert created.status_code == 200
        request_id = created.json()["id"]
        decided = client.post(f"/api/v1/approval-requests/{request_id}/decide",
                              headers=headers, json={"decision": "approve"})
        assert decided.status_code == 200
        integrations = client.get("/api/v1/integrations", headers=headers)
        assert integrations.status_code == 200
        item = next(x for x in integrations.json() if x["id"] == "blueticks_whatsapp")
        assert "read" in item["approved_scopes"]
        assert "send" not in item["approved_scopes"]

def test_user_cannot_decide_another_users_request():
    with TestClient(app) as client:
        owner = {"X-User-ID": "approval-owner-" + uuid4().hex}
        stranger = {"X-User-ID": "different-user-" + uuid4().hex}
        created = client.post("/api/v1/approval-requests", headers=owner,
                              json={"integration_id": "blueticks_whatsapp", "scope": "send"})
        assert created.status_code == 200
        denied = client.post(f"/api/v1/approval-requests/{created.json()['id']}/decide",
                             headers=stranger, json={"decision": "approve"})
        assert denied.status_code == 404
