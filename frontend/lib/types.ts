export interface GridSnapshot {
  step: number;
  timestamp: string;
  demand_kw: number;
  solar_kw: number;
  grid_import_kw: number;
  grid_export_kw: number;
  battery_charge_kw: number;
  battery_discharge_kw: number;
  battery_soc_kwh: number;
  carbon_intensity_g_per_kwh: number;
  price_per_kwh: number;
  solar_direct_kw?: number;
  net_need_kw?: number;
  energy_balance_error?: number;
  residential_kw?: number;
  common_area_kw?: number;
  ev_kw?: number;
  datacenter_kw?: number;
  pump_kw?: number;
}

export interface GridSummary {
  total_demand_kwh: number;
  total_solar_kwh: number;
  total_grid_import_kwh: number;
  total_cost: number;
  total_co2e_kg: number;
  peak_grid_import_kw: number;
  peak_demand_kw: number;
}

export interface Asset {
  id: string;
  type: string;
  name: string;
  rated_power_kw: number;
  capacity_kwh?: number | null;
  flexibility_class: string;
}

export interface FlexibleLoad {
  id: string;
  asset_id: string;
  name: string;
  load_type: string;
  energy_required_kwh: number;
  earliest_start: number;
  latest_end: number;
  max_power_kw: number;
  priority?: number;
  interruptible?: boolean;
  scheduled_power?: number[];
}

export interface MetricDeltas {
  peak_reduction_kw: number;
  peak_reduction_pct: number;
  co2e_reduction_kg: number;
  co2e_reduction_pct: number;
  cost_reduction_currency: number;
  cost_reduction_pct: number;
  renewable_self_consumption_gain_pct: number;
}

export interface MetricSnapshot {
  total_demand_kwh: number;
  total_solar_kwh: number;
  total_grid_import_kwh: number;
  total_grid_export_kwh: number;
  peak_demand_kw: number;
  peak_grid_import_kw: number;
  total_cost: number;
  total_co2e_kg: number;
  renewable_self_consumption_pct: number;
  curtailment_pct: number;
  pcc_violation_count: number;
  soc_violation_count: number;
  max_energy_balance_error_kw: number;
}

export interface ConstraintAudit {
  hard_constraint_violations: number;
  pcc_violations: number;
  soc_violations: number;
  missed_deadlines: number;
  unserved_load_energy_kwh: number;
  is_feasible: boolean;
}

export interface OptimizationResponse {
  solver_status: string;
  objective_value: number;
  solve_time_seconds: number;
  peak_grid_import_kw: number;
  total_cost: number;
  total_co2e_kg: number;
  hard_constraint_violations: number;
  schedule_id: string;
  policy: string;
  deltas: MetricDeltas;
  baseline_metrics: MetricSnapshot;
  optimized_metrics: MetricSnapshot;
  constraint_audit: ConstraintAudit;
  snapshots?: GridSnapshot[];
  flexible_loads?: FlexibleLoad[];
}

export interface AgentToolCall {
  name: string;
  arguments: Record<string, any>;
  result?: string;
}

export interface AgentChatMessage {
  id: string;
  sender: "user" | "agent";
  text: string;
  tool_calls?: AgentToolCall[];
  timestamp: string;
}

export interface DefaultConfig {
  simulation: {
    timestep_minutes: number;
    horizon_steps: number;
    random_seed: number;
  };
  community: {
    apartments: number;
    ev_chargers: number;
    solar_capacity_kw: number;
    battery_capacity_kwh: number;
    battery_power_kw: number;
    pcc_limit_kw: number;
  };
  battery: {
    min_soc_pct: number;
    max_soc_pct: number;
    initial_soc_pct: number;
    charge_efficiency: number;
    discharge_efficiency: number;
  };
  flexible_loads: {
    ev: {
      charger_kw: number;
      min_energy_kwh: number;
      max_energy_kwh: number;
    };
    data_center: {
      flexible_power_kw: number;
      default_duration_hours: number;
      preferred_start_step: number;
    };
    water_pump: {
      power_kw: number;
      required_energy_kwh: number;
      preferred_start_step: number;
    };
  };
  common_area: {
    base_kw: number;
    peak_kw: number;
  };
  policy: Record<string, Record<string, number>>;
  carbon: {
    baseline_g_per_kwh: number;
    solar_day_reduction_factor: number;
    evening_peak_multiplier: number;
  };
  pricing: {
    currency: string;
    off_peak_rate: number;
    shoulder_rate: number;
    peak_rate: number;
  };
}

