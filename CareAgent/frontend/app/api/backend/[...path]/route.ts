import { NextRequest } from "next/server";

async function proxy(request: NextRequest, context: { params: Promise<{path: string[]}> }) {
  const { path } = await context.params;
  const base = process.env.BACKEND_URL || "http://127.0.0.1:8000";
  const headers = new Headers();
  for (const name of ["cookie", "content-type", "origin", "traceparent"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  try {
    const response = await fetch(`${base}/api/v1/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`, {
      method: request.method, headers, cache: "no-store",
      body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.text(),
    });
    const outgoing = new Headers({ "Content-Type": response.headers.get("content-type") || "application/json", "Cache-Control": "no-store" });
    for (const cookie of response.headers.getSetCookie()) outgoing.append("Set-Cookie", cookie);
    return new Response(response.body, { status: response.status, headers: outgoing });
  } catch {
    return Response.json({ detail: "CareAgent API is unavailable. Check the backend and Oracle health." }, {status: 503});
  }
}
export const GET = proxy;
export const POST = proxy;
