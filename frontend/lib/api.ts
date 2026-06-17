export type Mode = "todo" | "plan";

/**
 * Callbacks for SSE events emitted by the backend research stream.
 *
 * SSE event shapes:
 *   {"type": "status",                "message": "..."}
 *   {"type": "report",                "content": "...markdown..."}
 *   {"type": "plan_review",           "execution_id": "...", "plan": ["..."]}
 *   {"type": "plan_progress",         "completed": n, "total": n}
 *   {"type": "clarification_required","execution_id": "...", "message": "...", "options": ["..."]}
 *   {"type": "approval_required",     "execution_id": "...", "message": "..."}
 *   {"type": "error",                 "message": "..."}
 *   {"type": "done"}
 */
export type StreamHandlers = {
  onStatus?: (message: string) => void;
  onChat?: (message: string) => void;
  onModeSwitch?: (target: Mode, message: string) => void;
  onReport?: (report: string) => void;
  onPlanReview?: (executionId: string, plan: string[]) => void;
  onPlanProgress?: (completed: number, total: number) => void;
  onClarification?: (executionId: string, question: string, options: string[]) => void;
  onApproval?: (executionId: string) => void;
  onError?: (error: string) => void;
  onDone?: () => void;
};

type SSEEvent = {
  type:
    | "status"
    | "chat"
    | "mode_switch"
    | "report"
    | "plan_review"
    | "plan_progress"
    | "clarification_required"
    | "approval_required"
    | "error"
    | "done";
  message?: string;
  content?: string;
  execution_id?: string;
  target?: Mode;
  plan?: string[];
  options?: string[];
  completed?: number;
  total?: number;
};

async function consumeStream(response: Response, handlers: StreamHandlers): Promise<void> {
  if (!response.ok || !response.body) {
    handlers.onError?.(`Request failed with status ${response.status}.`);
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
          const data = JSON.parse(trimmed.slice(6)) as SSEEvent;

          switch (data.type) {
            case "status":
              if (data.message) handlers.onStatus?.(data.message);
              break;
            case "chat":
              if (typeof data.content === "string") handlers.onChat?.(data.content);
              break;
            case "mode_switch":
              if (data.target === "plan" || data.target === "todo")
                handlers.onModeSwitch?.(data.target, data.message ?? "");
              break;
            case "report":
              if (typeof data.content === "string") handlers.onReport?.(data.content);
              break;
            case "plan_review":
              if (data.execution_id)
                handlers.onPlanReview?.(data.execution_id, data.plan ?? []);
              break;
            case "plan_progress":
              handlers.onPlanProgress?.(data.completed ?? 0, data.total ?? 0);
              break;
            case "clarification_required":
              if (data.execution_id)
                handlers.onClarification?.(
                  data.execution_id,
                  data.message ?? "Please clarify your request.",
                  data.options ?? [],
                );
              break;
            case "approval_required":
              if (data.execution_id) handlers.onApproval?.(data.execution_id);
              break;
            case "error":
              if (data.message) handlers.onError?.(data.message);
              break;
            case "done":
              handlers.onDone?.();
              break;
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

/** Start a new research session in the given mode. */
export async function streamResearch(
  query: string,
  mode: Mode,
  handlers: StreamHandlers,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch("/api/research", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, mode }),
    });
  } catch {
    handlers.onError?.("Network error: could not reach the research service.");
    return;
  }
  await consumeStream(response, handlers);
}

/**
 * Resume a paused session. `resume` is interpreted by the paused step:
 *   - clarification: string (selected/typed answer)
 *   - plan start:    { action: "start" }
 *   - plan edit:     { action: "edit", instruction: string }
 *   - approval:      boolean
 */
export async function continueResearch(
  executionId: string,
  resume: unknown,
  handlers: StreamHandlers,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch("/api/research/continue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ execution_id: executionId, resume }),
    });
  } catch {
    handlers.onError?.("Network error: could not reach the research service.");
    return;
  }
  await consumeStream(response, handlers);
}
