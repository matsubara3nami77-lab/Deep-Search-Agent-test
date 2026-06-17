"use client";

import { useCallback, useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import ReportPanel from "@/components/ReportPanel";
import { approveResearch, streamResearch } from "@/lib/api";

export type Message = {
  id: string;
  type: "user" | "status" | "agent" | "error";
  content: string;
};

export type PendingApproval = {
  executionId: string;
  message: string;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [report, setReport] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [pendingApproval, setPendingApproval] = useState<PendingApproval | null>(null);
  const [isApproving, setIsApproving] = useState(false);

  const addMessage = useCallback((type: Message["type"], content: string) => {
    setMessages((prev) => [
      ...prev,
      { id: `${Date.now()}-${Math.random()}`, type, content },
    ]);
  }, []);

  const handleSubmit = useCallback(
    async (query: string) => {
      if (isLoading || !query.trim()) return;

      setIsLoading(true);
      setReport("");
      setPendingApproval(null);
      addMessage("user", query);

      try {
        await streamResearch(
          query,
          (status) => addMessage("status", status),
          (reportContent) => setReport(reportContent),
          (executionId, message) => {
            setPendingApproval({ executionId, message });
            addMessage("agent", "Report generated! Please review the report and choose whether to save it.");
          },
          (error) => addMessage("error", error),
        );
      } catch {
        addMessage("error", "An unexpected error occurred. Please try again.");
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, addMessage],
  );

  const handleApprove = useCallback(
    async (approved: boolean) => {
      if (!pendingApproval || isApproving) return;

      setIsApproving(true);
      setPendingApproval(null);

      try {
        const result = await approveResearch(pendingApproval.executionId, approved);

        if (result.status === "saved") {
          addMessage("agent", `Report saved to ${result.report_path}`);
        } else {
          addMessage("status", "Save skipped.");
        }
      } catch (err) {
        addMessage("error", `Approval failed: ${err instanceof Error ? err.message : String(err)}`);
      } finally {
        setIsApproving(false);
      }
    },
    [pendingApproval, isApproving, addMessage],
  );

  return (
    <div className="flex h-screen overflow-hidden bg-gray-100">
      <div className="w-1/2 flex flex-col border-r border-gray-200 bg-white shadow-sm">
        <ChatPanel
          messages={messages}
          onSubmit={handleSubmit}
          isLoading={isLoading}
          pendingApproval={pendingApproval}
          isApproving={isApproving}
          onApprove={handleApprove}
        />
      </div>
      <div className="w-1/2 flex flex-col bg-gray-50">
        <ReportPanel report={report} isLoading={isLoading && !pendingApproval} />
      </div>
    </div>
  );
}
