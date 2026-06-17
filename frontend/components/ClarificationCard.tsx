"use client";

import { useState } from "react";

interface ClarificationCardProps {
  question: string;
  options: string[];
  isBusy: boolean;
  onSubmit: (answer: string) => void;
}

const OTHER = "__other__";

export default function ClarificationCard({
  question,
  options,
  isBusy,
  onSubmit,
}: ClarificationCardProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const [otherText, setOtherText] = useState("");

  const resolvedAnswer = selected === OTHER ? otherText.trim() : selected ?? "";
  const canSubmit = resolvedAnswer.length > 0 && !isBusy;

  return (
    <div className="flex justify-start mb-4">
      <div className="flex items-start gap-2 w-full max-w-[90%]">
        <div className="w-7 h-7 bg-amber-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
          <svg className="w-4 h-4 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>

        <div className="flex-1 bg-amber-50 border border-amber-200 rounded-2xl rounded-tl-sm px-4 py-3">
          <p className="text-xs font-semibold text-amber-900 mb-1">Quick clarification</p>
          <p className="text-sm text-amber-900 mb-3 leading-relaxed">{question}</p>

          <div className="space-y-2">
            {options.map((opt) => (
              <label
                key={opt}
                className={`flex items-center gap-3 px-3 py-2 rounded-xl border cursor-pointer transition bg-white ${
                  selected === opt
                    ? "border-amber-500 ring-1 ring-amber-400"
                    : "border-amber-100 hover:border-amber-300"
                }`}
              >
                <input
                  type="radio"
                  name="clarify"
                  checked={selected === opt}
                  onChange={() => setSelected(opt)}
                  disabled={isBusy}
                  className="accent-amber-600"
                />
                <span className="text-sm text-gray-700">{opt}</span>
              </label>
            ))}

            <label
              className={`flex items-center gap-3 px-3 py-2 rounded-xl border cursor-pointer transition bg-white ${
                selected === OTHER
                  ? "border-amber-500 ring-1 ring-amber-400"
                  : "border-amber-100 hover:border-amber-300"
              }`}
            >
              <input
                type="radio"
                name="clarify"
                checked={selected === OTHER}
                onChange={() => setSelected(OTHER)}
                disabled={isBusy}
                className="accent-amber-600"
              />
              <span className="text-sm text-gray-700">Other</span>
            </label>

            {selected === OTHER && (
              <input
                type="text"
                value={otherText}
                onChange={(e) => setOtherText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && canSubmit) onSubmit(resolvedAnswer);
                }}
                placeholder="Describe what you're looking for..."
                disabled={isBusy}
                autoFocus
                className="w-full bg-white border border-amber-200 rounded-xl px-3 py-2 text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent disabled:opacity-60"
              />
            )}
          </div>

          <div className="mt-3">
            <button
              type="button"
              onClick={() => onSubmit(resolvedAnswer)}
              disabled={!canSubmit}
              className="flex items-center gap-1.5 bg-amber-600 hover:bg-amber-700 active:bg-amber-800 disabled:bg-amber-300 text-white text-xs font-medium px-4 py-2 rounded-lg transition disabled:cursor-not-allowed"
            >
              {isBusy ? (
                <>
                  <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Continuing...
                </>
              ) : (
                "Continue"
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
