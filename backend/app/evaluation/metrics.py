"""
Evaluation Metrics & Scientific Baseline Comparison Service.
Section 21 of System Design Specification.
"""

from typing import List, Dict, Any, Union
import numpy as np


def compute_simulation_metrics(
    snapshots: List[Dict[str, Any]],
    pcc_limit_kw: float = 2500.0,
    dt_hours: float = 0.25
) -> Dict[str, Any]:
    """
    Computes absolute evaluation metrics for a single simulation run.
    Section 21.1:
      Peak demand = max_t(GridImportPower_t)
      Total energy imported = Σ_t(GridImportPower_t × Δt)
      Energy cost = Σ_t(GridImportEnergy_t × Price_t)
      CO2e = Σ_t(GridImportEnergy_t × CarbonIntensity_t)
      Renewable utilization = RenewableEnergyUsedLocally / RenewableEnergyGenerated
    """
    if not snapshots:
        return {}

    total_demand_kwh = sum(s["demand_kw"] * dt_hours for s in snapshots)
    total_solar_kwh = sum(s["solar_kw"] * dt_hours for s in snapshots)
    total_grid_import_kwh = sum(s["grid_import_kw"] * dt_hours for s in snapshots)
    total_grid_export_kwh = sum(s.get("grid_export_kw", 0.0) * dt_hours for s in snapshots)

    peak_demand_kw = max(s["demand_kw"] for s in snapshots)
    peak_grid_import_kw = max(s["grid_import_kw"] for s in snapshots)

    # Net cost accounting (grid import cost minus feed-in tariff export revenue)
    feed_in_tariff = 0.05
    total_cost = sum(
        (s["grid_import_kw"] * s["price_per_kwh"] - s.get("grid_export_kw", 0.0) * feed_in_tariff) * dt_hours
        for s in snapshots
    )
    total_co2e_kg = sum(
        s["grid_import_kw"] * dt_hours * s["carbon_intensity_g_per_kwh"] for s in snapshots
    ) / 1000.0

    # Solar local usage = solar directly consumed by demand + solar used to charge battery
    solar_direct_kwh = sum(s.get("solar_direct_kw", min(s["solar_kw"], s["demand_kw"])) * dt_hours for s in snapshots)
    solar_to_battery_kwh = sum(s.get("battery_charge_kw", 0.0) * dt_hours for s in snapshots)
    renewable_consumed_kwh = solar_direct_kwh + solar_to_battery_kwh
    
    # Solar curtailed = excess solar that neither went to demand, battery, nor exported
    solar_curtailed_kwh = max(0.0, total_solar_kwh - renewable_consumed_kwh - total_grid_export_kwh)
    
    renewable_self_consumption_pct = (renewable_consumed_kwh / max(0.001, total_solar_kwh)) * 100.0
    curtailment_pct = (solar_curtailed_kwh / max(0.001, total_solar_kwh)) * 100.0

    # Constraint checks
    pcc_violations = [s for s in snapshots if s["grid_import_kw"] > (pcc_limit_kw + 1e-3)]
    soc_violations = [
        s for s in snapshots
        if (s.get("battery_soc_kwh", 0.0) < (500.0 * 0.199) or s.get("battery_soc_kwh", 0.0) > (500.0 * 0.951))
    ]
    max_energy_balance_error = max([s.get("energy_balance_error", 0.0) for s in snapshots], default=0.0)

    return {
        "total_demand_kwh": round(total_demand_kwh, 2),
        "total_solar_kwh": round(total_solar_kwh, 2),
        "total_grid_import_kwh": round(total_grid_import_kwh, 2),
        "total_grid_export_kwh": round(total_grid_export_kwh, 2),
        "peak_demand_kw": round(peak_demand_kw, 2),
        "peak_grid_import_kw": round(peak_grid_import_kw, 2),
        "total_cost": round(total_cost, 2),
        "total_co2e_kg": round(total_co2e_kg, 2),
        "renewable_self_consumption_pct": round(min(100.0, renewable_self_consumption_pct), 2),
        "curtailment_pct": round(min(100.0, curtailment_pct), 2),
        "pcc_violation_count": len(pcc_violations),
        "soc_violation_count": len(soc_violations),
        "max_energy_balance_error_kw": round(max_energy_balance_error, 6)
    }


