from enum import StrEnum

class Scope(StrEnum):
    READ = "read"
    WRITE = "write"
    SEND = "send"

class PermissionManager:
    """Deny-by-default; read, write and send are independent grants."""
    def __init__(self):
        self._grants: dict[tuple[str, str], frozenset[Scope]] = {}
    def grant(self, user_id: str, integration_id: str, scopes: set[Scope]):
        self._grants[(user_id, integration_id)] = frozenset(scopes)
    def revoke(self, user_id: str, integration_id: str):
        self._grants.pop((user_id, integration_id), None)
    def allowed(self, user_id: str, integration_id: str, scope: Scope) -> bool:
        return scope in self._grants.get((user_id, integration_id), frozenset())
