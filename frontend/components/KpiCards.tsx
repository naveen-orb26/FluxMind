"use client";

import React from "react";
import {
  Activity,
  Flame,
  Sun,
  BatteryCharging,
  TrendingDown,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { GridSnapshot, GridSummary, MetricDeltas, DefaultConfig } from "../lib/types";

interface KpiCardsProps {
  currentSnapshot?: GridSnapshot;
  summary?: GridSummary;
  deltas?: MetricDeltas | null;
  isOptimized: boolean;
  config?: DefaultConfig;
}

export const KpiCards: React.FC<KpiCardsProps> = ({
  currentSnapshot,
  summary,
  deltas,
  isOptimized,
  config,
}) => {
  const pccLimit = config?.community?.pcc_limit_kw ?? 2500; // kW
  const solarCapacityKw = config?.community?.solar_capacity_kw ?? 250;
  const batteryCapacityKwh = config?.community?.battery_capacity_kwh ?? 500;
  const minSocPct = config?.battery?.min_soc_pct ?? 20;
  const maxSocPct = config?.battery?.max_soc_pct ?? 95;
  const baselineCarbon = config?.carbon?.baseline_g_per_kwh ?? 450;

  const currentImport = currentSnapshot?.grid_import_kw ?? 0;
  const currentDemand = currentSnapshot?.demand_kw ?? 0;
  const peakImport = summary?.peak_grid_import_kw ?? 0;
  const currentSolar = currentSnapshot?.solar_kw ?? 0;
  const currentCarbon = currentSnapshot?.carbon_intensity_g_per_kwh ?? baselineCarbon;
  const batterySocKwh = currentSnapshot?.battery_soc_kwh ?? (batteryCapacityKwh * 0.5);
  const batterySocPct = Math.round((batterySocKwh / batteryCapacityKwh) * 100);
  const batteryCharge = currentSnapshot?.battery_charge_kw ?? 0;
  const batteryDischarge = currentSnapshot?.battery_discharge_kw ?? 0;

  // PCC capacity percentage
  const pccUtilizationPct = Math.min(100, Math.round((currentImport / pccLimit) * 100));

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5 mb-6">
      {/* 1. Current Grid Import & Load */}
      <div className="glass-panel glass-panel-hover rounded-2xl p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between text-gray-400 mb-1">
          <span className="text-xs font-semibold uppercase tracking-wider">Grid Import / Load</span>
          <Zap className="h-4 w-4 text-sky-400" />
        </div>
        <div className="my-1">
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-bold text-white tracking-tight">{currentImport.toFixed(1)}</span>
            <span className="text-xs text-gray-400 font-mono">kW</span>
          </div>
          <p className="text-[11px] text-gray-400 mt-0.5">
            Community Demand: <span className="text-gray-200 font-mono font-medium">{currentDemand} kW</span>
          </p>
        </div>
        <div className="mt-2">
          <div className="flex justify-between text-[10px] text-gray-400 mb-1 font-mono">
            <span>PCC Headroom</span>
            <span>{pccUtilizationPct}% of {(pccLimit / 1000).toFixed(1)} MW</span>
          </div>
          <div className="w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                pccUtilizationPct > 80
                  ? "bg-red-500"
                  : pccUtilizationPct > 50
                  ? "bg-amber-400"
                  : "bg-sky-400"
              }`}
              style={{ width: `${pccUtilizationPct}%` }}
            />
          </div>
        </div>
      </div>

      {/* 2. 24h Peak Demand */}
      <div className="glass-panel glass-panel-hover rounded-2xl p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between text-gray-400 mb-1">
          <span className="text-xs font-semibold uppercase tracking-wider">24h Peak Grid Demand</span>
          <Activity className="h-4 w-4 text-emerald-400" />
        </div>
        <div className="my-1">
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-bold text-white tracking-tight">{peakImport.toFixed(0)}</span>
            <span className="text-xs text-gray-400 font-mono">kW</span>
          </div>
          {isOptimized && deltas && deltas.peak_reduction_kw > 0 ? (
            <div className="flex items-center gap-1 text-[11px] font-semibold text-emerald-400 mt-1">
              <TrendingDown className="h-3.5 w-3.5" />
              <span>Shaved -{deltas.peak_reduction_kw.toFixed(0)} kW (-{deltas.peak_reduction_pct}%)</span>
            </div>
          ) : (
            <p className="text-[11px] text-gray-400 mt-1">
              Baseline Uncoordinated Peak
            </p>
          )}
        </div>
        <div className="text-[10px] font-mono text-gray-400 flex items-center justify-between border-t border-gray-800/80 pt-1.5">
          <span>Max PCC Capacity</span>
          <span className="text-gray-300 font-semibold">{pccLimit} kW Limit</span>
        </div>
      </div>

      {/* 3. Carbon Intensity */}
      <div className="glass-panel glass-panel-hover rounded-2xl p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between text-gray-400 mb-1">
          <span className="text-xs font-semibold uppercase tracking-wider">Carbon Intensity</span>
          <Flame className="h-4 w-4 text-amber-400" />
        </div>
        <div className="my-1">
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-bold text-white tracking-tight">{currentCarbon}</span>
            <span className="text-xs text-gray-400 font-mono">gCO₂e/kWh</span>
          </div>
          <div className="mt-1">
            <span
              className={`text-[10px] font-semibold px-2 py-0.5 rounded-full inline-block ${
                currentCarbon < 260
                  ? "bg-emerald-950 text-emerald-400 border border-emerald-800/50"
                  : currentCarbon > 500
                  ? "bg-red-950 text-red-400 border border-red-800/50"
                  : "bg-amber-950 text-amber-400 border border-amber-800/50"
              }`}
            >
              {currentCarbon < 260
                ? "Clean Solar Valley"
                : currentCarbon > 500
                ? "Dirty Evening Peak"
                : "Average Grid Mix"}
            </span>
          </div>
        </div>
        <div className="text-[10px] font-mono text-gray-400 flex items-center justify-between border-t border-gray-800/80 pt-1.5">
          <span>Est. 24h Emissions</span>
          <span className="text-gray-300 font-semibold">{summary?.total_co2e_kg ?? 0} kg</span>
        </div>
      </div>

      {/* 4. Solar Output */}
      <div className="glass-panel glass-panel-hover rounded-2xl p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between text-gray-400 mb-1">
          <span className="text-xs font-semibold uppercase tracking-wider">Rooftop Solar PV</span>
          <Sun className="h-4 w-4 text-solar" />
        </div>
        <div className="my-1">
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-bold text-solar tracking-tight">{currentSolar.toFixed(1)}</span>
            <span className="text-xs text-gray-400 font-mono">kW</span>
          </div>
          <p className="text-[11px] text-gray-400 mt-1">
            Array Capacity: <span className="text-gray-200 font-mono">{solarCapacityKw} kWp</span>
          </p>
        </div>
        <div className="text-[10px] font-mono text-gray-400 flex items-center justify-between border-t border-gray-800/80 pt-1.5">
          <span>Daily Generation</span>
          <span className="text-solar font-semibold">{summary?.total_solar_kwh ?? 0} kWh</span>
        </div>
      </div>

      {/* 5. Battery SOC */}
      <div className="glass-panel glass-panel-hover rounded-2xl p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between text-gray-400 mb-1">
          <span className="text-xs font-semibold uppercase tracking-wider">Community BESS</span>
          <BatteryCharging className="h-4 w-4 text-battery" />
        </div>
        <div className="my-1">
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-bold text-white tracking-tight">{batterySocPct}%</span>
            <span className="text-xs text-gray-400 font-mono">({batterySocKwh.toFixed(0)} / {batteryCapacityKwh} kWh)</span>
          </div>
          <div className="flex items-center gap-1.5 text-[11px] text-gray-300 mt-1">
            {batteryCharge > 0 ? (
              <span className="text-emerald-400 font-medium">Charging: +{batteryCharge.toFixed(1)} kW</span>
            ) : batteryDischarge > 0 ? (
              <span className="text-purple-400 font-medium">Discharging: -{batteryDischarge.toFixed(1)} kW</span>
            ) : (
              <span className="text-gray-400">Idle Reserve</span>
            )}
          </div>
        </div>
        <div className="mt-1">
          <div className="w-full bg-gray-800 rounded-full h-1.5 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-purple-500 to-indigo-500 transition-all duration-500"
              style={{ width: `${batterySocPct}%` }}
            />
          </div>
          <div className="flex justify-between text-[9px] text-gray-400 font-mono mt-1">
            <span>{minSocPct}% Reserve</span>
            <span>{maxSocPct}% Max</span>
          </div>
        </div>
      </div>
    </div>
  );
};
