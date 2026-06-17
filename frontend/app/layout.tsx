import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Deep Research Agent",
  description: "AI-powered research assistant using Gemini 2.5 Flash Lite and Tavily",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-gray-50 text-gray-900 antialiased">{children}</body>
    </html>
  );
}
