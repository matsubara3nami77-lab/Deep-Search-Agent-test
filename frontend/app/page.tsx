"use client";

import { useCallback, useState } from "react";
import ChatPanel from "@/components/ChatPanel";
import ReportPanel from "@/components/ReportPanel";
import { streamResearch } from "@/lib/api";

export type Message = {
  id: string;
  type: "user" | "status" | "agent" | "error";
  content: string;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [report, setReport] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);

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
      addMessage("user", query);

      try {
        await streamResearch(
          query,
          (status) => addMessage("status", status),
          (reportContent) => {
            setReport(reportContent);
            addMessage("agent", "Research complete! The report has been generated and saved to disk.");
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

  return (
    <div className="flex h-screen overflow-hidden bg-gray-100">
      <div className="w-1/2 flex flex-col border-r border-gray-200 bg-white shadow-sm">
        <ChatPanel messages={messages} onSubmit={handleSubmit} isLoading={isLoading} />
      </div>
      <div className="w-1/2 flex flex-col bg-gray-50">
        <ReportPanel report={report} isLoading={isLoading} />
      </div>
    </div>
  );
}
