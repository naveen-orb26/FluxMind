"use client";

import React, { useState } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ReferenceLine,
  CartesianGrid,
} from "recharts";
import { GridSnapshot, DefaultConfig } from "../lib/types";
import { Sun, Battery, Zap, Activity } from "lucide-react";

interface EnergyProfileChartProps {
  baselineSnapshots: GridSnapshot[];
  optimizedSnapshots?: GridSnapshot[];
  isOptimizedActive: boolean;
  config?: DefaultConfig;
}

export const EnergyProfileChart: React.FC<EnergyProfileChartProps> = ({
  baselineSnapshots,
  optimizedSnapshots,
  isOptimizedActive,
  config,
}) => {
  const [viewMode, setViewMode] = useState<"active" | "compare">("active");
  const pccLimit = config?.community?.pcc_limit_kw ?? 2500;

  const activeSnapshots =
    isOptimizedActive && optimizedSnapshots && optimizedSnapshots.length > 0
      ? optimizedSnapshots
      : baselineSnapshots;

  // Format data for chart
  const chartData = activeSnapshots.map((item, idx) => {
    const baseItem = baselineSnapshots[idx] || item;
    const optItem = optimizedSnapshots?.[idx] || item;

    // Battery net dispatch: positive for discharge (supplying energy), negative for charging (absorbing)
    const batteryNet = item.battery_discharge_kw - item.battery_charge_kw;

    return {
      step: item.step,
      time: item.timestamp,
      demand: item.demand_kw,
      solar: item.solar_kw,
      gridImport: item.grid_import_kw,
      batteryNet,
      batterySoc: item.battery_soc_kwh,
      baseImport: baseItem.grid_import_kw,
      optImport: optItem.grid_import_kw,
    };
  });

  return (
    <div className="glass-panel rounded-2xl p-5 mb-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <Activity className="h-5 w-5 text-sky-400" />
            24-Hour Community Energy Profile & DER Dispatch
          </h2>
          <p className="text-xs text-gray-400">
            96 intervals (15-min) • Conservation of Energy: Demand = Solar + BESS Dispatch + Grid Import
          </p>
        </div>

        {/* View mode toggle */}
        {optimizedSnapshots && (
          <div className="flex items-center gap-1 bg-gray-900/80 p-1 rounded-xl border border-gray-800 text-xs">
            <button
              onClick={() => setViewMode("active")}
              className={`px-3 py-1 rounded-lg font-medium transition-all ${
                viewMode === "active"
                  ? "bg-sky-600 text-white shadow-sm"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              {isOptimizedActive ? "Optimized Schedule" : "Baseline Schedule"}
            </button>
            <button
              onClick={() => setViewMode("compare")}
              className={`px-3 py-1 rounded-lg font-medium transition-all ${
                viewMode === "compare"
                  ? "bg-emerald-600 text-white shadow-sm"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              Compare Import Curves
            </button>
          </div>
        )}
      </div>

      {/* Chart container */}
      <div className="h-[320px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              {/* Solar gradient */}
              <linearGradient id="solarGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#eab308" stopOpacity={0.4} />
                <stop offset="95%" stopColor="#eab308" stopOpacity={0.0} />
              </linearGradient>
              {/* Demand gradient */}
              <linearGradient id="demandGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#38bdf8" stopOpacity={0.0} />
              </linearGradient>
              {/* Grid import gradient */}
              <linearGradient id="gridImportGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#0ea5e9" stopOpacity={0.45} />
                <stop offset="95%" stopColor="#0ea5e9" stopOpacity={0.05} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />

            <XAxis
              dataKey="time"
              stroke="#6b7280"
              fontSize={11}
              tickLine={false}
              interval={7} // show every 2 hours (8 intervals of 15m)
            />

            <YAxis
              stroke="#6b7280"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              unit=" kW"
            />

            <Tooltip
              contentStyle={{
                backgroundColor: "#111827",
                borderColor: "#374151",
                borderRadius: "0.75rem",
                boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.5)",
                fontSize: "12px",
              }}
              formatter={(value: any, name: string) => {
                const val = typeof value === "number" ? `${value.toFixed(1)} kW` : value;
                if (name === "demand") return [val, "Community Demand"];
                if (name === "solar") return [val, "Rooftop Solar PV"];
                if (name === "gridImport") return [val, "Grid Import"];
                if (name === "batteryNet") {
                  const num = Number(value);
                  return num >= 0
                    ? [`+${num.toFixed(1)} kW`, "BESS Discharge"]
                    : [`${num.toFixed(1)} kW`, "BESS Charging"];
                }
                if (name === "baseImport") return [val, "Baseline Grid Import"];
                if (name === "optImport") return [val, "Optimized Grid Import"];
                return [val, name];
              }}
              labelFormatter={(label) => `Time: ${label} (15-min interval)`}
            />

            <Legend
              verticalAlign="top"
              height={36}
              iconType="circle"
              wrapperStyle={{ fontSize: "12px", color: "#9ca3af" }}
            />

            {/* PCC Physical Limit line */}
            <ReferenceLine
              y={pccLimit}
              stroke="#ef4444"
              strokeDasharray="4 4"
              label={{
                value: `PCC Limit: ${pccLimit} kW`,
                fill: "#ef4444",
                fontSize: 10,
                position: "insideTopRight",
              }}
            />

            {viewMode === "active" ? (
              <>
                {/* Rooftop Solar */}
                <Area
                  type="monotone"
                  dataKey="solar"
                  name="solar"
                  fill="url(#solarGradient)"
                  stroke="#eab308"
                  strokeWidth={2}
                />

                {/* Total Demand */}
                <Line
                  type="monotone"
                  dataKey="demand"
                  name="demand"
                  stroke="#94a3b8"
                  strokeWidth={2}
                  strokeDasharray="3 3"
                  dot={false}
                />

                {/* Grid Import */}
                <Area
                  type="monotone"
                  dataKey="gridImport"
                  name="gridImport"
                  fill="url(#gridImportGradient)"
                  stroke="#0ea5e9"
                  strokeWidth={2.5}
                />

                {/* Battery Net Dispatch Bar */}
                <Bar
                  dataKey="batteryNet"
                  name="batteryNet"
                  fill="#8b5cf6"
                  opacity={0.85}
                  barSize={4}
                />
              </>
            ) : (
              <>
                {/* Baseline vs Optimized Overlay */}
                <Area
                  type="monotone"
                  dataKey="baseImport"
                  name="baseImport"
                  fill="rgba(239, 68, 68, 0.15)"
                  stroke="#ef4444"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                />
                <Area
                  type="monotone"
                  dataKey="optImport"
                  name="optImport"
                  fill="rgba(16, 185, 129, 0.25)"
                  stroke="#10b981"
                  strokeWidth={2.5}
                />
              </>
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Legend summary pills */}
      <div className="flex flex-wrap items-center justify-between text-[11px] text-gray-400 mt-2 pt-2 border-t border-gray-800/80">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-solar inline-block"></span> Solar Surplus Window (10:00–15:00)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-purple-500 inline-block"></span> BESS Evening Shaving (18:00–21:00)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-sky-400 inline-block"></span> Net Grid Inflow
          </span>
        </div>
        <span className="font-mono text-gray-400">Fixed Seed=42 • 100% Deterministic Reproducibility</span>
      </div>
    </div>
  );
};
