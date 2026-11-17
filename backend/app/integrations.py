from dataclasses import dataclass, field
from app.config import settings

@dataclass
class Integration:
    id: str
    name: str
    kind: str
    endpoint: str | None = None
    connected: bool = False
    approval_required: bool = True
    capabilities: list[dict] = field(default_factory=list)

class IntegrationRegistry:
    def __init__(self): self._items: dict[str, Integration] = {}
    def register(self, item: Integration): self._items[item.id] = item
    def list(self): return list(self._items.values())

registry = IntegrationRegistry()

def register_existing_integrations():
    # Preserve existing Blueticks endpoint. Credentials are supplied at runtime from Secrets Manager.
    if settings.blueticks_mcp_url:
        registry.register(Integration(id="blueticks_whatsapp", name="WhatsApp (Blueticks MCP)", kind="remote_mcp", endpoint=settings.blueticks_mcp_url, connected=False, approval_required=True))
