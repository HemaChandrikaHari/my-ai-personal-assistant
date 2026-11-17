from app.permissions import PermissionManager, Scope

def test_read_does_not_imply_send():
    manager = PermissionManager()
    manager.grant("u1", "whatsapp", {Scope.READ})
    assert manager.allowed("u1", "whatsapp", Scope.READ)
    assert not manager.allowed("u1", "whatsapp", Scope.SEND)
