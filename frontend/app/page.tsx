"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const COGNITO_DOMAIN = process.env.NEXT_PUBLIC_COGNITO_DOMAIN || "";
const COGNITO_CLIENT_ID = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID || "";
const REDIRECT_URI = process.env.NEXT_PUBLIC_COGNITO_REDIRECT_URI || (typeof window !== "undefined" ? window.location.origin : "");
const DEV_AUTH = process.env.NEXT_PUBLIC_ENABLE_DEV_AUTH === "true";
const DEV_USER = process.env.NEXT_PUBLIC_DEV_USER || "local-developer";
const TOKEN_KEY = "assistant_id_token";
const REFRESH_KEY = "assistant_refresh_token";

type Integration = { id: string; name: string; discovered: boolean; connected: boolean; capabilities: {name:string;description:string}[]; approved_scopes:string[] };
type Approval = { id:string|number; integration_id:string; scope:string; status:string };

function base64url(bytes: Uint8Array) {
  let binary = "";
  bytes.forEach((b) => binary += String.fromCharCode(b));
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}
async function pkcePair() {
  const verifier = base64url(crypto.getRandomValues(new Uint8Array(32)));
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return { verifier, challenge: base64url(new Uint8Array(digest)) };
}
function jwtExpiry(token:string):number {
  try { return Number(JSON.parse(atob(token.split(".")[1].replace(/-/g,"+").replace(/_/g,"/"))).exp||0); }
  catch { return 0; }
}

