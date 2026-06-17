/**
 * Stream research results via the Next.js proxy route (/api/research).
 * The proxy forwards the request to the FastAPI backend server-side,
 * eliminating cross-origin issues in the browser.
 *
 * SSE event shapes emitted by the backend:
 *   {"type": "status",  "message": "..."}
 *   {"type": "report",  "content": "..."}
 *   {"type": "error",   "message": "..."}
 */
export async function streamResearch(
  query: string,
  onStatus: (message: string) => void,
  onReport: (report: string) => void,
  onError: (error: string) => void,
): Promise<void> {
  let response: Response;

  try {
    response = await fetch("/api/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
  } catch (err) {
    onError("Network error: could not reach the research service.");
    return;
  }

  if (!response.ok || !response.body) {
    onError(`Request failed with status ${response.status}.`);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data: ")) continue;

        try {
          const data = JSON.parse(trimmed.slice(6)) as {
            type: "status" | "report" | "error";
            message?: string;
            content?: string;
          };

          if (data.type === "status" && data.message) {
            onStatus(data.message);
          } else if (data.type === "report" && data.content) {
            onReport(data.content);
          } else if (data.type === "error" && data.message) {
            onError(data.message);
          }
        } catch {
          // ignore malformed SSE lines
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
