import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FluxMind | Community Energy Orchestrator",
  description:
    "AI-Powered Community Energy Management, Carbon-Aware DER Scheduling, Digital Twin & Agentic Copilot",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased bg-[#0b0f19] text-gray-100 min-h-screen">
        {children}
      </body>
    </html>
  );
}