def evaluate_baseline_vs_optimized(
    baseline_run: Dict[str, Any],
    optimized_run: Dict[str, Any],
    pcc_limit_kw: float = 2500.0
) -> Dict[str, Any]:
    """
    Computes comparative deltas and reduction percentages adhering strictly to Section 21.1:
      Peak reduction (%) = (BaselinePeak - OptimizedPeak) / BaselinePeak * 100
      CO2e reduction (%) = (BaselineCO2e - OptimizedCO2e) / BaselineCO2e * 100
      Cost reduction (%) = (BaselineCost - OptimizedCost) / BaselineCost * 100
    Also audits constraint satisfaction (Section 21.2).
    """
    base_metrics = compute_simulation_metrics(baseline_run.get("snapshots", []), pcc_limit_kw=pcc_limit_kw)
    opt_metrics = compute_simulation_metrics(optimized_run.get("snapshots", []), pcc_limit_kw=pcc_limit_kw)

    # Reduction percentages
    b_peak = max(0.001, base_metrics["peak_grid_import_kw"])
    o_peak = opt_metrics["peak_grid_import_kw"]
    peak_reduction_pct = ((b_peak - o_peak) / b_peak) * 100.0

    b_co2 = max(0.001, base_metrics["total_co2e_kg"])
    o_co2 = opt_metrics["total_co2e_kg"]
    co2e_reduction_pct = ((b_co2 - o_co2) / b_co2) * 100.0

    b_cost = max(0.001, base_metrics["total_cost"])
    o_cost = opt_metrics["total_cost"]
    cost_reduction_pct = ((b_cost - o_cost) / b_cost) * 100.0

    # Check flexible load deadlines
    missed_deadlines = 0
    unserved_load_energy_kwh = 0.0
    opt_loads = optimized_run.get("flexible_loads", [])
    opt_snapshots = optimized_run.get("snapshots", [])

    for load in opt_loads:
        req_kwh = load.get("energy_required_kwh", 0.0)
        earliest = load.get("earliest_start", 0)
        deadline = load.get("latest_end", 95)
        
        # Check power assigned in opt_snapshots
        if load.get("load_type") == "ev":
            # For EV loads, if individual load scheduled_power is tracked or total ev energy delivered
            load_id = load.get("id")
            # If load contains individual scheduled power
            sched = load.get("scheduled_power", [])
            if sched and len(sched) > deadline:
                delivered = sum(sched[t] * 0.25 for t in range(earliest, deadline + 1))
                if delivered < (req_kwh - 0.05):
                    missed_deadlines += 1
                    unserved_load_energy_kwh += (req_kwh - delivered)

    hard_constraint_violations = (
        opt_metrics["pcc_violation_count"] +
        opt_metrics["soc_violation_count"] +
        missed_deadlines
    )

    return {
        "baseline": base_metrics,
        "optimized": opt_metrics,
        "deltas": {
            "peak_reduction_kw": round(b_peak - o_peak, 2),
            "peak_reduction_pct": round(peak_reduction_pct, 2),
            "co2e_reduction_kg": round(b_co2 - o_co2, 2),
            "co2e_reduction_pct": round(co2e_reduction_pct, 2),
            "cost_reduction_currency": round(b_cost - o_cost, 2),
            "cost_reduction_pct": round(cost_reduction_pct, 2),
            "renewable_self_consumption_gain_pct": round(
                opt_metrics["renewable_self_consumption_pct"] - base_metrics["renewable_self_consumption_pct"], 2
            )
        },
        "constraint_audit": {
            "hard_constraint_violations": hard_constraint_violations,
            "pcc_violations": opt_metrics["pcc_violation_count"],
            "soc_violations": opt_metrics["soc_violation_count"],
            "missed_deadlines": missed_deadlines,
            "unserved_load_energy_kwh": round(unserved_load_energy_kwh, 3),
            "is_feasible": (hard_constraint_violations == 0)
        }
    }
