import math
from fractions import Fraction
from typing import Dict, Any

def apply_hard_constraints(
    model, 
    horizon_steps: int, 
    scale_factor: int, 
    vars_dict: Dict[str, Any], 
    sim_data: Dict[str, Any], 
    battery_config: Dict[str, Any]
):
    """Enforces all hard constraints on the CP-SAT model."""
    grid_import = vars_dict["grid_import"]
    grid_export = vars_dict["grid_export"]
    bat_charge = vars_dict["bat_charge"]
    bat_discharge = vars_dict["bat_discharge"]
    bat_soc = vars_dict["bat_soc"]
    is_charging = vars_dict["is_charging"]
    ev_power = vars_dict["ev_power"]
    dc_power = vars_dict["dc_power"]
    pump_power = vars_dict["pump_power"]

    snapshots = sim_data["snapshots"]
    
    # 1. Grid Balance Constraint
    for t in range(horizon_steps):
        res_kw = snapshots[t]["residential_kw"] + snapshots[t]["common_area_kw"]
        res_scaled = int(res_kw * scale_factor)
        solar_scaled = int(snapshots[t]["solar_kw"] * scale_factor)

        dynamic_demand = res_scaled + dc_power[t] + pump_power[t]
        for ev_id in ev_power.keys():
            dynamic_demand += ev_power[ev_id][t]
            
        model.Add(
            dynamic_demand + bat_charge[t] + grid_export[t] == 
            solar_scaled + bat_discharge[t] + grid_import[t]
        )

    # 2. Battery SOC and Constraints
    eff_c_frac = Fraction(battery_config.get("charge_efficiency", 0.95)).limit_denominator()
    eff_d_frac = Fraction(battery_config.get("discharge_efficiency", 0.95)).limit_denominator()
    charge_term_frac = eff_c_frac / 4
    discharge_term_frac = 1 / (eff_d_frac * 4)

    def lcm(a, b):
        return abs(a*b) // math.gcd(a, b)

    denom = lcm(charge_term_frac.denominator, discharge_term_frac.denominator)
    soc_coeff = denom
    charge_coeff = int(charge_term_frac.numerator * (denom / charge_term_frac.denominator))
    discharge_coeff = int(discharge_term_frac.numerator * (denom / discharge_term_frac.denominator))
    
    init_soc_scaled = int((battery_config["capacity_kwh"] * (battery_config["initial_soc_pct"] / 100.0)) * scale_factor)
    
    for t in range(horizon_steps):
        model.Add(bat_charge[t] == 0).OnlyEnforceIf(is_charging[t].Not())
        model.Add(bat_discharge[t] == 0).OnlyEnforceIf(is_charging[t])
        
        if t == 0:
            model.Add(soc_coeff * bat_soc[t] == soc_coeff * init_soc_scaled + charge_coeff * bat_charge[t] - discharge_coeff * bat_discharge[t])
        else:
            model.Add(soc_coeff * bat_soc[t] == soc_coeff * bat_soc[t-1] + charge_coeff * bat_charge[t] - discharge_coeff * bat_discharge[t])

    # 3. Flexible Load Constraints
    flexible_loads = sim_data["flexible_loads"]
    for load in flexible_loads:
        req_energy_scaled = int(load["energy_required_kwh"] * scale_factor)
        earliest = load["earliest_start"]
        latest = load["latest_end"]
        
        if load["load_type"] == "ev":
            target_sum = req_energy_scaled * 4
            model.Add(sum(ev_power[load["id"]][t] for t in range(earliest, latest)) == target_sum)
            for t in range(horizon_steps):
                if t < earliest or t >= latest:
                    model.Add(ev_power[load["id"]][t] == 0)
                    
        elif load["load_type"] == "data_center":
            target_sum = req_energy_scaled * 4
            model.Add(sum(dc_power[t] for t in range(earliest, latest)) == target_sum)
            for t in range(horizon_steps):
                if t < earliest or t >= latest:
                    model.Add(dc_power[t] == 0)
                    
        elif load["load_type"] == "water_pump":
            target_sum = req_energy_scaled * 4
            model.Add(sum(pump_power[t] for t in range(earliest, latest)) == target_sum)
            for t in range(horizon_steps):
                if t < earliest or t >= latest:
                    model.Add(pump_power[t] == 0)
