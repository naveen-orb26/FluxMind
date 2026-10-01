"use client";

import React, { useState, useEffect } from "react";
import {
  Zap,
  Sun,
  CloudRain,
  Car,
  Leaf,
  Play,
  Bot,
  RefreshCw,
  Sliders,
} from "lucide-react";

import { DefaultConfig } from "../lib/types";

interface HeaderProps {
  currentScenario: string;
  currentPolicy: string;
  onSelectPreset: (presetKey: string) => void;
  onRunOptimization: () => void;
  isOptimizing: boolean;
  onToggleCopilot: () => void;
  isCopilotOpen: boolean;
  hasOptimized: boolean;
  config?: DefaultConfig;
}

export const Header: React.FC<HeaderProps> = ({
  currentScenario,
  currentPolicy,
  onSelectPreset,
  onRunOptimization,
  isOptimizing,
  onToggleCopilot,
  isCopilotOpen,
  hasOptimized,
  config: propConfig,
}) => {
  const [fetchedConfig, setFetchedConfig] = useState<any>(null);

  useEffect(() => {
    // If parent didn't pass config, fetch directly from your new server route
    if (!propConfig) {
      const fetchConfig = async () => {
        try {
          const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
          // Try /api/config first, fallback to /api/grid/config
          let res = await fetch(`${baseUrl}/api/config`);
          if (!res.ok) {
            res = await fetch(`${baseUrl}/api/grid/config`);
          }
          if (res.ok) {
            const data = await res.json();
            setFetchedConfig(data);
          }
        } catch (err) {
          console.warn("Could not fetch remote config, using defaults:", err);
        }
      };
      fetchConfig();
    }
  }, [propConfig]);

  const activeConfig = propConfig || fetchedConfig;

  // Read dynamically from backend YAML with updated 500-flat microgrid fallbacks
  const apartments = activeConfig?.community?.apartments ?? 500;
  const evChargers = activeConfig?.community?.ev_chargers ?? 60;
  const solarKw = activeConfig?.community?.solar_capacity_kw ?? 350;
  const batteryKwh = activeConfig?.community?.battery_capacity_kwh ?? 600;
  const dcPowerKw = activeConfig?.flexible_loads?.data_center?.flexible_power_kw ?? 200;

  const presets = [
    { key: "S1", label: "S1: Normal Day", icon: Zap, sub: "Default" },
    { key: "S2", label: "S2: Solar-Rich", icon: Sun, sub: "+40% Solar" },
    { key: "S3", label: "S3: Cloudy Day", icon: CloudRain, sub: "-40% Solar" },
    { key: "S5", label: "S5: EV Surge", icon: Car, sub: "+20 EVs" },
    { key: "CARBON", label: "Carbon Priority", icon: Leaf, sub: "Min CO₂e" },
  ];

  return (
    <header className="border-b border-gray-800 bg-[#0b0f19]/80 backdrop-blur-md sticky top-0 z-30 px-4 lg:px-8 py-3.5">
      <div className="max-w-[1720px] mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        {/* Brand & Digital Twin Status */}
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-sky-600 to-emerald-500 flex items-center justify-center shadow-lg shadow-sky-500/20">
            <Zap className="h-5 w-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-1.5">
                FluxMind
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-sky-950 text-sky-400 border border-sky-800/60">
                  DER Orchestrator
                </span>
              </h1>
              <span className="flex items-center gap-1.5 text-[11px] font-medium text-emerald-400 bg-emerald-950/60 border border-emerald-800/40 px-2 py-0.5 rounded-full">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                Digital Twin Live
              </span>
            </div>
            <p className="text-xs text-gray-400 font-mono">
              {apartments} Apartments • {evChargers} EVs • {solarKw} kW Solar • {batteryKwh} kWh BESS • {dcPowerKw} kW Compute
            </p>
          </div>
        </div>

        {/* 1-Click Scenario Preset Switcher */}
        <div className="flex flex-wrap items-center gap-1.5 bg-gray-900/90 p-1 rounded-xl border border-gray-800">
          <span className="text-[11px] font-mono text-gray-400 px-2 font-semibold flex items-center gap-1">
            <Sliders className="h-3 w-3 text-sky-400" /> Presets:
          </span>
          {presets.map((p) => {
            const Icon = p.icon;
            const isActive = currentScenario === p.key;
            return (
              <button
                key={p.key}
                onClick={() => onSelectPreset(p.key)}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? "bg-gradient-to-r from-sky-600 to-cyan-600 text-white shadow-md shadow-sky-600/30"
                    : "text-gray-300 hover:text-white hover:bg-gray-800/80"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                <span>{p.label}</span>
                <span className="text-[10px] opacity-75 hidden sm:inline">({p.sub})</span>
              </button>
            );
          })}
        </div>

        {/* Action Controls: Optimization & AI Copilot */}
        <div className="flex items-center gap-2 w-full md:w-auto justify-end">
          <button
            onClick={onRunOptimization}
            disabled={isOptimizing}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold shadow-lg transition-all ${
              isOptimizing
                ? "bg-gray-800 text-gray-400 cursor-not-allowed border border-gray-700"
                : hasOptimized
                ? "bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/25 border border-emerald-400/30"
                : "bg-sky-600 hover:bg-sky-500 text-white shadow-sky-600/25 border border-sky-400/30"
            }`}
          >
            {isOptimizing ? (
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="h-3.5 w-3.5 fill-current" />
            )}
            <span>
              {isOptimizing
                ? "Solving CP-SAT..."
                : hasOptimized
                ? "Re-Run Optimizer"
                : "Optimize Schedule"}
            </span>
          </button>

          <button
            onClick={onToggleCopilot}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold border transition-all ${
              isCopilotOpen
                ? "bg-violet-600 text-white border-violet-400 shadow-lg shadow-violet-600/20"
                : "bg-gray-800/80 text-gray-300 hover:text-white hover:bg-gray-800 border-gray-700"
            }`}
          >
            <Bot className="h-4 w-4 text-violet-400" />
            <span className="hidden sm:inline">AI Copilot</span>
          </button>
        </div>
      </div>
    </header>
  );
};