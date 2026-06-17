import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return new Response(
      `data: ${JSON.stringify({ type: "error", message: "Invalid request body" })}\n\n`,
      { status: 400, headers: { "Content-Type": "text/event-stream" } },
    );
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${BACKEND_URL}/api/research`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      // @ts-expect-error – Node 18 fetch duplex option
      duplex: "half",
    });
  } catch {
    return new Response(
      `data: ${JSON.stringify({ type: "error", message: `Could not connect to research backend at ${BACKEND_URL}` })}\n\n`,
      { status: 200, headers: { "Content-Type": "text/event-stream" } },
    );
  }

  if (!backendResponse.ok || !backendResponse.body) {
    return new Response(
      `data: ${JSON.stringify({ type: "error", message: `Research backend returned ${backendResponse.status}` })}\n\n`,
      { status: 200, headers: { "Content-Type": "text/event-stream" } },
    );
  }

  return new Response(backendResponse.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
