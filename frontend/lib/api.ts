/**
 * Stream research results via the Next.js proxy route (/api/research).
 *
 * SSE event shapes:
 *   {"type": "status",            "message": "..."}
 *   {"type": "report",            "content": "...markdown..."}
 *   {"type": "approval_required", "execution_id": "...", "message": "..."}
 *   {"type": "error",             "message": "..."}
 */
export async function streamResearch(
  query: string,
  onStatus: (message: string) => void,
  onReport: (report: string) => void,
  onApprovalRequired: (executionId: string, message: string) => void,
  onError: (error: string) => void,
): Promise<void> {
  let response: Response;

  try {
    response = await fetch("/api/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
  } catch {
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
            type: "status" | "report" | "approval_required" | "error";
            message?: string;
            content?: string;
            execution_id?: string;
          };

          if (data.type === "status" && data.message) {
            onStatus(data.message);
          } else if (data.type === "report" && data.content) {
            onReport(data.content);
          } else if (data.type === "approval_required" && data.execution_id) {
            onApprovalRequired(data.execution_id, data.message ?? "Save this report?");
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

/**
 * Approve or reject saving the report for a paused execution.
 * Returns {status: "saved"|"skipped", report_path: string}.
 */
export async function approveResearch(
  executionId: string,
  approved: boolean,
): Promise<{ status: "saved" | "skipped"; report_path: string }> {
  const response = await fetch("/api/research/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ execution_id: executionId, approved }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `Approval request failed (${response.status})`);
  }

  return response.json();
}
