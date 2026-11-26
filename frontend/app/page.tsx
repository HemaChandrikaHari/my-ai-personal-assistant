"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const USER = process.env.NEXT_PUBLIC_ENABLE_DEV_AUTH === "true"
  ? (process.env.NEXT_PUBLIC_DEV_USER || "local-developer") : "";

type Integration = {
  id: string; name: string; discovered: boolean; connected: boolean;
  capabilities: { name: string; description: string }[]; approved_scopes: string[];
};
type Approval = { id: number; integration_id: string; scope: string; status: string };
type Connection = { provider: string; connected: boolean; scopes: string[] };

export default function Home() {
  const [items, setItems] = useState<Integration[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [providerData, setProviderData] = useState("");
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");
  const [token, setToken] = useState("");
  const [status, setStatus] = useState("Checking API…");

  const headers = () => ({
    "Content-Type": "application/json",
    ...(token ? { Authorization: "Bearer " + token } :
      USER ? { "X-User-ID": USER } : {}),
  });

  async function refresh() {
    try {
      const health = await fetch(API + "/health");
      setStatus(health.ok ? "API online" : "API unavailable");
      const [integrationsResponse, approvalsResponse, connectionsResponse] = await Promise.all([
        fetch(API + "/api/v1/integrations", { headers: headers(), cache: "no-store" }),
        fetch(API + "/api/v1/approval-requests", { headers: headers(), cache: "no-store" }),
        fetch(API + "/api/v1/connections", { headers: headers(), cache: "no-store" }),
      ]);
      if (integrationsResponse.ok) setItems(await integrationsResponse.json());
      if (approvalsResponse.ok) setApprovals(await approvalsResponse.json());
      if (connectionsResponse.ok) setConnections(await connectionsResponse.json());
    } catch {
      setStatus("API offline — start the backend");
    }
  }

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    const connected = query.get("connected");
    const oauthError = query.get("oauth_error");
    if (connected) setAnswer(connected + " account connected successfully.");
    if (oauthError) setAnswer(connected + " connection was not completed.");
    void refresh();
  }, []);

  async function connect(provider: string) {
    setBusy(provider);
    try {
      const response = await fetch(API + "/api/v1/oauth/" + provider + "/start", {
        headers: headers(), cache: "no-store",
      });
      const data = await response.json();
      if (!response.ok) {
        setAnswer(data.detail || "Could not start OAuth");
        return;
      }
      window.location.assign(data.authorization_url);
    } catch {
      setAnswer("Could not reach the backend");
    } finally {
      setBusy("");
    }
  }

  async function disconnect(provider: string) {
    setBusy(provider);
    try {
      const response = await fetch(API + "/api/v1/connections/" + provider, {
        method: "DELETE", headers: headers(),
      });
      const data = await response.json();
      setAnswer(response.ok ? provider + " disconnected locally." :
        data.detail || "Disconnect failed");
      await refresh();
    } catch {
      setAnswer("Could not reach the backend");
    } finally {
      setBusy("");
    }
  }

  async function loadProviderData(path: string) {
    setBusy(path);
    setProviderData("");
    try {
      const response = await fetch(API + path, { headers: headers(), cache: "no-store" });
      const data = await response.json();
      setProviderData(response.ok ? JSON.stringify(data, null, 2) :
        (data.detail || "Request failed"));
    } catch {
      setProviderData("Could not reach the backend");
    } finally {
      setBusy("");
    }
  }

  async function discover() {
    const response = await fetch(API + "/api/v1/integrations/blueticks/discover", {
      method: "POST", headers: headers(),
    });
    const data = await response.json();
    setAnswer(response.ok
      ? "Discovered " + (data.tools?.length || 0) + " Blueticks tools. Request scopes before using them."
      : data.detail || "Discovery failed");
    await refresh();
  }

  async function request(scope: string) {
    const response = await fetch(API + "/api/v1/approval-requests", {
      method: "POST", headers: headers(),
      body: JSON.stringify({ integration_id: "blueticks_whatsapp", scope }),
    });
    const data = await response.json();
    setAnswer(response.ok ? "Approval request created for " + scope + "." :
      data.detail || "Request failed");
    await refresh();
  }

  async function decide(id: number, decision: string) {
    const response = await fetch(API + "/api/v1/approval-requests/" + id + "/decide", {
      method: "POST", headers: headers(), body: JSON.stringify({ decision }),
    });
    const data = await response.json();
    setAnswer(response.ok ? "Request " + decision + "d." : data.detail || "Decision failed");
    await refresh();
  }

  async function chat() {
    const response = await fetch(API + "/api/v1/chat", {
      method: "POST", headers: headers(), body: JSON.stringify({ message }),
    });
    const data = await response.json();
    setAnswer(response.ok ? data.answer : data.detail || "Chat failed");
  }

  return <main>
    <header>
      <span className="eyebrow">PERSONAL AI WORKSPACE</span>
      <h1>My AI Personal Assistant</h1>
      <p>One assistant, shared permissions, and integrations you control.</p>
      <span className="status">{status}</span>
    </header>

    <section className="panel">
      <h2>Authentication</h2>
      <p>For deployed environments, paste a short-lived JWT issued by your identity provider. Local development uses a development-only identity.</p>
      <input type="password" placeholder="Bearer JWT (leave blank for local dev)"
        value={token} onChange={event => setToken(event.target.value)} />
      <button className="secondary" onClick={() => void refresh()}>Refresh connections</button>
    </section>

    <section className="panel">
      <h2>Assistant</h2>
      <textarea placeholder="Ask your assistant…" value={message}
        onChange={event => setMessage(event.target.value)} />
      <button onClick={chat} disabled={!message.trim()}>Send message</button>
      {answer && <p className="answer">{answer}</p>}
    </section>

    <section className="panel">
      <h2>Connected accounts</h2>
      <p>Connect your accounts using OAuth. Provider tokens are encrypted by the backend. Configure the provider credentials in the server environment first.</p>
      {(["google", "todoist"] as const).map(provider => {
        const item = connections.find(connection => connection.provider === provider);
        return <article className="integration" key={provider}>
          <div>
            <b>{provider === "google" ? "Google · Gmail + Calendar" : "Todoist"}</b>
            <p>{item?.connected ? "Connected · " + item.scopes.join(", ") : "Not connected"}</p>
          </div>
          <div className="scopes">
            {item?.connected
              ? <button className="secondary" disabled={!!busy} onClick={() => disconnect(provider)}>Disconnect</button>
              : <button disabled={!!busy} onClick={() => connect(provider)}>
                  Connect {provider === "google" ? "Google" : "Todoist"}
                </button>}
          </div>
        </article>;
      })}
      <div className="scopes">
        <button className="secondary" disabled={!connections.find(x => x.provider === "google")?.connected || !!busy}
          onClick={() => loadProviderData("/api/v1/google/gmail/messages")}>Load recent Gmail</button>
        <button className="secondary" disabled={!connections.find(x => x.provider === "google")?.connected || !!busy}
          onClick={() => loadProviderData("/api/v1/google/calendar/events")}>Load Calendar events</button>
        <button className="secondary" disabled={!connections.find(x => x.provider === "todoist")?.connected || !!busy}
          onClick={() => loadProviderData("/api/v1/todoist/tasks")}>Load Todoist tasks</button>
      </div>
      {providerData && <pre className="answer" style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{providerData}</pre>}
    </section>

    <section className="panel">
      <h2>WhatsApp · Blueticks MCP</h2>
      {items.map(item => <article className="integration" key={item.id}>
        <div><b>{item.name}</b><p>{item.connected ? "Approved connection" : "Not connected"} · {item.capabilities.length} discovered tools · Approved scopes: {item.approved_scopes.join(", ") || "none"}</p></div>
      </article>)}
      <button onClick={discover}>Discover Blueticks tools</button>
      <div className="scopes">
        {["read", "write", "send"].map(scope =>
          <button className="secondary" key={scope} onClick={() => request(scope)}>Request {scope} access</button>)}
      </div>
    </section>

    <section className="panel">
      <h2>Approval requests</h2>
      {approvals.length === 0 && <p>No requests yet.</p>}
      {approvals.map(item => <article className="integration" key={item.id}>
        <span>{item.integration_id} · {item.scope} · {item.status}</span>
        {item.status === "pending" && <div className="scopes">
          <button onClick={() => decide(item.id, "approve")}>Approve</button>
          <button className="secondary" onClick={() => decide(item.id, "reject")}>Reject</button>
        </div>}
      </article>)}
    </section>
    <footer>External actions require an explicit user action. Never paste long-lived secrets here.</footer>
  </main>;
}
