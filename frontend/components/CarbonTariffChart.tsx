"use client";

import React from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ReferenceArea,
} from "recharts";
import { GridSnapshot, DefaultConfig } from "../lib/types";
import { Flame, DollarSign, Clock } from "lucide-react";

interface CarbonTariffChartProps {
  snapshots: GridSnapshot[];
  config?: DefaultConfig;
}

export const CarbonTariffChart: React.FC<CarbonTariffChartProps> = ({ snapshots, config }) => {
  const offPeakRate = config?.pricing?.off_peak_rate ?? 0.10;
  const shoulderRate = config?.pricing?.shoulder_rate ?? 0.15;
  const peakRate = config?.pricing?.peak_rate ?? 0.30;

  const chartData = snapshots.map((s) => ({
    time: s.timestamp,
    carbon: s.carbon_intensity_g_per_kwh,
    price: s.price_per_kwh,
    step: s.step,
  }));

  return (
    <div className="glass-panel rounded-2xl p-5 mb-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-3">
        <div>
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <Flame className="h-5 w-5 text-emerald-400" />
            24-Hour Grid Carbon Intensity & Dynamic TOU Tariff
          </h2>
          <p className="text-xs text-gray-400">
            Marginal grid emissions signal (gCO₂e/kWh) synchronized with utility Time-of-Use pricing ($/kWh)
          </p>
        </div>

        <div className="flex items-center gap-3 text-xs font-mono">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-950/60 border border-emerald-800/40 text-emerald-400">
            <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
            <span>Solar Valley: Clean</span>
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-red-950/60 border border-red-800/40 text-red-400">
            <span className="h-2 w-2 rounded-full bg-red-400"></span>
            <span>Evening Peak: ${peakRate.toFixed(2)}/kWh</span>
          </div>
        </div>
      </div>

      <div className="h-[220px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />

            <XAxis
              dataKey="time"
              stroke="#6b7280"
              fontSize={11}
              tickLine={false}
              interval={7}
            />

            {/* Left Axis: Carbon Intensity (gCO2e/kWh) */}
            <YAxis
              yAxisId="carbon"
              stroke="#10b981"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              domain={[150, 650]}
              unit=" g"
            />

            {/* Right Axis: TOU Tariff ($/kWh) */}
            <YAxis
              yAxisId="price"
              orientation="right"
              stroke="#c084fc"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              domain={[0.05, 0.35]}
              unit=" $"
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
                if (name === "carbon") return [`${Number(value).toFixed(0)} gCO₂e/kWh`, "Grid Carbon Intensity"];
                if (name === "price") return [`$${Number(value).toFixed(2)}/kWh`, "TOU Electricity Tariff"];
                return [value, name];
              }}
              labelFormatter={(label) => `Time: ${label}`}
            />

            <Legend
              verticalAlign="top"
              height={30}
              iconType="circle"
              wrapperStyle={{ fontSize: "12px", color: "#9ca3af" }}
            />

            {/* Carbon line (Emerald gradient/glow) */}
            <Line
              yAxisId="carbon"
              type="monotone"
              dataKey="carbon"
              name="carbon"
              stroke="#10b981"
              strokeWidth={2.5}
              dot={false}
            />

            {/* Price line (Stepped violet line) */}
            <Line
              yAxisId="price"
              type="stepAfter"
              dataKey="price"
              name="price"
              stroke="#c084fc"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-3 gap-2 mt-2 pt-2 border-t border-gray-800/80 text-center text-[11px] text-gray-400">
        <div>
          <span className="text-gray-200 font-semibold">Off-Peak (00:00–06:00):</span> ${offPeakRate.toFixed(2)}/kWh
        </div>
        <div>
          <span className="text-gray-200 font-semibold">Shoulder (06:00–16:00):</span> ${shoulderRate.toFixed(2)}/kWh
        </div>
        <div>
          <span className="text-gray-200 font-semibold">On-Peak (16:00–21:00):</span> ${peakRate.toFixed(2)}/kWh
        </div>
      </div>
    </div>
  );
};
