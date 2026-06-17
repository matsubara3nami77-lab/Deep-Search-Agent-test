"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import ReportPanel from "@/components/ReportPanel";
import {
  continueResearch,
  streamResearch,
  type Mode,
  type StreamHandlers,
  type SynthesisStatus,
  type Task,
} from "@/lib/api";

export type Message = {
  id: string;
  type: "user" | "status" | "agent" | "error";
  content: string;
};

type Clarification = {
  question: string;
  options: string[];
};

export type PhaseTone = "blue" | "indigo" | "amber";

export type Phase = {
  label: string;
  hint: string;
  tone: PhaseTone;
  started: boolean;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [report, setReport] = useState<string>("");
  const [mode, setMode] = useState<Mode>("todo");

  const [isStreaming, setIsStreaming] = useState(false);
  const [executionId, setExecutionId] = useState<string | null>(null);

  // Plan mode state (review of the Supervisor's decomposed tasks)
  const [plan, setPlan] = useState<string[] | null>(null);
  const [planAwaitingReview, setPlanAwaitingReview] = useState(false);

  // Multi-agent execution state
  const [tasks, setTasks] = useState<Task[]>([]);
  const [completedTaskIds, setCompletedTaskIds] = useState<number[]>([]);
  const [synthesisStatus, setSynthesisStatus] = useState<SynthesisStatus | null>(null);

  // Clarification state (independent of plan mode)
  const [clarification, setClarification] = useState<Clarification | null>(null);

  // HITL approval state (Level 2)
  const [pendingApproval, setPendingApproval] = useState(false);

  const modeRef = useRef<Mode>("todo");

  // Persist mode per session
  useEffect(() => {
    const saved = sessionStorage.getItem("research-mode");
    if (saved === "todo" || saved === "plan") {
      setMode(saved);
      modeRef.current = saved;
    }
  }, []);

  const changeMode = useCallback((next: Mode) => {
    setMode(next);
    modeRef.current = next;
    sessionStorage.setItem("research-mode", next);
  }, []);

  const addMessage = useCallback((type: Message["type"], content: string) => {
    setMessages((prev) => [
      ...prev,
      { id: `${Date.now()}-${Math.random()}`, type, content },
    ]);
  }, []);

  const buildHandlers = useCallback(
    (): StreamHandlers => ({
      onStatus: (m) => addMessage("status", m),
      onChat: (m) => addMessage("agent", m),
      onModeSwitch: (target, m) => {
        // Single source of truth: actually change the mode, THEN confirm.
        changeMode(target);
        addMessage("agent", m || `Switched to ${target.toUpperCase()} mode.`);
      },
      onReport: (r) => setReport(r),
      onTasks: (execId, t) => {
        setExecutionId(execId);
        setTasks(t);
        setCompletedTaskIds([]);
        setSynthesisStatus(null);
      },
      onTaskProgress: (taskId) =>
        setCompletedTaskIds((prev) =>
          prev.includes(taskId) ? prev : [...prev, taskId],
        ),
      onSynthesis: (status) => setSynthesisStatus(status),
      onPlanReview: (execId, p) => {
        setExecutionId(execId);
        setPlan(p);
        setPlanAwaitingReview(true);
      },
      onClarification: (execId, question, options) => {
        setExecutionId(execId);
        setClarification({ question, options });
      },
      onApproval: (execId) => {
        setExecutionId(execId);
        setPendingApproval(true);
      },
      onError: (e) => addMessage("error", e),
      onDone: () => {},
    }),
    [addMessage, changeMode],
  );

  // --- Start a new research session ---
  const handleSubmit = useCallback(
    async (raw: string) => {
      const trimmed = raw.trim();
      if (!trimmed || isStreaming) return;

      // Slash command prefix parsing.
      // `/plan` alone -> switch mode only. `/plan <query>` -> switch mode AND run.
      let query = trimmed;
      const COMMANDS: Record<string, Mode> = {
        "/plan": "plan",
        "/todo": "todo",
        "/research": "todo",
      };
      const firstSpace = trimmed.indexOf(" ");
      const firstToken = (
        firstSpace === -1 ? trimmed : trimmed.slice(0, firstSpace)
      ).toLowerCase();

      if (firstToken in COMMANDS) {
        const next = COMMANDS[firstToken];
        changeMode(next);
        const rest = firstSpace === -1 ? "" : trimmed.slice(firstSpace + 1).trim();
        if (!rest) {
          // Bare command: just switch the mode and wait for the next message.
          addMessage("status", `Switched to ${next.toUpperCase()} MODE`);
          return;
        }
        // Command + payload: run the remaining text in the new mode.
        query = rest;
      }

      // Reset session state
      setReport("");
      setPlan(null);
      setPlanAwaitingReview(false);
      setTasks([]);
      setCompletedTaskIds([]);
      setSynthesisStatus(null);
      setPendingApproval(false);
      setClarification(null);
      addMessage("user", query);

      setIsStreaming(true);
      try {
        await streamResearch(query, modeRef.current, buildHandlers());
      } catch {
        addMessage("error", "An unexpected error occurred. Please try again.");
      } finally {
        setIsStreaming(false);
      }
    },
    [isStreaming, changeMode, addMessage, buildHandlers],
  );

  // --- Resume helper ---
  const resume = useCallback(
    async (resumeValue: unknown) => {
      if (!executionId) return;
      setIsStreaming(true);
      try {
        await continueResearch(executionId, resumeValue, buildHandlers());
      } catch {
        addMessage("error", "An unexpected error occurred. Please try again.");
      } finally {
        setIsStreaming(false);
      }
    },
    [executionId, buildHandlers, addMessage],
  );

  // --- Clarification answer ---
  const handleClarify = useCallback(
    async (answer: string) => {
      if (!answer.trim()) return;
      setClarification(null);
      addMessage("status", `Refining request: ${answer}`);
      await resume(answer);
    },
    [resume, addMessage],
  );

  // --- Plan: start execution ---
  const handlePlanStart = useCallback(async () => {
    setPlanAwaitingReview(false);
    addMessage("agent", "Starting parallel research execution...");
    await resume({ action: "start" });
  }, [resume, addMessage]);

  // --- Plan: regenerate (AI-driven editing) ---
  const handlePlanRegenerate = useCallback(
    async (instruction: string) => {
      addMessage("status", `Regenerating plan: ${instruction}`);
      await resume({ action: "edit", instruction });
    },
    [resume, addMessage],
  );

  // --- HITL approval ---
  const handleApprove = useCallback(
    async (approved: boolean) => {
      setPendingApproval(false);
      await resume(approved);
    },
    [resume],
  );

  const phase: Phase = (() => {
    if (clarification)
      return {
        label: "Clarification needed",
        hint: "Answer the question to continue — research not started",
        tone: "amber",
        started: false,
      };
    if (pendingApproval)
      return {
        label: "Awaiting save approval",
        hint: "Approve or reject saving the report to disk",
        tone: "amber",
        started: true,
      };
    if (planAwaitingReview)
      return {
        label: "Plan ready for review",
        hint: "Edit, regenerate, or start execution — research not started",
        tone: "indigo",
        started: false,
      };
    if (isStreaming) {
      if (mode === "plan" && !plan)
        return {
          label: "Generating plan",
          hint: "Creating your research plan…",
          tone: "indigo",
          started: false,
        };
      if (mode === "plan")
        return {
          label: "Executing plan",
          hint: "Researching and writing the report…",
          tone: "indigo",
          started: true,
        };
      return {
        label: "Researching",
        hint: "Searching the web and writing the report…",
        tone: "blue",
        started: true,
      };
    }
    return mode === "plan"
      ? {
          label: "PLAN mode · Ready",
          hint: "Enter a topic — a plan is generated for review first",
          tone: "indigo",
          started: false,
        }
      : {
          label: "TODO mode · Ready",
          hint: "Enter a topic — research runs immediately",
          tone: "blue",
          started: false,
        };
  })();

  return (
    <div className="flex h-screen overflow-hidden bg-gray-100">
      <div
        className={`w-1/2 flex flex-col border-r shadow-sm bg-white ${
          mode === "plan" ? "border-indigo-200" : "border-gray-200"
        }`}
      >
        <ChatPanel
          messages={messages}
          onSubmit={handleSubmit}
          isStreaming={isStreaming}
          mode={mode}
          onModeChange={changeMode}
          phase={phase}
          plan={plan}
          planAwaitingReview={planAwaitingReview}
          tasks={tasks}
          completedTaskIds={completedTaskIds}
          synthesisStatus={synthesisStatus}
          onPlanStart={handlePlanStart}
          onPlanRegenerate={handlePlanRegenerate}
          pendingApproval={pendingApproval}
          onApprove={handleApprove}
          clarification={clarification}
          onClarify={handleClarify}
        />
      </div>
      <div className="w-1/2 flex flex-col bg-gray-50">
        <ReportPanel report={report} isLoading={isStreaming && !report && !planAwaitingReview} />
      </div>
    </div>
  );
}
