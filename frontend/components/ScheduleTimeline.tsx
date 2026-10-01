"use client";

import React from "react";
import { Clock, Car, Server, Droplets, ArrowRight } from "lucide-react";
import { FlexibleLoad, GridSnapshot, DefaultConfig } from "../lib/types";

interface ScheduleTimelineProps {
  loads: FlexibleLoad[];
  isOptimized: boolean;
  snapshots?: GridSnapshot[];
  config?: DefaultConfig;
}

export const ScheduleTimeline: React.FC<ScheduleTimelineProps> = ({
  loads,
  isOptimized,
  snapshots,
  config,
}) => {
  const evCount = config?.community?.ev_chargers ?? 40;
  const dcKw = config?.flexible_loads?.data_center?.flexible_power_kw ?? 200;
  const dcHours = config?.flexible_loads?.data_center?.default_duration_hours ?? 2;
  const dcKwh = dcKw * dcHours;
  const pumpKw = config?.flexible_loads?.water_pump?.power_kw ?? 50;
  const pumpKwh = config?.flexible_loads?.water_pump?.required_energy_kwh ?? 50;
  const offPeakRate = config?.pricing?.off_peak_rate ?? 0.10;
  // 96 intervals, each represented by a small block or bar
  // Time markers every 4 hours (16 steps)
  const timeMarkers = [
    { step: 0, label: "00:00" },
    { step: 16, label: "04:00" },
    { step: 32, label: "08:00" },
    { step: 48, label: "12:00" },
    { step: 64, label: "16:00" },
    { step: 80, label: "20:00" },
    { step: 95, label: "23:45" },
  ];

  // Helper to format step to HH:MM
  const stepToTime = (s: number) => {
    const h = Math.floor(s / 4);
    const m = (s % 4) * 15;
    return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}`;
  };

  return (
    <div className="glass-panel rounded-2xl p-5 mb-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <Clock className="h-5 w-5 text-sky-400" />
            Flexible Workload Gantt Schedule Timeline
          </h2>
          <p className="text-xs text-gray-400">
            Departure deadlines, preferred windows, and optimized DER dispatch across 96 intervals
          </p>
        </div>

        <div className="flex items-center gap-4 text-xs font-mono text-gray-400">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded bg-sky-500"></span> Active Scheduled Power
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded border border-dashed border-gray-500"></span> Feasible Window
          </span>
        </div>
      </div>

      {/* Timeline Grid Header */}
      <div className="relative w-full h-6 border-b border-gray-800 text-[10px] text-gray-400 font-mono mb-2">
        {timeMarkers.map((m) => (
          <div
            key={m.step}
            className="absolute -translate-x-1/2"
            style={{ left: `${(m.step / 95) * 100}%` }}
          >
            {m.label}
          </div>
        ))}
      </div>

      {/* Asset Schedules */}
      <div className="space-y-4">
        {/* 1. Level-2 EV Fleet Chargers (40 chargers / ~240 kWh flexible) */}
        <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-3">
          <div className="flex items-center justify-between text-xs mb-2">
            <div className="flex items-center gap-2">
              <div className="p-1 rounded bg-sky-950 text-sky-400">
                <Car className="h-4 w-4" />
              </div>
              <span className="font-semibold text-white">{evCount} Level-2 EV Chargers (Fleet Aggregate)</span>
              <span className="text-[10px] text-gray-400 font-mono">
                {isOptimized
                  ? "Optimized: Shifted into solar surplus & overnight off-peak"
                  : "Baseline: Immediate uncoordinated charging on arrival"}
              </span>
            </div>
            <span className="text-[11px] font-mono text-sky-400">
              {isOptimized ? "11:00–14:00 & 22:00–04:00" : "18:00–21:00 (Peak Surge)"}
            </span>
          </div>

          {/* Bar timeline */}
          <div className="relative w-full h-7 bg-gray-950 rounded-lg overflow-hidden border border-gray-800/80">
            {/* Feasible window range */}
            <div
              className="absolute top-0 bottom-0 bg-gray-800/30 border-x border-gray-700/60"
              style={{ left: "45%", width: "50%" }}
            />

            {/* Scheduled charging window */}
            {isOptimized ? (
              <>
                {/* Solar midday charging */}
                <div
                  className="absolute top-1 bottom-1 bg-gradient-to-r from-sky-500 to-cyan-500 rounded text-[10px] text-black font-bold flex items-center justify-center shadow"
                  style={{ left: "45%", width: "16%" }}
                >
                  Solar Shift
                </div>
                {/* Overnight off-peak charging */}
                <div
                  className="absolute top-1 bottom-1 bg-sky-600/80 rounded text-[10px] text-white font-medium flex items-center justify-center"
                  style={{ left: "88%", width: "12%" }}
                >
                  Off-Peak
                </div>
              </>
            ) : (
              <div
                className="absolute top-1 bottom-1 bg-gradient-to-r from-red-500 to-amber-500 rounded text-[10px] text-white font-bold flex items-center justify-center shadow-lg"
                style={{ left: "70%", width: "20%" }}
              >
                Uncoordinated Evening Peak (18:00-21:00)
              </div>
            )}
          </div>
          <div className="flex justify-between text-[10px] text-gray-400 font-mono mt-1">
            <span>Arrivals start: 16:00 (Step 64)</span>
            <span>Departure Deadline: 08:00 Next Morning (100% Satisfied)</span>
          </div>
        </div>

        {/* 2. AI Data Center Batch Cluster */}
        <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-3">
          <div className="flex items-center justify-between text-xs mb-2">
            <div className="flex items-center gap-2">
              <div className="p-1 rounded bg-purple-950 text-purple-400">
                <Server className="h-4 w-4" />
              </div>
              <span className="font-semibold text-white">AI Data Center Batch Compute ({dcKw} kW / {dcKwh} kWh)</span>
              <span className="text-[10px] text-gray-400 font-mono">
                {isOptimized ? "Optimized: Clean Solar Valley" : "Baseline: Preferred Window"}
              </span>
            </div>
            <span className="text-[11px] font-mono text-purple-400">
              {isOptimized ? "12:00–14:00 (Lowest Carbon)" : "10:00–12:00 (Default)"}
            </span>
          </div>

          <div className="relative w-full h-7 bg-gray-950 rounded-lg overflow-hidden border border-gray-800/80">
            {/* Feasible window */}
            <div
              className="absolute top-0 bottom-0 bg-gray-800/30 border-x border-gray-700/60"
              style={{ left: "33%", width: "35%" }}
            />

            {/* Scheduled window */}
            <div
              className={`absolute top-1 bottom-1 rounded text-[10px] font-bold flex items-center justify-center shadow transition-all ${
                isOptimized
                  ? "bg-gradient-to-r from-purple-500 to-indigo-500 text-white"
                  : "bg-gray-700 text-gray-300"
              }`}
              style={{ left: isOptimized ? "48%" : "40%", width: "8.3%" }} // 8 steps = 8.3%
            >
              {dcKw} kW Batch ({dcHours}h)
            </div>
          </div>
          <div className="flex justify-between text-[10px] text-gray-400 font-mono mt-1">
            <span>Window Open: 08:00 (Step 32)</span>
            <span>Batch Deadline: 16:00 (Step 64)</span>
          </div>
        </div>

        {/* 3. Water Reservoir Pump */}
        <div className="bg-gray-900/50 border border-gray-800 rounded-xl p-3">
          <div className="flex items-center justify-between text-xs mb-2">
            <div className="flex items-center gap-2">
              <div className="p-1 rounded bg-cyan-950 text-cyan-400">
                <Droplets className="h-4 w-4" />
              </div>
              <span className="font-semibold text-white">Municipal Water Reservoir Pump ({pumpKw} kW / {pumpKwh} kWh)</span>
              <span className="text-[10px] text-gray-400 font-mono">
                {isOptimized ? "Optimized: Lowest Tariff Off-Peak" : "Baseline: Fixed 04:00 Window"}
              </span>
            </div>
            <span className="text-[11px] font-mono text-cyan-400">
              03:00–04:00 (${offPeakRate.toFixed(2)}/kWh)
            </span>
          </div>

          <div className="relative w-full h-7 bg-gray-950 rounded-lg overflow-hidden border border-gray-800/80">
            {/* Feasible window */}
            <div
              className="absolute top-0 bottom-0 bg-gray-800/30 border-x border-gray-700/60"
              style={{ left: "8%", width: "25%" }}
            />

            {/* Scheduled window (4 steps = 4.1%) */}
            <div
              className="absolute top-1 bottom-1 bg-gradient-to-r from-cyan-500 to-teal-500 rounded text-[10px] text-black font-bold flex items-center justify-center shadow"
              style={{ left: "12%", width: "4.2%" }}
            >
              {pumpKw} kW (1h)
            </div>
          </div>
          <div className="flex justify-between text-[10px] text-gray-400 font-mono mt-1">
            <span>Allowed Window: 02:00–08:00</span>
            <span>Required: {pumpKwh} kWh Full Reservoir Level</span>
          </div>
        </div>
      </div>
    </div>
  );
};
