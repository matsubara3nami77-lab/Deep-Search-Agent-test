"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import type { Message, Phase } from "@/app/page";
import type { Mode, SynthesisStatus, Task } from "@/lib/api";
import AgentActivity from "@/components/AgentActivity";
import ClarificationCard from "@/components/ClarificationCard";
import ModeToggle from "@/components/ModeToggle";
import PlanViewer from "@/components/PlanViewer";

interface ChatPanelProps {
  messages: Message[];
  onSubmit: (query: string) => void;
  isStreaming: boolean;
  mode: Mode;
  onModeChange: (mode: Mode) => void;
  phase: Phase;
  plan: string[] | null;
  planAwaitingReview: boolean;
  tasks: Task[];
  completedTaskIds: number[];
  synthesisStatus: SynthesisStatus | null;
  onPlanStart: () => void;
  onPlanRegenerate: (instruction: string) => void;
  pendingApproval: boolean;
  onApprove: (approved: boolean) => void;
  clarification: { question: string; options: string[] } | null;
  onClarify: (answer: string) => void;
}

const TONE_STYLES: Record<
  Phase["tone"],
  { bar: string; dot: string; label: string; hint: string }
> = {
  blue: {
    bar: "bg-blue-50 border-blue-200",
    dot: "bg-blue-500",
    label: "text-blue-800",
    hint: "text-blue-600",
  },
  indigo: {
    bar: "bg-indigo-50 border-indigo-200",
    dot: "bg-indigo-500",
    label: "text-indigo-800",
    hint: "text-indigo-600",
  },
  amber: {
    bar: "bg-amber-50 border-amber-200",
    dot: "bg-amber-500",
    label: "text-amber-900",
    hint: "text-amber-700",
  },
};