export default function Home() {
  const [items,setItems] = useState<Integration[]>([]);
  const [approvals,setApprovals] = useState<Approval[]>([]);
  const [message,setMessage] = useState("");
  const [answer,setAnswer] = useState("");
  const [token,setToken] = useState("");
  const [status,setStatus] = useState("Checking API…");
  const [authStatus,setAuthStatus] = useState("Not signed in");
  const [busy,setBusy] = useState(false);
  const [devMode,setDevMode] = useState(false);

  useEffect(() => {
    const existing = sessionStorage.getItem(TOKEN_KEY) || "";
    if (existing) { setToken(existing); setAuthStatus("Signed in"); }
    else if (DEV_AUTH) { setDevMode(true); setAuthStatus("Local development identity"); }
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const returnedState = params.get("state");
    if (code) {
      const expectedState = sessionStorage.getItem("assistant_oauth_state");
      const verifier = sessionStorage.getItem("assistant_pkce_verifier");
      sessionStorage.removeItem("assistant_oauth_state");
      sessionStorage.removeItem("assistant_pkce_verifier");
      if (!expectedState || returnedState !== expectedState || !verifier || !COGNITO_DOMAIN || !COGNITO_CLIENT_ID) {
        setAuthStatus("Sign-in verification failed");
        window.history.replaceState({}, "", window.location.pathname);
        return;
      }
      setBusy(true);
      const form = new URLSearchParams({ grant_type:"authorization_code", client_id:COGNITO_CLIENT_ID, code, redirect_uri:REDIRECT_URI, code_verifier:verifier });
      void fetch(COGNITO_DOMAIN.replace(/\/$/,"")+"/oauth2/token", {
        method:"POST", headers:{"Content-Type":"application/x-www-form-urlencoded"}, body:form.toString()
      }).then(async response => {
        const data = await response.json();
        if (!response.ok || !data.id_token) throw new Error(data.error_description || "Token exchange failed");
        sessionStorage.setItem(TOKEN_KEY, data.id_token);
        if (data.refresh_token) sessionStorage.setItem(REFRESH_KEY, data.refresh_token);
        setToken(data.id_token); setAuthStatus("Signed in");
      }).catch(() => setAuthStatus("Sign-in failed; please try again"))
        .finally(() => { setBusy(false); window.history.replaceState({}, "", window.location.pathname); });
    }
  }, []);

  async function signIn() {
    if (!COGNITO_DOMAIN || !COGNITO_CLIENT_ID) {
      setAuthStatus("Cognito Hosted UI is not configured in environment variables");
      return;
    }
    const {verifier, challenge} = await pkcePair();
    const state = base64url(crypto.getRandomValues(new Uint8Array(24)));
    sessionStorage.setItem("assistant_pkce_verifier", verifier);
    sessionStorage.setItem("assistant_oauth_state", state);
    const url = new URL(COGNITO_DOMAIN.replace(/\/$/,"")+"/oauth2/authorize");
    url.search = new URLSearchParams({
      response_type:"code", client_id:COGNITO_CLIENT_ID, redirect_uri:REDIRECT_URI,
      scope:"openid email profile", code_challenge_method:"S256", code_challenge:challenge, state
    }).toString();
    window.location.assign(url.toString());
  }

  async function signOut() {
    sessionStorage.removeItem(TOKEN_KEY); sessionStorage.removeItem(REFRESH_KEY);
    setToken(""); setDevMode(false); setItems([]); setApprovals([]); setAuthStatus("Not signed in");
    if (COGNITO_DOMAIN && COGNITO_CLIENT_ID) {
      const url = new URL(COGNITO_DOMAIN.replace(/\/$/,"")+"/logout");
      url.search = new URLSearchParams({client_id:COGNITO_CLIENT_ID,logout_uri:REDIRECT_URI}).toString();
      window.location.assign(url.toString());
    }
  }

  async function authHeaders(): Promise<Record<string, string>> {
    let current = sessionStorage.getItem(TOKEN_KEY) || token;
    if (!current && DEV_AUTH && devMode) return {"Content-Type":"application/json","X-User-ID":DEV_USER};
    const refreshToken = sessionStorage.getItem(REFRESH_KEY);
    if (current && refreshToken && jwtExpiry(current) < Math.floor(Date.now()/1000)+120 &&
        COGNITO_DOMAIN && COGNITO_CLIENT_ID) {
      const form = new URLSearchParams({grant_type:"refresh_token",client_id:COGNITO_CLIENT_ID,refresh_token:refreshToken});
      const response = await fetch(COGNITO_DOMAIN.replace(/\/$/,"")+"/oauth2/token",{
        method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:form.toString()
      });
      const data = await response.json();
      if (!response.ok || !data.id_token) {
        sessionStorage.removeItem(TOKEN_KEY); sessionStorage.removeItem(REFRESH_KEY);
        setToken(""); setAuthStatus("Session expired; sign in again");
        throw new Error("Session expired; please sign in again");
      }
      current = data.id_token;
      sessionStorage.setItem(TOKEN_KEY,current);
      setToken(current);
    }
    if (!current) throw new Error("Please sign in first");
    return {"Content-Type":"application/json",Authorization:"Bearer "+current};
  }

  async function refresh() {
    if (!token && !devMode) { setStatus("Sign in to load your private workspace"); return; }
    try {
      const h = await fetch(API+"/health");
      setStatus(h.ok ? "API online" : "API unavailable");
      const auth = await authHeaders();
      const [i,a] = await Promise.all([
        fetch(API+"/api/v1/integrations",{headers:auth,cache:"no-store"}),
        fetch(API+"/api/v1/approval-requests",{headers:auth,cache:"no-store"})
      ]);
      if(i.status===401 || a.status===401) { setAuthStatus("Session expired; sign in again"); return; }
      if(i.ok) setItems(await i.json());
      if(a.ok) setApprovals(await a.json());
    } catch(e) { setStatus(e instanceof Error ? e.message : "API offline"); }
  }
  useEffect(()=>{ if(token || devMode) void refresh(); },[token,devMode]);

  async function apiAction(path:string, method="POST", body?:unknown) {
    const auth = await authHeaders();
    const r=await fetch(API+path,{method,headers:auth,...(body===undefined?{}:{body:JSON.stringify(body)})});
    const data=await r.json();
    if(!r.ok) throw new Error(data.detail||"Request failed");
    return data;
  }
  async function discover() {
    try { const data=await apiAction("/api/v1/integrations/blueticks/discover"); setAnswer("Discovered "+(data.tools?.length||0)+" Blueticks tools. Request scopes below before using them."); await refresh(); }
    catch(e) { setAnswer(e instanceof Error?e.message:"Discovery failed"); }
  }
  async function request(scope:string) {
    try { await apiAction("/api/v1/approval-requests","POST",{integration_id:"blueticks_whatsapp",scope}); setAnswer("Approval request created for "+scope+"."); await refresh(); }
    catch(e) { setAnswer(e instanceof Error?e.message:"Request failed"); }
  }
  async function decide(id:string|number,decision:string) {
    try { await apiAction("/api/v1/approval-requests/"+id+"/decide","POST",{decision}); setAnswer("Request "+decision+"d."); await refresh(); }
    catch(e) { setAnswer(e instanceof Error?e.message:"Request failed"); }
  }
  async function chat() {
    try { const data=await apiAction("/api/v1/chat","POST",{message}); setAnswer(data.answer); }
    catch(e) { setAnswer(e instanceof Error?e.message:"Chat failed"); }
  }

  return <main>
    <header><span className="eyebrow">PERSONAL AI WORKSPACE</span><h1>My AI Personal Assistant</h1><p>One assistant, shared permissions, and integrations you control.</p><span className="status">{status}</span></header>
    <section className="panel"><h2>Account</h2><p>{authStatus}</p>{token || devMode ? <button className="secondary" onClick={signOut}>Sign out</button> : DEV_AUTH ? <button onClick={()=>{setDevMode(true);setAuthStatus("Local development identity");}}>Continue with local development identity</button> : <button onClick={signIn} disabled={busy}>Sign in securely with Amazon Cognito</button>}</section>
    {(token || devMode) && <>
      <section className="panel"><h2>Assistant</h2><textarea placeholder="Ask your assistant…" value={message} onChange={e=>setMessage(e.target.value)} /><button onClick={chat} disabled={!message.trim()}>Send message</button>{answer && <p className="answer">{answer}</p>}</section>
      <section className="panel"><h2>Integrations</h2>{items.map(x=><article className="integration" key={x.id}><div><b>{x.name}</b><p>{x.connected?"Approved connection":"Not connected"} · {x.capabilities.length} discovered tools · Approved scopes: {x.approved_scopes.join(", ")||"none"}</p></div></article>)}<button onClick={discover}>Discover Blueticks tools</button><div className="scopes">{["read","write","send"].map(s=><button className="secondary" key={s} onClick={()=>request(s)}>Request {s} access</button>)}</div></section>
      <section className="panel"><h2>Approval requests</h2>{approvals.length===0 && <p>No requests yet.</p>}{approvals.map(a=><article className="integration" key={a.id}><span>{a.integration_id} · {a.scope} · {a.status}</span>{a.status==="pending" && <div className="scopes"><button onClick={()=>decide(a.id,"approve")}>Approve</button><button className="secondary" onClick={()=>decide(a.id,"reject")}>Reject</button></div>}</article>)}</section>
    </>}
    <footer>External actions require server-side scope approval. AI model calls and integrations remain disabled until explicitly configured.</footer>
  </main>;
}
