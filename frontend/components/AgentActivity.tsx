"use client";

import type { SynthesisStatus, Task } from "@/lib/api";

type NodeState = "done" | "running" | "pending";

function StateIcon({ state }: { state: NodeState }) {
  if (state === "done") {
    return (
      <span className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center flex-shrink-0">
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
        </svg>
      </span>
    );
  }
  if (state === "running") {
    return (
      <span className="w-5 h-5 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center flex-shrink-0">
        <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </span>
    );
  }
  return <span className="w-5 h-5 rounded-full border-2 border-gray-300 flex-shrink-0" />;
}

function StateLabel({ state }: { state: NodeState }) {
  const text = state === "done" ? "completed" : state === "running" ? "running" : "pending";
  const cls =
    state === "done"
      ? "text-emerald-600"
      : state === "running"
        ? "text-indigo-600"
        : "text-gray-400";
  return <span className={`text-[11px] font-medium ${cls}`}>{text}</span>;
}

interface AgentActivityProps {
  tasks: Task[];
  completedTaskIds: number[];
  synthesisStatus: SynthesisStatus | null;
  isStreaming: boolean;
  pendingApproval: boolean;
}

export default function AgentActivity({
  tasks,
  completedTaskIds,
  synthesisStatus,
  isStreaming,
  pendingApproval,
}: AgentActivityProps) {
  const completed = new Set(completedTaskIds);
  const allWorkersDone = tasks.length > 0 && completed.size >= tasks.length;
  const active = isStreaming && !pendingApproval;

  const workerState = (taskId: number): NodeState => {
    if (completed.has(taskId)) return "done";
    return active ? "running" : "pending";
  };

  const synthState: NodeState =
    synthesisStatus === "completed" || pendingApproval
      ? "done"
      : synthesisStatus === "running" || (allWorkersDone && active)
        ? "running"
        : "pending";

  return (
    <div className="mb-4 bg-slate-50 border border-slate-200 rounded-2xl px-4 py-3">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-semibold text-slate-700 bg-slate-200 px-2 py-0.5 rounded-full">
          MULTI-AGENT EXECUTION
        </span>
      </div>

      {/* Supervisor */}
      <div className="flex items-center gap-2.5 mb-3">
        <StateIcon state="done" />
        <span className="text-sm font-medium text-gray-700 flex-1">
          Supervisor &middot; task decomposition
        </span>
        <StateLabel state="done" />
      </div>

      {/* Research Workers */}
      <div className="mb-3">
        <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-2 pl-0.5">
          Research Workers ({completed.size}/{tasks.length})
        </p>
        <ul className="space-y-2">
          {tasks.map((task) => {
            const state = workerState(task.id);
            return (
              <li key={task.id} className="flex items-start gap-2.5">
                <StateIcon state={state} />
                <span
                  className={`text-sm leading-snug flex-1 ${
                    state === "done" ? "text-gray-400" : "text-gray-700"
                  }`}
                >
                  <span className="font-medium text-gray-500 mr-1">{task.id}.</span>
                  {task.title}
                </span>
                <StateLabel state={state} />
              </li>
            );
          })}
        </ul>
      </div>

      {/* Synthesis */}
      <div className="flex items-center gap-2.5 border-t border-slate-200 pt-3">
        <StateIcon state={synthState} />
        <span className="text-sm font-medium text-gray-700 flex-1">
          Synthesis &middot; integrate findings
        </span>
        <StateLabel state={synthState} />
      </div>
    </div>
  );
}
