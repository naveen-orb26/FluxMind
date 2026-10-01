import time
from typing import Dict, Any
from ortools.sat.python import cp_model

from .model import OptimizationResult
from .constraints import apply_hard_constraints
from ..simulation.simulator import engine

def solve_schedule(problem_spec: Dict[str, Any]) -> Dict[str, Any]:
    """Solves multi-objective DER schedule using OR-Tools CP-SAT."""
    start_time = time.time()
    
    run_id = problem_spec["run_id"]
    scenario_name = problem_spec.get("scenario_name", "baseline")
    policy = problem_spec.get("policy", "BALANCED")
    overrides = problem_spec.get("overrides", None)
    
    sim_data = engine.run_baseline_simulation(run_id=run_id + "_base", scenario_name=scenario_name, overrides=overrides)
    horizon_steps = sim_data["horizon_steps"]
    
    model = cp_model.CpModel()
    scale_factor = 1000
    
    grid_import = []
    grid_export = []
    bat_charge = []
    bat_discharge = []
    bat_soc = []
    is_charging = []
    
    ev_power = {load["id"]: [] for load in sim_data["flexible_loads"] if load["load_type"] == "ev"}
    dc_power = []
    pump_power = []
    
    bat_cfg = engine.default_config.get("battery", {})
    cap_kwh = float(engine.default_config.get("community", {}).get("battery_capacity_kwh", 500.0))
    pcc_limit = float(engine.default_config.get("community", {}).get("pcc_limit_kw", 2500.0))
    max_p_scaled = int(float(engine.default_config.get("community", {}).get("battery_power_kw", 250.0)) * scale_factor)
    
    min_soc_scaled = int(cap_kwh * (bat_cfg.get("min_soc_pct", 20.0) / 100.0) * scale_factor)
    max_soc_scaled = int(cap_kwh * (bat_cfg.get("max_soc_pct", 95.0) / 100.0) * scale_factor)
    pcc_limit_scaled = int(pcc_limit * scale_factor)
    
    for t in range(horizon_steps):
        grid_import.append(model.NewIntVar(0, pcc_limit_scaled, f"grid_import_{t}"))
        grid_export.append(model.NewIntVar(0, pcc_limit_scaled, f"grid_export_{t}"))
        
        bat_charge.append(model.NewIntVar(0, max_p_scaled, f"bat_charge_{t}"))
        bat_discharge.append(model.NewIntVar(0, max_p_scaled, f"bat_discharge_{t}"))
        bat_soc.append(model.NewIntVar(min_soc_scaled, max_soc_scaled, f"bat_soc_{t}"))
        is_charging.append(model.NewBoolVar(f"is_charging_{t}"))
        
        dc_power_kw = float(engine.default_config.get("flexible_loads", {}).get("data_center", {}).get("flexible_power_kw", 200.0))
        pump_power_kw = float(engine.default_config.get("flexible_loads", {}).get("water_pump", {}).get("power_kw", 50.0))
        dc_limit_scaled = int(dc_power_kw * scale_factor)
        pump_limit_scaled = int(pump_power_kw * scale_factor)
        dc_power.append(model.NewIntVar(0, dc_limit_scaled, f"dc_power_{t}"))
        pump_power.append(model.NewIntVar(0, pump_limit_scaled, f"pump_power_{t}"))
        
        for load in sim_data["flexible_loads"]:
            if load["load_type"] == "ev":
                max_ev_kw_scaled = int(load["max_power_kw"] * scale_factor)
                ev_power[load["id"]].append(model.NewIntVar(0, max_ev_kw_scaled, f"ev_{load['id']}_{t}"))

    vars_dict = {
        "grid_import": grid_import,
        "grid_export": grid_export,
        "bat_charge": bat_charge,
        "bat_discharge": bat_discharge,
        "bat_soc": bat_soc,
        "is_charging": is_charging,
        "ev_power": ev_power,
        "dc_power": dc_power,
        "pump_power": pump_power,
    }
    
    bat_config = {
        "capacity_kwh": cap_kwh,
        "rated_power_kw": max_p_scaled / scale_factor,
        "min_soc_pct": bat_cfg.get("min_soc_pct", 20.0),
        "max_soc_pct": bat_cfg.get("max_soc_pct", 95.0),
        "initial_soc_pct": bat_cfg.get("initial_soc_pct", 50.0),
        "charge_efficiency": bat_cfg.get("charge_efficiency", 0.95),
        "discharge_efficiency": bat_cfg.get("discharge_efficiency", 0.95)
    }

    apply_hard_constraints(model, horizon_steps, scale_factor, vars_dict, sim_data, bat_config)
    
    econ_expr = []
    carbon_expr = []
    
    for t in range(horizon_steps):
        price_scaled = int(sim_data["snapshots"][t]["price_per_kwh"] * 1000)
        feed_in_scaled = int(0.05 * 1000)
        econ_expr.append(grid_import[t] * price_scaled - grid_export[t] * feed_in_scaled)
        
        carbon_intensity_scaled = int(sim_data["snapshots"][t]["carbon_intensity_g_per_kwh"])
        carbon_expr.append(grid_import[t] * carbon_intensity_scaled)
        
    econ_total = sum(econ_expr)
    carbon_total = sum(carbon_expr)
    
    max_import = model.NewIntVar(0, pcc_limit_scaled, "max_import")
    for t in range(horizon_steps):
        model.Add(max_import >= grid_import[t])
        
    custom_weights = problem_spec.get("weights")
    if custom_weights and isinstance(custom_weights, dict):
        w_cost_val = float(custom_weights.get("cost", 0.33))
        w_carbon_val = float(custom_weights.get("carbon", 0.33))
        w_peak_val = float(custom_weights.get("peak", 0.33))
        w_econ = max(1, int(w_cost_val * 10))
        w_carbon = max(1, int(w_carbon_val * 10))
        w_peak = max(1, int(w_peak_val * 10))
    elif policy == "CARBON_PRIORITY":
        w_econ, w_carbon, w_peak = 1, 8, 1
    elif policy in ["PEAK_PROTECTION", "PEAK_SHAVING"]:
        w_econ, w_carbon, w_peak = 2, 2, 6
    else:  # BALANCED
        w_econ, w_carbon, w_peak = 4, 4, 2
        
    # Scale max_import by 1000 to match rough magnitude of other objectives
    objective = w_econ * econ_total + w_carbon * carbon_total + w_peak * max_import * 1000
    model.Minimize(objective)
    
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(problem_spec.get("solver_timeout", 30.0))
    solver.parameters.num_search_workers = 8
    solver.parameters.relative_gap_limit = 0.02
    status = solver.Solve(model)
    
    solve_time = time.time() - start_time
    
    if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
        out_snapshots = []
        total_cost = 0.0
        total_co2e = 0.0
        peak_import = 0.0
        
        for t in range(horizon_steps):
            s = sim_data["snapshots"][t].copy()
            s["grid_import_kw"] = solver.Value(grid_import[t]) / scale_factor
            s["grid_export_kw"] = solver.Value(grid_export[t]) / scale_factor
            s["battery_charge_kw"] = solver.Value(bat_charge[t]) / scale_factor
            s["battery_discharge_kw"] = solver.Value(bat_discharge[t]) / scale_factor
            s["battery_soc_kwh"] = solver.Value(bat_soc[t]) / scale_factor
            s["ev_kw"] = sum(solver.Value(ev_power[ev][t]) for ev in ev_power) / scale_factor
            s["datacenter_kw"] = solver.Value(dc_power[t]) / scale_factor
            s["pump_kw"] = solver.Value(pump_power[t]) / scale_factor
            
            s["demand_kw"] = s["residential_kw"] + s["common_area_kw"] + s["ev_kw"] + s["datacenter_kw"] + s["pump_kw"]
            s["solar_direct_kw"] = min(s["solar_kw"], s["demand_kw"])
            s["net_need_kw"] = max(0.0, s["demand_kw"] - s["solar_direct_kw"] - s["battery_discharge_kw"])
            
            # Recalculate energy balance error
            sink = s["demand_kw"] + s["battery_charge_kw"] + s["grid_export_kw"]
            source = s["solar_kw"] + s["battery_discharge_kw"] + s["grid_import_kw"]
            s["energy_balance_error"] = abs(sink - source)
            
            cost = (s["grid_import_kw"] * s["price_per_kwh"] - s["grid_export_kw"] * 0.05) * 0.25
            co2 = s["grid_import_kw"] * s["carbon_intensity_g_per_kwh"] * 0.25 / 1000.0
            total_cost += cost
            total_co2e += co2
            if s["grid_import_kw"] > peak_import:
                peak_import = s["grid_import_kw"]
                
            out_snapshots.append(s)
            
        summary = {
            "total_demand_kwh": sum(s["demand_kw"] * 0.25 for s in out_snapshots),
            "total_solar_kwh": sum(s["solar_kw"] * 0.25 for s in out_snapshots),
            "total_grid_import_kwh": sum(s["grid_import_kw"] * 0.25 for s in out_snapshots),
            "total_cost": total_cost,
            "total_co2e_kg": total_co2e,
            "peak_grid_import_kw": peak_import,
            "peak_demand_kw": max(s["demand_kw"] for s in out_snapshots)
        }
        
        out_flexible_loads = []
        for load in sim_data["flexible_loads"]:
            l_copy = load.copy()
            if load["load_type"] == "ev" and load["id"] in ev_power:
                l_copy["scheduled_power"] = [solver.Value(ev_power[load["id"]][t]) / scale_factor for t in range(horizon_steps)]
            elif load["load_type"] == "data_center":
                l_copy["scheduled_power"] = [solver.Value(dc_power[t]) / scale_factor for t in range(horizon_steps)]
            elif load["load_type"] == "water_pump":
                l_copy["scheduled_power"] = [solver.Value(pump_power[t]) / scale_factor for t in range(horizon_steps)]
            out_flexible_loads.append(l_copy)

        stat_str = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
        res = OptimizationResult(
            status=stat_str,
            solve_time_seconds=solve_time,
            objective_value=solver.ObjectiveValue(),
            snapshots=out_snapshots,
            summary=summary,
            flexible_loads=out_flexible_loads
        )
        return res.model_dump()
        
    else:
        res = OptimizationResult(
            status="INFEASIBLE",
            solve_time_seconds=solve_time,
            objective_value=0.0,
            snapshots=[],
            summary={},
            flexible_loads=[]
        )
        return res.model_dump()
