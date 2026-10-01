"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  X,
  Send,
  Bot,
  User,
  Sparkles,
  ChevronDown,
  ChevronRight,
  Terminal,
  Cpu,
  Layers,
  HelpCircle,
} from "lucide-react";
import { AgentChatMessage, AgentToolCall } from "../lib/types";
import { sendAgentChatMessage } from "../lib/api";

interface AICopilotDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onTriggerPreset?: (preset: string) => void;
}

export const AICopilotDrawer: React.FC<AICopilotDrawerProps> = ({
  isOpen,
  onClose,
  onTriggerPreset,
}) => {
  const [messages, setMessages] = useState<AgentChatMessage[]>([
    {
      id: "welcome",
      sender: "agent",
      text: "Hello! I am your AI Community Energy Copilot. I analyze the 96-interval digital twin, monitor PCC limits, invoke CP-SAT optimization tools, and explain DER dispatch decisions in natural language. How can I assist you?",
      timestamp: "12:00 PM",
    },
  ]);
  const [inputValue, setInputValue] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [expandedTools, setExpandedTools] = useState<Record<string, boolean>>({});

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isOpen]);

  const toggleToolExpand = (toolId: string) => {
    setExpandedTools((prev) => ({ ...prev, [toolId]: !prev[toolId] }));
  };

  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || inputValue;
    if (!text.trim() || isSending) return;

    const userMsg: AgentChatMessage = {
      id: `user_${Date.now()}`,
      sender: "user",
      text: text.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInputValue("");
    setIsSending(true);

    try {
      const data = await sendAgentChatMessage(userMsg.text);
      const agentMsg: AgentChatMessage = {
        id: `agent_${Date.now()}`,
        sender: "agent",
        text: data.response,
        tool_calls: data.tool_calls,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, agentMsg]);
    } catch (err) {
      const errorMsg: AgentChatMessage = {
        id: `agent_${Date.now()}`,
        sender: "agent",
        text: "Sorry, I encountered an issue communicating with the Energy Orchestrator API. Please verify the backend is running.",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsSending(false);
    }
  };

  const suggestedPrompts = [
    "Why did you move the EV charging sessions?",
    "What if tomorrow is 40% cloudier?",
    "What if 20 more EVs arrive?",
    "Explain current grid peak and battery status",
  ];

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[460px] bg-[#0d1322] border-l border-gray-800 shadow-2xl flex flex-col transition-all">
      {/* Drawer Header */}
      <div className="p-4 border-b border-gray-800 flex items-center justify-between bg-gray-900/60 backdrop-blur">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-tr from-violet-600 to-indigo-500 flex items-center justify-center shadow-md shadow-violet-600/25">
            <Bot className="h-4 w-4 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-1.5">
              AI Energy Copilot
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-violet-950 text-violet-400 border border-violet-800/60">
                Agentic Layer
              </span>
            </h3>
            <p className="text-[11px] text-gray-400">Grounding & Tools Orchestrator (Section 13)</p>
          </div>
        </div>

        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.sender === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.sender === "agent" && (
              <div className="h-7 w-7 rounded-lg bg-violet-950 border border-violet-800/80 flex items-center justify-center shrink-0 mt-0.5">
                <Sparkles className="h-3.5 w-3.5 text-violet-400" />
              </div>
            )}

            <div
              className={`max-w-[85%] rounded-2xl px-4 py-3 text-xs leading-relaxed ${
                msg.sender === "user"
                  ? "bg-sky-600 text-white shadow-md shadow-sky-600/20"
                  : "bg-gray-900 border border-gray-800 text-gray-200"
              }`}
            >
              {/* Tool Execution Badges (Section 13.2) */}
              {msg.tool_calls && msg.tool_calls.length > 0 && (
                <div className="mb-2.5 space-y-1.5">
                  <div className="text-[10px] font-mono text-gray-400 uppercase tracking-wider flex items-center gap-1">
                    <Terminal className="h-3 w-3 text-sky-400" /> Executed Analytical Tools:
                  </div>
                  {msg.tool_calls.map((tool, idx) => {
                    const toolKey = `${msg.id}_tool_${idx}`;
                    const isExp = expandedTools[toolKey];
                    return (
                      <div
                        key={idx}
                        className="rounded-lg bg-gray-950/80 border border-gray-800 overflow-hidden text-[11px] font-mono"
                      >
                        <button
                          onClick={() => toggleToolExpand(toolKey)}
                          className="w-full flex items-center justify-between px-2.5 py-1.5 text-sky-300 hover:bg-gray-800/40 text-left"
                        >
                          <span className="flex items-center gap-1.5">
                            <Cpu className="h-3 w-3 text-violet-400" />
                            <strong className="text-gray-200">Called:</strong> {tool.name}()
                          </span>
                          {isExp ? (
                            <ChevronDown className="h-3.5 w-3.5 text-gray-400" />
                          ) : (
                            <ChevronRight className="h-3.5 w-3.5 text-gray-400" />
                          )}
                        </button>
                        {isExp && (
                          <div className="p-2 border-t border-gray-800/60 bg-black/40 text-[10px] text-gray-400">
                            <div>
                              <span className="text-gray-500">Args:</span>{" "}
                              {JSON.stringify(tool.arguments)}
                            </div>
                            {tool.result && (
                              <div className="mt-1">
                                <span className="text-gray-500">Result:</span> {tool.result}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Natural Language Response */}
              <div className="whitespace-pre-line">{msg.text}</div>
              <div
                className={`text-[9px] mt-1.5 font-mono ${
                  msg.sender === "user" ? "text-sky-200" : "text-gray-400"
                }`}
              >
                {msg.timestamp}
              </div>
            </div>

            {msg.sender === "user" && (
              <div className="h-7 w-7 rounded-lg bg-sky-950 border border-sky-800/80 flex items-center justify-center shrink-0 mt-0.5">
                <User className="h-3.5 w-3.5 text-sky-400" />
              </div>
            )}
          </div>
        ))}
        {isSending && (
          <div className="flex gap-2.5 items-center text-xs text-gray-400 font-mono">
            <div className="h-6 w-6 rounded-lg bg-violet-950 border border-violet-800/60 flex items-center justify-center">
              <Bot className="h-3.5 w-3.5 text-violet-400 animate-spin" />
            </div>
            <span>Agent reasoning & querying digital twin tools...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Prompt Chips */}
      <div className="p-3 border-t border-gray-800/60 bg-gray-950/40">
        <div className="text-[10px] text-gray-400 font-mono mb-2 flex items-center gap-1">
          <HelpCircle className="h-3 w-3" /> Quick Scenario Questions:
        </div>
        <div className="flex flex-wrap gap-1.5">
          {suggestedPrompts.map((prompt, i) => (
            <button
              key={i}
              onClick={() => handleSendMessage(prompt)}
              className="text-[11px] text-gray-300 hover:text-white bg-gray-900 hover:bg-gray-800 border border-gray-800 rounded-lg px-2.5 py-1 transition text-left"
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>

      {/* Input Form */}
      <div className="p-3 border-t border-gray-800 bg-gray-900/60">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Ask about schedules, carbon, or what-if scenarios..."
            className="flex-1 bg-gray-950 border border-gray-800 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-sky-500 transition"
          />
          <button
            type="submit"
            disabled={!inputValue.trim() || isSending}
            className="p-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:hover:bg-violet-600 text-white shadow-lg transition"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
  );
};
