"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { CopilotKit } from "@copilotkit/react-core";
import { CopilotChat } from "@copilotkit/react-ui";

type User = {id: string; email: string; role: string; model_mode?: string};
type Service = {id: string; kind: string; label: string; plan: string; status: string; discount_code: string | null};
type Thread = {id: string; service_id: string};
type Approval = {id: string; issue: string; status: string; parameters: string};
type Message = {id: string; role: string; content: string};
type Case = {id: string; issue: string; summary: string; status: string; resolution: string | null; evidence: string; service_id: string};
type CaseDetail = {case: Case; service: Service; messages: Message[]; actions: Approval[]; invoices: {total_cents: number; credit_cents: number; breakdown: string}[]};

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/backend/${path}`, {method: body === undefined ? "GET" : "POST",
    headers: {"Content-Type": "application/json"}, body: body === undefined ? undefined : JSON.stringify(body)});
  const raw = await response.text();
  let data: Record<string, unknown> = {};
  try { data = raw ? JSON.parse(raw) as Record<string, unknown> : {}; }
  catch {
    if (!response.ok) throw new Error("CareAgent could not process the request. Please try again.");
    throw new Error("CareAgent returned an invalid response.");
  }
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Request failed. Please try again.");
  return data as T;
}

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { api<User>("me").then(setUser).catch(() => {}).finally(() => setLoading(false)); }, []);
  return <div className="shell">
    <header><a className="brand" href="/"><span className="brand-mark">c</span> careagent<span className="brand-dot">.</span></a>
      <div className="header-right"><span className="pill">LOCAL DEMO</span>{user && <button className="quiet" onClick={async () => { await api("auth/logout", {}); setUser(null); }}>Sign out</button>}</div>
    </header>
    {loading ? <main className="loading">Connecting to your care workspace…</main> : user ?
      user.role === "operator" ? <Operator user={user}/> : <Customer user={user}/> : <Login onLogin={setUser}/>}
    <footer>Built for better connections.<span>Synthetic accounts · Simulated service actions</span></footer>
  </div>;
}

function Login({onLogin}: {onLogin: (user: User) => void}) {
  const [email, setEmail] = useState("alex@example.test");
  const [password, setPassword] = useState("CareDemo123!");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return <main className="login-layout"><section className="intro"><div className="eyebrow">A LITTLE LESS WAITING. A LOT MORE HELP.</div>
    <h1>Your connection.<br/><em>Our attention.</em></h1><p>From a question about your bill to getting a new line connected. Tell us what you need. We’ll take it from there.</p>
    <div className="feature-grid"><div><span>01</span><strong>Understand</strong><p>Support that starts with your account.</p></div><div><span>02</span><strong>Resolve</strong><p>The right specialist for every step.</p></div><div><span>03</span><strong>Stay in control</strong><p>You approve changes before they happen.</p></div></div>
    <div className="connection-art" aria-hidden="true"><div/><div/><div/><span>Connected care</span></div>
  </section><section className="login-card"><span className="eyebrow">YOUR CARE WORKSPACE</span><h2>Welcome back</h2><p>Sign in to manage your mobile and broadband services.</p>
    <form onSubmit={async e => {e.preventDefault(); setBusy(true); setError(""); try {onLogin(await api<User>("auth/login", {email, password}));} catch (e) {setError((e as Error).message);} finally {setBusy(false);} }}>
      <label>Email<input type="email" autoComplete="username" value={email} onChange={e => setEmail(e.target.value)} required/></label>
      <label>Password<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required/></label>
      {error && <p role="alert" className="error">{error}</p>}<button className="primary full" disabled={busy}>{busy ? "Signing in…" : "Enter workspace →"}</button>
    </form><div className="demo-note"><strong>Explore the demo</strong><p>Alex’s account is ready to use. All demo users use <code>CareDemo123!</code>.</p>
      <button className="link" onClick={() => setEmail("alex@example.test")}>Customer</button><button className="link" onClick={() => setEmail("jordan@example.test")}>Restricted account</button><button className="link" onClick={() => setEmail("operator@example.test")}>Operator</button></div>
  </section></main>;
}

function CareInput({threadId, busy, inProgress, onSend}: {threadId: string; busy: boolean; inProgress: boolean; onSend: (message: string) => Promise<void>}) {
  const [text, setText] = useState("");
  const send = async () => {
    const message = text.trim();
    if (!message || busy || inProgress) return;
    setText("");
    try { await onSend(message); } catch { setText(message); }
  };
  return <div className="copilotKitInput care-input"><textarea aria-label="Type a message..." placeholder="Type a message..." value={text} onChange={e => setText(e.target.value)} onKeyDown={e => {if (e.key === "Enter" && !e.shiftKey) {e.preventDefault(); void send();}}}/><button aria-label="Send" disabled={!text.trim() || busy || inProgress} onClick={() => void send()}>Send →</button></div>;
}

function Customer({user}: {user: User}) {
  const [services, setServices] = useState<Service[]>([]);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState("");
  const [threads, setThreads] = useState<Thread[]>([]);
  const [thread, setThread] = useState<Thread | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [history, setHistory] = useState<Message[]>([]);
  const [cases, setCases] = useState<Case[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const refreshing = useRef(false);
  const refresh = useCallback(async () => {
    if (refreshing.current) return;
    refreshing.current = true;
    try {
    const [account, cases, conversations] = await Promise.all([
      api<{account: {name: string}; services: Service[]}>("account"), api<Case[]>("cases"), api<Thread[]>("conversations")]);
    setName(account.account.name); setServices(account.services); setCases(cases); setThreads(conversations);
    setSelected(s => s || account.services[0]?.id || "");
    if (thread) {
      const data = await api<{approvals: Approval[]; messages: Message[]}>(`conversations/${thread.id}`);
      setApprovals(data.approvals); setHistory(data.messages);
    }
    } finally { refreshing.current = false; }
  }, [thread]);
  useEffect(() => {refresh().catch(e => setError(e.message)); const timer = setInterval(() => refresh().catch(() => {}), 10000); return () => clearInterval(timer);}, [refresh]);
  const service = services.find(s => s.id === (thread?.service_id || selected));
  const CareMessages = () => <div className="care-messages">
    {history.length === 0 ? <div className="care-welcome"><p>How can I help with this service?</p><span>Try: “activate my service”, “explain my bill”, or “apply a discount”.</span></div> :
      history.map(m => <div className={`care-message ${m.role}`} key={m.id}><strong>{m.role === "user" ? "You" : "CareAgent"}</strong><p>{m.content}</p></div>)}
  </div>;
  const sendMessage = async (message: string) => {
    if (!thread) return;
    setBusy(true); setError(""); setNotice("");
    try { const result = await api<{message: string}>(`conversations/${thread.id}/messages`, {run_id: crypto.randomUUID(), message}); setNotice(result.message); await refresh(); }
    catch(e) { setError((e as Error).message); throw e; }
    finally { setBusy(false); }
  };
  return <main className="workspace"><div className="page-heading"><div><span className="eyebrow">CUSTOMER WORKSPACE</span><h1>Good to see you, {name.split(" ")[0] || "there"}.</h1><p>Let’s get your day connected.</p></div><span className="status-dot">Support is ready</span></div>
    {error && <p role="alert" className="error">{error}</p>}
    <div className="workspace-grid"><aside><section className="panel"><span className="eyebrow">YOUR SERVICES</span><h2>What can we help with?</h2>
      <label>Choose a service<select value={selected} onChange={e => setSelected(e.target.value)}>{services.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}</select></label>
      <button className="primary full" disabled={busy || !selected} onClick={async () => {setBusy(true); setError(""); try {setThread(await api<Thread>("conversations", {service_id: selected})); setHistory([]); setApprovals([]); setNotice("");} catch(e) {setError((e as Error).message);} finally {setBusy(false);}}}>Start a conversation ↗</button>
      {service && <div className="service-card"><span>{service.kind === "mobile" ? "◉ MOBILE" : "⌁ BROADBAND"}</span><h3>{service.label}</h3><p>{service.plan}</p><span className={`badge ${service.status}`}>{service.status}</span>{service.discount_code && <p>Offer: {service.discount_code}</p>}</div>}
    </section><section className="panel"><span className="eyebrow">PICK UP WHERE YOU LEFT OFF</span><div className="thread-list">{threads.length === 0 && <p>No conversations yet.</p>}{threads.map(t => <button className={thread?.id === t.id ? "selected" : ""} key={t.id} onClick={() => {setThread(t); setNotice("");}}>{services.find(s => s.id === t.service_id)?.label || t.service_id}<small>{t.id.slice(0, 8)} →</small></button>)}</div></section></aside>
    <section className="chat-panel panel"><div className="chat-heading"><div className="agent-avatar">c</div><div><h2>Your care team</h2><p>{service?.label || "Mobile & broadband specialists"}</p></div></div>
      {thread ? <><CopilotKit key={thread.id} runtimeUrl="/api/copilotkit" agent="careagent" threadId={thread.id} useSingleEndpoint={true} enableInspector={false}>
        <CopilotChat Messages={CareMessages} Input={(props: {inProgress: boolean}) => <CareInput threadId={thread.id} busy={busy} inProgress={props.inProgress} onSend={sendMessage}/>} suggestions={[]} labels={{title: "CareAgent", initial: "How can I help with this service?"}}/>
      </CopilotKit>
      {busy && <div className="chat-loading" role="status" aria-live="polite"><span className="loader-dot"/> CareAgent is checking your account…</div>}
      {approvals.filter(a => a.status === "pending").map(a => <div className="approval" key={a.id}><span className="eyebrow">YOUR CONFIRMATION NEEDED</span><h3>{a.issue.replaceAll("_", " ")}</h3><p>{Object.entries(JSON.parse(a.parameters)).map(([k,v]) => `${k.replaceAll("_", " ")}: ${v}`).join(" · ")}</p><p>This changes the selected service in the demo.</p><div className="button-row">{[true, false].map(approved => <button key={String(approved)} className={approved ? "primary" : "secondary"} disabled={busy} onClick={async () => {setBusy(true); setError(""); try {const result = await api<{message: string}>(`approvals/${a.id}`, {approved}); setNotice(result.message); await refresh();} catch(e) {setError((e as Error).message);} finally {setBusy(false);}}}>{approved ? "Approve" : "Decline"}</button>)}</div></div>)}
      {notice && <div className="notice" role="status">{notice}</div>}
      <details className="history"><summary>Saved conversation · {history.length} messages</summary>{history.map(m => <div key={m.id}><strong>{m.role === "user" ? "You" : "CareAgent"}</strong><p>{m.content}</p></div>)}</details><button className="quiet recovery" disabled={busy} onClick={async () => {setBusy(true); setError(""); try {const result = await api<{message: string}>(`conversations/${thread.id}/recover`, {}); setNotice(result.message); await refresh();} catch(e) {setError((e as Error).message);} finally {setBusy(false);}}}>Recover interrupted request</button></> : <div className="empty-chat"><div className="orbit">✳</div><h2>A specialist for every step.</h2><p>Choose your service and start a conversation.<br/>We’ll check your account and find the right way forward.</p><div className="topic-chips">{["Activation", "Billing", "Discounts", "Trade-in", "Service changes"].map(t => <span key={t}>{t}</span>)}</div></div>}
    </section></div><section className="cases-section"><div className="section-heading"><h2>Your support cases</h2><span>{cases.length} cases</span></div>{cases.length === 0 ? <p>No escalations. If you need a person, just ask in chat.</p> : <div className="case-grid">{cases.map(c => <article className="panel" key={c.id}><span className="badge">{c.status}</span><h3>{c.issue.replaceAll("_", " ")}</h3><p>{c.summary}</p>{c.resolution && <p className="notice">{c.resolution}</p>}<small>Case {c.id.slice(0,8)}</small></article>)}</div>}</section>
    <p className="mode-note">Signed in as {user.email}. You’re using simulated accounts and services.</p>
  </main>;
}

function Operator({user}: {user: User}) {
  const [cases, setCases] = useState<Case[]>([]);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [note, setNote] = useState("");
  const [action, setAction] = useState("resolve");
  const [credit, setCredit] = useState("10");
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const refresh = () => api<Case[]>("cases").then(setCases).catch(e => setError(e.message));
  useEffect(() => {refresh(); const timer = setInterval(refresh, 5000); return () => clearInterval(timer);}, []);
  return <main className="workspace"><div className="page-heading"><div><span className="eyebrow">OPERATOR WORKSPACE</span><h1>Care that goes further.</h1><p>Review the evidence. Take the next step.</p></div><span className="pill">{cases.filter(c => c.status === "open").length} OPEN CASES</span></div>
    {error && <p role="alert" className="error">{error}</p>}<div className="operator-grid"><section className="panel"><h2>Escalation queue</h2>{cases.length === 0 && <p>No cases waiting for review.</p>}{cases.map(c => <button className="queue-item" key={c.id} onClick={async () => {try {setDetail(await api<CaseDetail>(`operator/cases/${c.id}`)); setAction("resolve"); setNote(""); setConfirmed(false);} catch(e) {setError((e as Error).message);}}}><span className="badge">{c.status}</span><strong>{c.issue.replaceAll("_", " ")}</strong><p>{c.summary}</p><small>{c.id.slice(0,8)} →</small></button>)}</section>
    <section className="panel">{!detail ? <div className="empty-chat"><div className="orbit">↗</div><h2>The full picture, in one place.</h2><p>Select a case to review account findings and attempted actions.</p></div> : <><span className="eyebrow">CASE {detail.case.id.slice(0,8)}</span><h2>{detail.service.label}</h2><p>{detail.case.summary}</p><h3>Account evidence</h3><p>Service is <strong>{detail.service.status}</strong> on {detail.service.plan}.</p>{detail.invoices.map((i,n) => <p key={n}>{i.breakdown} Current balance: ${((i.total_cents-i.credit_cents)/100).toFixed(2)}.</p>)}<pre>{JSON.stringify(JSON.parse(detail.case.evidence), null, 2)}</pre><h3>Attempted actions</h3>{detail.actions.length ? detail.actions.map(a => <p key={a.id}>{a.issue} — {a.status}</p>) : <p>No service changes attempted.</p>}<details className="history"><summary>Conversation history</summary>{detail.messages.map(m => <div key={m.id}><strong>{m.role}</strong><p>{m.content}</p></div>)}</details>
    {detail.case.status === "resolved" ? <p className="notice">{detail.case.resolution}</p> : <form onSubmit={async e => {e.preventDefault(); setBusy(true); setError(""); try {await api(`operator/cases/${detail.case.id}/resolve`, {action, note, confirmed, credit_cents: action === "credit" ? Math.round(Number(credit)*100) : 0}); setDetail(await api<CaseDetail>(`operator/cases/${detail.case.id}`)); await refresh();} catch(e) {setError((e as Error).message);} finally {setBusy(false);}}}>
      <h3>Resolve this case</h3><label>Action<select value={action} onChange={e => setAction(e.target.value)}><option value="resolve">Record resolution</option>{detail.case.issue === "billing" && <option value="credit">Apply billing credit</option>}{detail.case.issue === "disconnect" && <option value="disconnect">Permanently disconnect service</option>}</select></label>
      {action === "credit" && <label>Credit amount ($)<input type="number" min="0.01" max="100" step="0.01" value={credit} onChange={e => setCredit(e.target.value)}/></label>}
      <label>Resolution note<textarea minLength={5} required value={note} onChange={e => setNote(e.target.value)} placeholder="Explain the outcome for the customer…"/></label><label className="checkbox"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)}/>I reviewed the case and confirm this action.</label><button className="primary" disabled={busy || !confirmed}>{busy ? "Saving…" : "Complete resolution"}</button>
    </form>}</>}</section></div><p className="mode-note">Operator: {user.email} · All actions are audited.</p></main>;
}
