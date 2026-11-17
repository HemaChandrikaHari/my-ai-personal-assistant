"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const USER = process.env.NEXT_PUBLIC_ENABLE_DEV_AUTH === "true" ? (process.env.NEXT_PUBLIC_DEV_USER || "local-developer") : "";

type Integration = { id: string; name: string; discovered: boolean; connected: boolean; capabilities: {name:string;description:string}[]; approved_scopes:string[] };
type Approval = { id:number; integration_id:string; scope:string; status:string };

export default function Home() {
  const [items,setItems] = useState<Integration[]>([]);
  const [approvals,setApprovals] = useState<Approval[]>([]);
  const [message,setMessage] = useState("");
  const [answer,setAnswer] = useState("");
  const [token,setToken] = useState("");
  const [status,setStatus] = useState("Checking API…");
  const headers = () => ({ "Content-Type":"application/json", ...(token ? {Authorization:"Bearer "+token} : USER ? {"X-User-ID":USER} : {}) });
  async function refresh() {
    try {
      const h = await fetch(API+"/health");
      setStatus(h.ok ? "API online" : "API unavailable");
      const [i,a] = await Promise.all([
        fetch(API+"/api/v1/integrations",{headers:headers(),cache:"no-store"}),
        fetch(API+"/api/v1/approval-requests",{headers:headers(),cache:"no-store"})
      ]);
      if(i.ok) setItems(await i.json());
      if(a.ok) setApprovals(await a.json());
    } catch { setStatus("API offline — start the backend"); }
  }
  useEffect(()=>{ void refresh(); },[]);
  async function discover() {
    const r=await fetch(API+"/api/v1/integrations/blueticks/discover",{method:"POST",headers:headers()});
    const data=await r.json(); setAnswer(r.ok ? "Discovered "+(data.tools?.length||0)+" Blueticks tools. Request scopes below before using them." : data.detail||"Discovery failed"); await refresh();
  }
  async function request(scope:string) {
    const r=await fetch(API+"/api/v1/approval-requests",{method:"POST",headers:headers(),body:JSON.stringify({integration_id:"blueticks_whatsapp",scope})});
    const data=await r.json(); setAnswer(r.ok ? "Approval request created for "+scope+"." : data.detail||"Request failed"); await refresh();
  }
  async function decide(id:number,decision:string) {
    const r=await fetch(API+"/api/v1/approval-requests/"+id+"/decide",{method:"POST",headers:headers(),body:JSON.stringify({decision})});
    const data=await r.json(); setAnswer(r.ok ? "Request "+decision+"d." : data.detail||"Decision failed"); await refresh();
  }
  async function chat() {
    const r=await fetch(API+"/api/v1/chat",{method:"POST",headers:headers(),body:JSON.stringify({message})});
    const data=await r.json(); setAnswer(r.ok ? data.answer : data.detail||"Chat failed");
  }
  return <main>
    <header><span className="eyebrow">PERSONAL AI WORKSPACE</span><h1>My AI Personal Assistant</h1><p>One assistant, shared permissions, and integrations you control.</p><span className="status">{status}</span></header>
    <section className="panel"><h2>Authentication</h2><p>For deployed environments, paste a short-lived JWT issued by your identity provider. Local development uses a development-only identity.</p><input type="password" placeholder="Bearer JWT (leave blank for local dev)" value={token} onChange={e=>setToken(e.target.value)} /></section>
    <section className="panel"><h2>Assistant</h2><textarea placeholder="Ask your assistant…" value={message} onChange={e=>setMessage(e.target.value)} /><button onClick={chat} disabled={!message.trim()}>Send message</button>{answer && <p className="answer">{answer}</p>}</section>
    <section className="panel"><h2>Integrations</h2>{items.map(x=><article className="integration" key={x.id}><div><b>{x.name}</b><p>{x.connected?"Approved connection":"Not connected"} · {x.capabilities.length} discovered tools · Approved scopes: {x.approved_scopes.join(", ")||"none"}</p></div></article>)}<button onClick={discover}>Discover Blueticks tools</button><div className="scopes">{["read","write","send"].map(s=><button className="secondary" key={s} onClick={()=>request(s)}>Request {s} access</button>)}</div></section>
    <section className="panel"><h2>Approval requests</h2>{approvals.length===0 && <p>No requests yet.</p>}{approvals.map(a=><article className="integration" key={a.id}><span>{a.integration_id} · {a.scope} · {a.status}</span>{a.status==="pending" && <div className="scopes"><button onClick={()=>decide(a.id,"approve")}>Approve</button><button className="secondary" onClick={()=>decide(a.id,"reject")}>Reject</button></div>}</article>)}</section>
    <footer>Prototype foundation · External actions require server-side scope approval · Do not paste long-lived secrets here.</footer>
  </main>;
}
