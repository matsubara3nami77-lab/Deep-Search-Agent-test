"use client";

import type { Mode } from "@/lib/api";

interface ModeToggleProps {
  mode: Mode;
  onChange: (mode: Mode) => void;
  disabled?: boolean;
}

export default function ModeToggle({ mode, onChange, disabled }: ModeToggleProps) {
  return (
    <div className="inline-flex items-center bg-gray-100 rounded-lg p-0.5 text-xs font-semibold select-none">
      <button
        type="button"
        onClick={() => onChange("todo")}
        disabled={disabled}
        aria-pressed={mode === "todo"}
        className={`px-3 py-1.5 rounded-md transition ${
          mode === "todo"
            ? "bg-blue-600 text-white shadow-sm"
            : "text-gray-500 hover:text-gray-700"
        } disabled:cursor-not-allowed disabled:opacity-60`}
      >
        TODO
      </button>
      <button
        type="button"
        onClick={() => onChange("plan")}
        disabled={disabled}
        aria-pressed={mode === "plan"}
        className={`px-3 py-1.5 rounded-md transition ${
          mode === "plan"
            ? "bg-indigo-600 text-white shadow-sm"
            : "text-gray-500 hover:text-gray-700"
        } disabled:cursor-not-allowed disabled:opacity-60`}
      >
        PLAN
      </button>
    </div>
  );
}
