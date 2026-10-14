import { NextRequest } from "next/server";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const MAX_REQUEST = 10 * 1024 * 1024 + 65536;

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const target = `${process.env.API_BASE_URL || "http://127.0.0.1:8000"}/${path.map(encodeURIComponent).join("/")}`;
  let body: Uint8Array | undefined;
  if (request.method === "POST" && request.body) {
    const reader = request.body.getReader();
    const chunks: Uint8Array[] = [];
    let total = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > MAX_REQUEST) {
        await reader.cancel();
        return Response.json(
          { detail: "Request exceeds the 10 MB upload limit" },
          { status: 413 },
        );
      }
      chunks.push(value);
    }
    body = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) {
      body.set(chunk, offset);
      offset += chunk.byteLength;
    }
  }
  try {
    const response = await fetch(target, {
      method: request.method,
      body: body as BodyInit | undefined,
      headers: request.headers.has("content-type")
        ? { "Content-Type": request.headers.get("content-type")! }
        : {},
      cache: "no-store",
      signal: AbortSignal.timeout(180000),
    });
    const headers = new Headers({
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    });
    for (const key of ["content-type", "content-disposition"]) {
      const value = response.headers.get(key);
      if (value) headers.set(key, value);
    }
    return new Response(response.body, { status: response.status, headers });
  } catch {
    return Response.json(
      {
        detail:
          "Cannot reach the backend. Start FastAPI on port 8000, then retry.",
      },
      { status: 502 },
    );
  }
}
export const GET = proxy;
export const POST = proxy;
