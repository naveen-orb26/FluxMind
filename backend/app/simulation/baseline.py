from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
from .loads import FlexibleLoad
from .battery import BatteryStorage
from .grid import GridSnapshot, compute_interval_balance


class BaselineScheduler:
    """
    Deterministic Baseline Scheduler according to Section 11.
    Executes:
    1. Unmodified apartment and common area base loads.
    2. Naive EV charging on arrival at max rated power until required energy is met.
    3. Fixed preferred-hour data-center batch workload execution.
    4. Default fixed-time water pump execution.
    5. Rule-based battery dispatch:
       - Absorbs excess rooftop solar surplus.
       - Discharges during evening peak (18:00 - 21:00) to serve community net load.
       - Strictly no simultaneous charge/discharge.
    6. No carbon-aware optimization; no cross-asset coordination.
    """

    def __init__(
        self,
        residential_kw: List[float],
        common_area_kw: List[float],
        flexible_loads: List[FlexibleLoad],
        solar_profile: List[float],
        carbon_profile: List[float],
        price_profile: List[float],
        battery: BatteryStorage,
        pcc_limit_kw: float = 2500.0,
        horizon_steps: int = 96,
        timestep_hours: float = 0.25,
        start_time_iso: str = "2026-09-30T00:00:00"
    ):
        self.residential_kw = residential_kw
        self.common_area_kw = common_area_kw
        self.flexible_loads = flexible_loads
        self.solar_profile = solar_profile
        self.carbon_profile = carbon_profile
        self.price_profile = price_profile
        self.battery = battery
        self.pcc_limit_kw = pcc_limit_kw
        self.horizon_steps = horizon_steps
        self.dt = timestep_hours
        self.start_time = datetime.fromisoformat(start_time_iso)

    def run(self) -> Tuple[List[GridSnapshot], Dict[str, Any]]:
        snapshots: List[GridSnapshot] = []

        # Track delivered energy per flexible load
        energy_delivered: Dict[str, float] = {load.id: 0.0 for load in self.flexible_loads}
        load_power_history: Dict[str, List[float]] = {load.id: [0.0] * self.horizon_steps for load in self.flexible_loads}

        for step in range(self.horizon_steps):
            step_time = self.start_time + timedelta(minutes=step * 15)
            timestamp_str = step_time.strftime("%H:%M")

            res_kw = round(self.residential_kw[step], 3)
            common_kw = round(self.common_area_kw[step], 3)
            solar_kw = round(self.solar_profile[step], 3)
            carbon_val = round(self.carbon_profile[step], 2)
            price_val = round(self.price_profile[step], 4)

            ev_step_kw = 0.0
            dc_step_kw = 0.0
            pump_step_kw = 0.0

            # 1. Flexible load naive execution
            for load in self.flexible_loads:
                if step >= load.earliest_start and energy_delivered[load.id] < load.energy_required_kwh:
                    remaining_energy = load.energy_required_kwh - energy_delivered[load.id]
                    # Deliver up to max_power_kw for this interval
                    power_kw = round(min(load.max_power_kw, remaining_energy / self.dt), 3)
                    energy_delivered[load.id] += power_kw * self.dt
                    load_power_history[load.id][step] = power_kw

                    if load.load_type == "ev":
                        ev_step_kw += power_kw
                    elif load.load_type == "data_center":
                        dc_step_kw += power_kw
                    elif load.load_type == "water_pump":
                        pump_step_kw += power_kw

            ev_step_kw = round(ev_step_kw, 3)
            dc_step_kw = round(dc_step_kw, 3)
            pump_step_kw = round(pump_step_kw, 3)

            # Total current community demand before battery dispatch
            community_demand_kw = round(res_kw + ev_step_kw + dc_step_kw + pump_step_kw + common_kw, 3)

            # 2. Battery dispatch logic (Section 11, Rule 5)
            # Direct solar usage meets community demand first
            solar_direct = round(min(solar_kw, community_demand_kw), 3)
            solar_surplus = round(max(0.0, solar_kw - solar_direct), 3)

            charge_target = 0.0
            discharge_target = 0.0

            # Condition A: Surplus solar available -> charge battery
            if solar_surplus > 0.0:
                max_charge = self.battery.get_max_charge_power()
                charge_target = min(solar_surplus, max_charge)
                discharge_target = 0.0

            # Condition B: Evening peak (18:00 to 21:00 -> steps 72 to 83) -> discharge battery
            elif 72 <= step < 84:
                remaining_demand = round(community_demand_kw - solar_direct, 3)
                max_discharge = self.battery.get_max_discharge_power()
                discharge_target = min(remaining_demand, max_discharge)
                charge_target = 0.0

            # Step physical battery model
            actual_charge, actual_discharge, new_soc = self.battery.step(charge_target, discharge_target)

            # 3. Compute exact energy balance & grid interaction
            snapshot = compute_interval_balance(
                step=step,
                timestamp=timestamp_str,
                residential_kw=res_kw,
                ev_kw=ev_step_kw,
                datacenter_kw=dc_step_kw,
                pump_kw=pump_step_kw,
                common_area_kw=common_kw,
                solar_kw=solar_kw,
                battery_charge_kw=actual_charge,
                battery_discharge_kw=actual_discharge,
                battery_soc_kwh=new_soc,
                battery_capacity_kwh=self.battery.config.capacity_kwh,
                carbon_intensity_g_per_kwh=carbon_val,
                price_per_kwh=price_val,
                pcc_limit_kw=self.pcc_limit_kw,
                allow_export=True
            )
            snapshots.append(snapshot)

        # Update flexible loads scheduled power
        for load in self.flexible_loads:
            load.scheduled_power = load_power_history[load.id]

        summary = self._compute_summary_metrics(snapshots, energy_delivered)
        return snapshots, summary

    def _compute_summary_metrics(
        self,
        snapshots: List[GridSnapshot],
        energy_delivered: Dict[str, float]
    ) -> Dict[str, Any]:
        dt = self.dt
        total_demand_kwh = sum(s.demand_kw * dt for s in snapshots)
        total_solar_kwh = sum(s.solar_kw * dt for s in snapshots)
        total_grid_import_kwh = sum(s.grid_import_kw * dt for s in snapshots)
        total_grid_export_kwh = sum(s.grid_export_kw * dt for s in snapshots)
        peak_grid_import_kw = max(s.grid_import_kw for s in snapshots)
        peak_demand_kw = max(s.demand_kw for s in snapshots)

        # Energy cost = sum(GridImport_t * dt * Price_t)
        total_cost = sum(s.grid_import_kw * dt * s.price_per_kwh for s in snapshots)
        # Operational CO2e = sum(GridImport_t * dt * Carbon_t) / 1000.0 (kg)
        total_co2e_kg = sum(s.grid_import_kw * dt * s.carbon_intensity_g_per_kwh for s in snapshots) / 1000.0

        solar_direct_kwh = sum(s.solar_direct_kw * dt for s in snapshots)
        solar_to_battery_kwh = sum(s.battery_charge_kw * dt for s in snapshots)
        renewable_used_kwh = solar_direct_kwh + solar_to_battery_kwh
        renewable_utilization_pct = (renewable_used_kwh / max(1.0, total_solar_kwh)) * 100.0

        pcc_violations = sum(1 for s in snapshots if s.pcc_violation)

        # Check deadline satisfaction
        ev_missed_deadlines = 0
        for load in self.flexible_loads:
            if energy_delivered.get(load.id, 0.0) < (load.energy_required_kwh - 0.01):
                ev_missed_deadlines += 1

        return {
            "total_demand_kwh": round(total_demand_kwh, 2),
            "total_solar_kwh": round(total_solar_kwh, 2),
            "total_grid_import_kwh": round(total_grid_import_kwh, 2),
            "total_grid_export_kwh": round(total_grid_export_kwh, 2),
            "peak_grid_import_kw": round(peak_grid_import_kw, 2),
            "peak_demand_kw": round(peak_demand_kw, 2),
            "total_cost": round(total_cost, 2),
            "total_co2e_kg": round(total_co2e_kg, 2),
            "renewable_utilization_pct": round(min(100.0, renewable_utilization_pct), 2),
            "pcc_violations": pcc_violations,
            "unmet_flexible_loads": ev_missed_deadlines
        }