function StatusBar({
  phase,
  mode,
  isStreaming,
  pendingApproval,
}: {
  phase: Phase;
  mode: Mode;
  isStreaming: boolean;
  pendingApproval: boolean;
}) {
  const tone = TONE_STYLES[phase.tone];

  const researchLabel = !phase.started
    ? "Research: not started"
    : pendingApproval
      ? "Report ready"
      : isStreaming
        ? "Research: running"
        : "Research: active";

  return (
    <div className={`px-5 py-2.5 border-b flex items-center gap-3 ${tone.bar}`}>
      <span className="flex items-center justify-center w-5 h-5 flex-shrink-0">
        {isStreaming ? (
          <svg className={`w-4 h-4 animate-spin ${tone.label}`} fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        ) : (
          <span className={`w-2.5 h-2.5 rounded-full ${tone.dot}`} />
        )}
      </span>

      <div className="flex-1 min-w-0">
        <p className={`text-xs font-semibold leading-tight ${tone.label}`}>{phase.label}</p>
        <p className={`text-[11px] leading-tight truncate ${tone.hint}`}>{phase.hint}</p>
      </div>

      <span
        className={`text-[10px] font-semibold px-2 py-1 rounded-full whitespace-nowrap ${
          phase.started
            ? "bg-emerald-100 text-emerald-700"
            : "bg-gray-100 text-gray-500"
        }`}
      >
        {researchLabel}
      </span>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  if (message.type === "user") {
    return (
      <div className="flex justify-end mb-3">
        <div className="max-w-[80%] bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm shadow-sm leading-relaxed">
          {message.content}
        </div>
      </div>
    );
  }

  if (message.type === "status") {
    return (
      <div className="flex justify-center mb-2">
        <div className="flex items-center gap-2 text-xs text-gray-500 bg-gray-100 px-3 py-1.5 rounded-full max-w-[90%]">
          <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse flex-shrink-0" />
          <span className="truncate">{message.content}</span>
        </div>
      </div>
    );
  }

  if (message.type === "agent") {
    return (
      <div className="flex justify-start mb-3">
        <div className="flex items-start gap-2 max-w-[80%]">
          <div className="w-7 h-7 bg-emerald-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
            <svg className="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div className="bg-emerald-50 border border-emerald-100 text-emerald-800 rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm leading-relaxed">
            {message.content}
          </div>
        </div>
      </div>
    );
  }

  if (message.type === "error") {
    return (
      <div className="flex justify-start mb-3">
        <div className="flex items-start gap-2 max-w-[80%]">
          <div className="w-7 h-7 bg-red-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
            <svg className="w-4 h-4 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div className="bg-red-50 border border-red-100 text-red-800 rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm leading-relaxed">
            {message.content}
          </div>
        </div>
      </div>
    );
  }

  return null;
}

function ApprovalCard({
  isApproving,
  onApprove,
}: {
  isApproving: boolean;
  onApprove: (approved: boolean) => void;
}) {
  return (
    <div className="flex justify-start mb-4">
      <div className="flex items-start gap-2 w-full max-w-[90%]">
        <div className="w-7 h-7 bg-amber-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
          <svg className="w-4 h-4 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          </svg>
        </div>
        <div className="flex-1 bg-amber-50 border border-amber-200 rounded-2xl rounded-tl-sm px-4 py-3">
          <p className="text-sm font-medium text-amber-900 mb-1">Approval Required</p>
          <p className="text-sm text-amber-800 mb-3 leading-relaxed">
            Report generated successfully. Do you want to save this report to disk?
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => onApprove(true)}
              disabled={isApproving}
              className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 disabled:bg-emerald-300 text-white text-xs font-medium px-4 py-2 rounded-lg transition disabled:cursor-not-allowed"
            >
              {isApproving ? (
                <>
                  <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Saving...
                </>
              ) : (
                <>
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Approve
                </>
              )}
            </button>
            <button
              onClick={() => onApprove(false)}
              disabled={isApproving}
              className="flex items-center gap-1.5 bg-white hover:bg-gray-50 active:bg-gray-100 disabled:opacity-50 text-gray-700 border border-gray-300 text-xs font-medium px-4 py-2 rounded-lg transition disabled:cursor-not-allowed"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              Reject
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ChatPanel({
  messages,
  onSubmit,
  isStreaming,
  mode,
  onModeChange,
  phase,
  plan,
  planAwaitingReview,
  tasks,
  completedTaskIds,
  synthesisStatus,
  onPlanStart,
  onPlanRegenerate,
  pendingApproval,
  onApprove,
  clarification,
  onClarify,
}: ChatPanelProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [input, setInput] = useState("");

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, plan, completedTaskIds, synthesisStatus, pendingApproval, clarification]);

  const inputDisabled =
    isStreaming || planAwaitingReview || pendingApproval || !!clarification;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || inputDisabled) return;
    onSubmit(input.trim());
    setInput("");
  };

  const showEmptyState =
    messages.length === 0 &&
    !plan &&
    tasks.length === 0 &&
    !pendingApproval &&
    !clarification;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-5 py-4 border-b border-gray-100 bg-white">
        <div className="flex items-center gap-3">
          <div
            className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${
              mode === "plan" ? "bg-indigo-600" : "bg-blue-600"
            }`}
          >
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
          </div>
          <div>
            <h1 className="font-semibold text-gray-900 text-sm">Research Assistant</h1>
            <p className="text-xs text-gray-400">Powered by Gemini 3.1 Flash Lite &amp; Tavily</p>
          </div>
          <div className="ml-auto">
            <ModeToggle mode={mode} onChange={onModeChange} disabled={isStreaming} />
          </div>
        </div>
      </div>

      {/* Workflow status bar — always-visible source of truth for state */}
      <StatusBar
        phase={phase}
        mode={mode}
        isStreaming={isStreaming}
        pendingApproval={pendingApproval}
      />

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-4">
        {showEmptyState && (
          <div className="flex flex-col items-center justify-center h-full text-center select-none">
            <div className="w-14 h-14 bg-blue-50 rounded-2xl flex items-center justify-center mb-3">
              <svg className="w-7 h-7 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <p className="text-sm font-medium text-gray-600 mb-1">Start your research</p>
            <p className="text-xs text-gray-400 max-w-[230px]">
              {mode === "plan"
                ? "PLAN mode: a step-by-step plan is generated for your review before execution."
                : "TODO mode: research runs immediately, pausing only to approve saving."}
            </p>
            <p className="text-[11px] text-gray-300 mt-2">
              Tip: type <span className="font-mono">/plan</span> or{" "}
              <span className="font-mono">/todo</span> to switch modes
            </p>
            <div className="mt-5 flex flex-col gap-2 w-full max-w-xs">
              {[
                "AI coding agents in 2026",
                "Quantum computing breakthroughs",
                "Future of renewable energy",
              ].map((example) => (
                <button
                  key={example}
                  onClick={() => onSubmit(example)}
                  disabled={inputDisabled}
                  className="text-xs text-blue-600 bg-blue-50 hover:bg-blue-100 px-3 py-2 rounded-lg text-left transition disabled:opacity-50"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {plan && planAwaitingReview && (
          <PlanViewer
            plan={plan}
            awaitingReview={planAwaitingReview}
            completed={0}
            isBusy={isStreaming}
            onStart={onPlanStart}
            onRegenerate={onPlanRegenerate}
          />
        )}

        {tasks.length > 0 && !planAwaitingReview && (
          <AgentActivity
            tasks={tasks}
            completedTaskIds={completedTaskIds}
            synthesisStatus={synthesisStatus}
            isStreaming={isStreaming}
            pendingApproval={pendingApproval}
          />
        )}

        {clarification && (
          <ClarificationCard
            question={clarification.question}
            options={clarification.options}
            isBusy={isStreaming}
            onSubmit={onClarify}
          />
        )}

        {pendingApproval && (
          <ApprovalCard isApproving={isStreaming} onApprove={onApprove} />
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-gray-100 bg-white">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              planAwaitingReview
                ? "Review the plan above to continue..."
                : pendingApproval
                  ? "Respond to the approval above..."
                  : clarification
                    ? "Answer the clarification above..."
                    : mode === "plan"
                      ? "Describe a topic to plan research for..."
                      : "e.g. AI coding agents in 2026"
            }
            disabled={inputDisabled}
            className="flex-1 bg-gray-50 border border-gray-200 rounded-xl px-4 py-2.5 text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-60 disabled:cursor-not-allowed transition"
          />
          <button
            type="submit"
            disabled={inputDisabled || !input.trim()}
            className="bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:bg-blue-300 text-white rounded-xl px-4 py-2.5 text-sm font-medium transition flex items-center gap-2 disabled:cursor-not-allowed flex-shrink-0"
          >
            {isStreaming ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Working
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                Research
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
