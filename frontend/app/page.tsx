async function integrations() {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  try { const r = await fetch(base + "/api/v1/integrations", {headers:{"x-user-id":"local-developer"},cache:"no-store"}); return r.ok ? await r.json() : []; }
  catch { return []; }
}
export default async function Home() {
  const items = await integrations();
  return &lt;main&gt;&lt;span className="pill"&gt;PERSONAL AI WORKSPACE&lt;/span&gt;&lt;h1&gt;My AI Personal Assistant&lt;/h1&gt;&lt;p className="muted"&gt;One assistant, shared permissions, and integrations you control.&lt;/p&gt;
    &lt;section className="grid"&gt;&lt;div className="panel"&gt;&lt;h2&gt;Assistant&lt;/h2&gt;&lt;p className="muted"&gt;FastAPI orchestration gateway.&lt;/p&gt;&lt;/div&gt;&lt;div className="panel"&gt;&lt;h2&gt;Approvals&lt;/h2&gt;&lt;p className="muted"&gt;Each app and read/write/send scope requires explicit approval.&lt;/p&gt;&lt;/div&gt;&lt;div className="panel"&gt;&lt;h2&gt;Workflows&lt;/h2&gt;&lt;p className="muted"&gt;Worker and scheduler modules are planned next.&lt;/p&gt;&lt;/div&gt;&lt;/section&gt;
    &lt;section className="panel"&gt;&lt;h2&gt;Integrations&lt;/h2&gt;{items.length ? items.map((x:any)=&gt;&lt;p key={x.id}&gt;&lt;b&gt;{x.name}&lt;/b&gt; — {x.connected?"Connected":"Setup required"} · {x.approval_required?"Approval required":"Approved"}&lt;/p&gt;) : &lt;p className="muted"&gt;Start the backend to load registered integrations.&lt;/p&gt;}&lt;/section&gt;
    &lt;p className="muted"&gt;Starter scaffold: configure production identity, persistence and secret management before use.&lt;/p&gt;&lt;/main&gt;;
}
