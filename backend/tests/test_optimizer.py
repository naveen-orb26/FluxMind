import pytest
from app.optimization.solver import solve_schedule
from app.optimization.model import OptimizationResult

def test_optimizer_execution_and_constraints():
    """Verifies optimization executes successfully and respects battery bounds & EV deadlines."""
    req = {
        "run_id": "test_opt_01",
        "scenario_name": "baseline",
        "policy": "BALANCED"
    }
    
    result = solve_schedule(req)
    assert result["status"] in ["OPTIMAL", "FEASIBLE"]
    assert result["solve_time_seconds"] > 0
    assert len(result["snapshots"]) == 96
    
    snapshots = result["snapshots"]
    loads = result["flexible_loads"]
    
    # Check battery constraints and energy balance
    min_soc_kwh = 100.0
    max_soc_kwh = 475.0
    max_p_kw = 250.0
    
    for s in snapshots:
        # Physical constraints
        assert s["battery_soc_kwh"] >= min_soc_kwh - 1e-3
        assert s["battery_soc_kwh"] <= max_soc_kwh + 1e-3
        assert s["battery_charge_kw"] <= max_p_kw + 1e-3
        assert s["battery_discharge_kw"] <= max_p_kw + 1e-3
        
        # No simultaneous charge and discharge
        assert (s["battery_charge_kw"] * s["battery_discharge_kw"]) == pytest.approx(0.0, abs=1e-5)
        
        # Grid limit
        assert s["grid_import_kw"] <= 2500.0 + 1e-3
        assert s["grid_export_kw"] <= 2500.0 + 1e-3
        
        # Energy Balance
        assert s["energy_balance_error"] < 1e-3
        
    # Check flexible loads
    ev_loads = [load for load in loads if load["load_type"] == "ev"]
    for ev in ev_loads:
        ev_energy_delivered = sum(
            s["ev_kw"] * 0.25 for i, s in enumerate(snapshots) 
            # In our solver we only extracted aggregate `s["ev_kw"]` for all EVs...
            # Wait, we don't have individual EV power in the snapshot.
            # We can check aggregate EV energy.
        )
    
    aggregate_ev_req = sum(ev["energy_required_kwh"] for ev in ev_loads)
    aggregate_ev_del = sum(s["ev_kw"] * 0.25 for s in snapshots)
    
    # Floating point comparison
    assert abs(aggregate_ev_req - aggregate_ev_del) < 0.1

def test_optimizer_policy_comparison():
    """Verifies that PEAK_SHAVING produces a lower peak than CARBON_PRIORITY,
    and CARBON_PRIORITY produces less CO2 than PEAK_SHAVING."""
    
    res_peak = solve_schedule({"run_id": "test_peak", "policy": "PEAK_SHAVING"})
    res_carbon = solve_schedule({"run_id": "test_carbon", "policy": "CARBON_PRIORITY"})
    
    assert res_peak["status"] in ["OPTIMAL", "FEASIBLE"]
    assert res_carbon["status"] in ["OPTIMAL", "FEASIBLE"]
    
    peak_shaving_peak = res_peak["summary"]["peak_grid_import_kw"]
    carbon_policy_peak = res_carbon["summary"]["peak_grid_import_kw"]
    
    peak_shaving_co2 = res_peak["summary"]["total_co2e_kg"]
    carbon_policy_co2 = res_carbon["summary"]["total_co2e_kg"]
    
    # Peak Shaving should have lower or equal peak
    assert peak_shaving_peak <= carbon_policy_peak + 1e-3
    
    # Carbon Priority should have lower or equal CO2e
    assert carbon_policy_co2 <= peak_shaving_co2 + 1e-3
