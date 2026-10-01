"use client";

import React, { useState, useEffect } from "react";
import { Header } from "../components/Header";
import { KpiCards } from "../components/KpiCards";
import { EnergyProfileChart } from "../components/EnergyProfileChart";
import { CarbonTariffChart } from "../components/CarbonTariffChart";
import { ComparisonImpactPanel } from "../components/ComparisonImpactPanel";
import { ScheduleTimeline } from "../components/ScheduleTimeline";
import { AICopilotDrawer } from "../components/AICopilotDrawer";
import {
  fetchGridTimeseries,
  fetchFlexibleLoads,
  runOptimization,
  generateFallbackSnapshots,
  generateFallbackSummary,
  fetchDefaultConfig,
} from "../lib/api";
import {
  GridSnapshot,
  GridSummary,
  FlexibleLoad,
  OptimizationResponse,
  DefaultConfig,
} from "../lib/types";
import { Sliders, Clock, Info } from "lucide-react";

export default function DashboardPage() {
  const [currentScenario, setCurrentScenario] = useState<string>("S1");
  const [currentPolicy, setCurrentPolicy] = useState<string>("BALANCED");
  const [selectedStep, setSelectedStep] = useState<number>(48); // default to step 48 (12:00 PM solar noon)

  const [defaultConfig, setDefaultConfig] = useState<DefaultConfig | undefined>();
  const [baselineSnapshots, setBaselineSnapshots] = useState<GridSnapshot[]>([]);
  const [baselineSummary, setBaselineSummary] = useState<GridSummary | undefined>();
  const [flexibleLoads, setFlexibleLoads] = useState<FlexibleLoad[]>([]);

  const [optimizationResult, setOptimizationResult] = useState<OptimizationResponse | null>(null);
  const [isOptimizedActive, setIsOptimizedActive] = useState<boolean>(true);
  const [isOptimizing, setIsOptimizing] = useState<boolean>(false);
  const [isCopilotOpen, setIsCopilotOpen] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Load initial baseline, default config, and trigger default optimization on mount
  useEffect(() => {
    async function loadInitialData() {
      setIsLoading(true);
      try {
        const [timeseriesData, loadsData, cfgData] = await Promise.all([
          fetchGridTimeseries("default_baseline"),
          fetchFlexibleLoads("default_baseline"),
          fetchDefaultConfig(),
        ]);
        setBaselineSnapshots(timeseriesData.timeseries);
        setBaselineSummary(timeseriesData.summary);
        setFlexibleLoads(loadsData);
        setDefaultConfig(cfgData);

        // Run initial optimization for instant comparison view
        const optRes = await runOptimization("BALANCED", "baseline");
        setOptimizationResult(optRes);
        setIsOptimizedActive(true);
      } catch (err) {
        console.error("Initial load error:", err);
        const fallbackSnaps = generateFallbackSnapshots();
        setBaselineSnapshots(fallbackSnaps);
        setBaselineSummary(generateFallbackSummary(fallbackSnaps));
      } finally {
        setIsLoading(false);
      }
    }
    loadInitialData();

    // Auto-poll config every 3 seconds so any edit to default.yaml immediately updates the UI live
    const intervalId = setInterval(async () => {
      try {
        const freshCfg = await fetchDefaultConfig();
        setDefaultConfig(freshCfg);
      } catch (e) {
        // silent error handling
      }
    }, 3000);

    const handleFocus = async () => {
      try {
        const freshCfg = await fetchDefaultConfig();
        setDefaultConfig(freshCfg);
      } catch (e) {}
    };

    window.addEventListener("focus", handleFocus);
    return () => {
      clearInterval(intervalId);
      window.removeEventListener("focus", handleFocus);
    };
  }, []);

  // Preset switch handler (Section 20 & 32)
  const handleSelectPreset = async (presetKey: string) => {
    setCurrentScenario(presetKey);
    setIsOptimizing(true);

    let scenarioName = "baseline";
    let policy = "BALANCED";
    let overrides: Record<string, any> = {};

    let latestConfig = defaultConfig;
    try {
      latestConfig = await fetchDefaultConfig();
      setDefaultConfig(latestConfig);
    } catch (e) {}

    const baseEvCount = latestConfig?.community?.ev_chargers ?? 40;

    if (presetKey === "S1") {
      // Normal Day
      scenarioName = "baseline";
      policy = "BALANCED";
      overrides = { solar_multiplier: 1.0, ev_count: baseEvCount };
    } else if (presetKey === "S2") {
      // Solar-Rich Day (+40% solar)
      scenarioName = "baseline";
      policy = "BALANCED";
      overrides = { solar_multiplier: 1.4, ev_count: baseEvCount };
    } else if (presetKey === "S3") {
      // Cloudy Day (-40% solar)
      scenarioName = "baseline";
      policy = "BALANCED";
      overrides = { solar_multiplier: 0.6, ev_count: baseEvCount };
    } else if (presetKey === "S5") {
      // EV Surge (+20 EVs)
      scenarioName = "baseline";
      policy = "BALANCED";
      overrides = { ev_count: baseEvCount + 20 };
    } else if (presetKey === "CARBON") {
      // Carbon Priority Policy Mode
      scenarioName = "baseline";
      policy = "CARBON_PRIORITY";
      overrides = {};
    }

    setCurrentPolicy(policy);

    try {
      const optRes = await runOptimization(policy, scenarioName, overrides);
      setOptimizationResult(optRes);
      if (optRes.snapshots && optRes.snapshots.length > 0) {
        setBaselineSnapshots(optRes.snapshots);
        setBaselineSummary(optRes.baseline_metrics);
      }
      setIsOptimizedActive(true);
    } catch (err) {
      console.error("Preset execution error:", err);
    } finally {
      setIsOptimizing(false);
    }
  };

  const handleRunOptimization = async () => {
    setIsOptimizing(true);
    try {
      const freshCfg = await fetchDefaultConfig();
      setDefaultConfig(freshCfg);
      const optRes = await runOptimization(currentPolicy, "baseline");
      setOptimizationResult(optRes);
      setIsOptimizedActive(true);
    } catch (err) {
      console.error("Optimize execution error:", err);
    } finally {
      setIsOptimizing(false);
    }
  };

  const currentDisplaySnapshots =
    isOptimizedActive && optimizationResult?.snapshots
      ? optimizationResult.snapshots
      : baselineSnapshots;

  const currentSnapshot = currentDisplaySnapshots[selectedStep] || currentDisplaySnapshots[48];

  return (
    <div className="min-h-screen bg-[#0b0f19] text-gray-100 flex flex-col">
      {/* Top Header & Presets */}
      <Header
        currentScenario={currentScenario}
        currentPolicy={currentPolicy}
        onSelectPreset={handleSelectPreset}
        onRunOptimization={handleRunOptimization}
        isOptimizing={isOptimizing}
        onToggleCopilot={() => setIsCopilotOpen((prev) => !prev)}
        isCopilotOpen={isCopilotOpen}
        hasOptimized={!!optimizationResult}
        config={defaultConfig}
      />

      {/* Main Container */}
      <main className="flex-1 max-w-[1720px] w-full mx-auto px-4 lg:px-8 py-6">
        {/* Time Scrubber Bar: Interactive 96 Timestep Controller */}
        <div className="glass-panel rounded-2xl px-5 py-3.5 mb-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-sky-950 text-sky-400 border border-sky-800/60">
              <Clock className="h-4 w-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-white uppercase tracking-wider font-mono">
                  Digital Twin Time Scrubber:
                </span>
                <span className="text-sm font-bold text-sky-400 font-mono">
                  {currentSnapshot?.timestamp || "12:00"} (Interval #{selectedStep} of 96)
                </span>
              </div>
              <p className="text-[11px] text-gray-400">
                Drag slider to inspect virtual grid power flows, battery SOC, and carbon intensity at any 15-minute timestep.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto">
            <input
              type="range"
              min={0}
              max={95}
              value={selectedStep}
              onChange={(e) => setSelectedStep(Number(e.target.value))}
              className="w-full sm:w-64 h-2 bg-gray-800 rounded-lg appearance-none cursor-pointer accent-sky-400"
            />
            <div className="flex gap-1">
              <button
                onClick={() => setSelectedStep(48)}
                className="px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 text-[10px] font-mono text-gray-300"
                title="Jump to 12:00 Solar Peak"
              >
                12:00
              </button>
              <button
                onClick={() => setSelectedStep(76)}
                className="px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 text-[10px] font-mono text-gray-300"
                title="Jump to 19:00 Evening Peak"
              >
                19:00
              </button>
            </div>
          </div>
        </div>

        {/* Top Row: 5 Core KPI Cards */}
        <KpiCards
          currentSnapshot={currentSnapshot}
          summary={optimizationResult?.optimized_metrics || baselineSummary}
          deltas={optimizationResult?.deltas}
          isOptimized={isOptimizedActive}
          config={defaultConfig}
        />

        {/* Middle Panels: 24h Energy ComposedChart & Carbon / Tariff Chart */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-8">
            <EnergyProfileChart
              baselineSnapshots={baselineSnapshots}
              optimizedSnapshots={optimizationResult?.snapshots}
              isOptimizedActive={isOptimizedActive}
              config={defaultConfig}
            />
          </div>
          <div className="lg:col-span-4">
            <CarbonTariffChart snapshots={currentDisplaySnapshots} config={defaultConfig} />
          </div>
        </div>

        {/* Lower Panels: Baseline vs. Optimized Impact & Flexible Asset Timeline */}
        <ComparisonImpactPanel
          optimizationResult={optimizationResult}
          isOptimized={isOptimizedActive}
          onToggleOptimized={() => setIsOptimizedActive((prev) => !prev)}
          config={defaultConfig}
        />

        <ScheduleTimeline
          loads={flexibleLoads}
          isOptimized={isOptimizedActive}
          snapshots={currentDisplaySnapshots}
          config={defaultConfig}
        />
      </main>

      {/* Floating AI Energy Copilot Drawer */}
      <AICopilotDrawer
        isOpen={isCopilotOpen}
        onClose={() => setIsCopilotOpen(false)}
        onTriggerPreset={handleSelectPreset}
      />
    </div>
  );
}
