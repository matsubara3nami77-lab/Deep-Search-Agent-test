"use client";

import { useState } from "react";

interface PlanViewerProps {
  plan: string[];
  awaitingReview: boolean;
  completed?: number;
  isBusy: boolean;
  onStart: () => void;
  onRegenerate: (instruction: string) => void;
}

function StepIcon({ state }: { state: "done" | "running" | "pending" }) {
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
  return (
    <span className="w-5 h-5 rounded-full border-2 border-gray-300 flex-shrink-0" />
  );
}

export default function PlanViewer({
  plan,
  awaitingReview,
  completed = 0,
  isBusy,
  onStart,
  onRegenerate,
}: PlanViewerProps) {
  const [showEdit, setShowEdit] = useState(false);
  const [instruction, setInstruction] = useState("");

  const handleRegenerate = () => {
    const text = instruction.trim();
    if (!text) return;
    onRegenerate(text);
    setInstruction("");
    setShowEdit(false);
  };

  return (
    <div className="mb-4 bg-indigo-50/60 border border-indigo-200 rounded-2xl px-4 py-3">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-semibold text-indigo-700 bg-indigo-100 px-2 py-0.5 rounded-full">
          PLAN MODE ACTIVE
        </span>
      </div>

      <ol className="space-y-2 mb-3">
        {plan.map((step, i) => {
          const state: "done" | "running" | "pending" =
            i < completed ? "done" : i === completed ? "running" : "pending";
          return (
            <li key={i} className="flex items-start gap-2.5">
              <StepIcon state={awaitingReview ? "pending" : state} />
              <span
                className={`text-sm leading-snug ${
                  !awaitingReview && i < completed
                    ? "text-gray-400 line-through"
                    : "text-gray-700"
                }`}
              >
                <span className="font-medium text-gray-500 mr-1">{i + 1}.</span>
                {step}
              </span>
            </li>
          );
        })}
      </ol>

      {awaitingReview && (
        <div className="border-t border-indigo-100 pt-3">
          {showEdit && (
            <textarea
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder='e.g. "focus more on open-source tools"'
              rows={2}
              disabled={isBusy}
              className="w-full mb-2 bg-white border border-indigo-200 rounded-lg px-3 py-2 text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent disabled:opacity-60 resize-none"
            />
          )}

          <div className="flex flex-wrap gap-2">
            {!showEdit ? (
              <button
                type="button"
                onClick={() => setShowEdit(true)}
                disabled={isBusy}
                className="text-xs font-medium text-indigo-700 bg-white border border-indigo-300 hover:bg-indigo-50 px-3 py-2 rounded-lg transition disabled:opacity-60 disabled:cursor-not-allowed"
              >
                Edit Instruction
              </button>
            ) : (
              <button
                type="button"
                onClick={handleRegenerate}
                disabled={isBusy || !instruction.trim()}
                className="text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 px-3 py-2 rounded-lg transition disabled:bg-indigo-300 disabled:cursor-not-allowed flex items-center gap-1.5"
              >
                {isBusy ? (
                  <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : null}
                Regenerate Plan
              </button>
            )}

            <button
              type="button"
              onClick={onStart}
              disabled={isBusy}
              className="text-xs font-medium text-white bg-emerald-600 hover:bg-emerald-700 px-3 py-2 rounded-lg transition disabled:bg-emerald-300 disabled:cursor-not-allowed"
            >
              Start Execution
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
