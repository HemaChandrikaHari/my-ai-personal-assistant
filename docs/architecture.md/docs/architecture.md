# Architecture
FastAPI is the single source of truth. The Next.js dashboard and ChatGPT-facing MCP server both call it. The supervisor plans tasks; an integration registry discovers provider capabilities; an approval manager gates every tool invocation; adapters connect to APIs and remote MCP servers; workers execute scheduled and event-driven jobs.

Lifecycle: discover → propose → user approves app → authenticate → inspect capabilities → user approves exact scopes → enable. Discovery never grants access. Read, write and send are distinct permissions.

Incoming email, WhatsApp messages, documents and tool outputs are untrusted data. They cannot change system policy or approve their own actions.
