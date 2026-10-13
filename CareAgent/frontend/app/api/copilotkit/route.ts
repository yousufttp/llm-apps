import { NextRequest } from "next/server";
import { CopilotRuntime, ExperimentalEmptyAdapter, copilotRuntimeNextJSAppRouterEndpoint } from "@copilotkit/runtime";
import { HttpAgent } from "@ag-ui/client";
import { createHash } from "node:crypto";

type RuntimeEntry = { runtime: CopilotRuntime; expiresAt: number };
const globalCache = globalThis as typeof globalThis & { careagentRuntimes?: Map<string, RuntimeEntry> };
const runtimes = globalCache.careagentRuntimes ??= new Map<string, RuntimeEntry>();

function runtimeForSession(backend: string, cookie: string, origin: string | null) {
  const key = createHash("sha256").update(cookie).digest("hex");
  const now = Date.now();
  for (const [candidate, entry] of runtimes) if (entry.expiresAt < now) runtimes.delete(candidate);
  const existing = runtimes.get(key);
  if (existing) { existing.expiresAt = now + 8 * 60 * 60 * 1000; return existing.runtime; }
  const headers: Record<string, string> = {cookie};
  if (origin) headers.origin = origin;
  const runtime = new CopilotRuntime({
    agents: { careagent: new HttpAgent({url: `${backend}/api/v1/agent`, headers}) },
  });
  runtimes.set(key, {runtime, expiresAt: now + 8 * 60 * 60 * 1000});
  return runtime;
}

export async function POST(request: NextRequest) {
  const backend = process.env.BACKEND_URL || "http://127.0.0.1:8000";
  const cookie = request.headers.get("cookie") || "";
  const origin = request.headers.get("origin");
  const headers: Record<string, string> = { cookie };
  if (origin) headers.origin = origin;
  let envelope: {method?: string; params?: {threadId?: string}; body?: {threadId?: string}};
  try { envelope = await request.clone().json(); }
  catch { return Response.json({error: "Invalid request"}, {status: 400}); }
  try {
    // Discovery exposes capabilities only. Thread-aware operations require a
    // live session and ownership before the runtime can access cached events.
    if (envelope.method !== "info") {
      const auth = await fetch(`${backend}/api/v1/me`, {headers, cache: "no-store"});
      if (!auth.ok) return Response.json({error: "Sign in to continue"}, {status: 401});
      if (!["agent/run", "agent/connect", "agent/stop"].includes(envelope.method || "")) {
        return Response.json({error: "Unsupported operation"}, {status: 403});
      }
      const threadId = envelope.body?.threadId || envelope.params?.threadId;
      if (!threadId) return Response.json({error: "Conversation required"}, {status: 400});
      // The runtime's memory runner is process-global. Authorize connect/stop as well
      // as run before it can return any cached thread events.
      const ownership = await fetch(`${backend}/api/v1/conversations/${encodeURIComponent(threadId)}`, {headers, cache: "no-store"});
      if (!ownership.ok) return Response.json({error: "Conversation not found"}, {status: 404});
    }
  } catch {
    return Response.json({error: "CareAgent API is temporarily unavailable"}, {status: 503});
  }
  // Each authenticated session gets an isolated, bounded runtime so connect/run
  // share thread state without allowing event history to cross user sessions.
  const runtime = runtimeForSession(backend, cookie, origin);
  const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime, serviceAdapter: new ExperimentalEmptyAdapter(), endpoint: "/api/copilotkit",
  });
  return handleRequest(request);
}
