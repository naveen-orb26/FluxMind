import pytest
import math
from fastapi.testclient import TestClient

from app.main import app
from app.simulation.simulator import SimulationEngine, engine
from app.simulation.battery import BatteryConfig, BatteryStorage
from app.simulation.loads import generate_residential_profiles, generate_ev_sessions
from app.simulation.solar import generate_solar_generation
from app.carbon.intensity import generate_carbon_intensity_signal


@pytest.fixture
def sim_engine():
    """Provides a fresh SimulationEngine instance."""
    return SimulationEngine()


@pytest.fixture
def test_client():
    """FastAPI TestClient fixture."""
    return TestClient(app)


def test_baseline_simulation_execution_96_steps(sim_engine):
    """
    Verifies that the baseline simulation executes without errors,
    produces exactly 96 timesteps (15-min intervals over 24 hours),
    and correctly populates summary KPIs.
    """
    result = sim_engine.run_baseline_simulation(run_id="test_run_01", scenario_name="baseline")
    assert result is not None
    assert result["run_id"] == "test_run_01"
    assert result["horizon_steps"] == 96

    snapshots = result["snapshots"]
    assert len(snapshots) == 96, f"Expected 96 snapshots, got {len(snapshots)}"

    # Check timestamps: step 0 -> 00:00, step 95 -> 23:45
    assert snapshots[0]["timestamp"] == "00:00"
    assert snapshots[95]["timestamp"] == "23:45"

    summary = result["summary"]
    assert summary["total_demand_kwh"] > 0.0
    assert summary["total_solar_kwh"] > 0.0
    assert summary["total_cost"] > 0.0
    assert summary["total_co2e_kg"] > 0.0
    assert summary["peak_grid_import_kw"] > 0.0
    assert summary["peak_demand_kw"] > 0.0


def test_energy_balance_equation_every_interval(sim_engine):
    """
    Verifies that at every interval t (0..95), the system satisfies the energy balance equation:
    Demand_t + BatteryCharge_t + GridExport_t == SolarPower_t + BatteryDischarge_t + GridImport_t
    within numerical tolerance (< 1e-4 kW).
    Section 8.3 & Section 22.
    """
    result = sim_engine.run_baseline_simulation(run_id="test_balance_run", scenario_name="baseline")
    snapshots = result["snapshots"]

    for idx, s in enumerate(snapshots):
        step = s["step"]
        demand_kw = s["demand_kw"]
        bat_charge_kw = s["battery_charge_kw"]
        grid_export_kw = s["grid_export_kw"]

        solar_kw = s["solar_kw"]
        bat_discharge_kw = s["battery_discharge_kw"]
        grid_import_kw = s["grid_import_kw"]

        # 1. Total energy sink must match total energy source
        total_sink = demand_kw + bat_charge_kw + grid_export_kw
        total_source = solar_kw + bat_discharge_kw + grid_import_kw
        error = abs(total_sink - total_source)

        assert error < 1e-4, (
            f"Energy balance violated at step {step} ({s['timestamp']}): "
            f"Sink={total_sink:.4f} kW != Source={total_source:.4f} kW (error={error:.6f} kW)"
        )

        # 2. Demand subcomponent reconciliation
        sub_demand = s["residential_kw"] + s["ev_kw"] + s["datacenter_kw"] + s["pump_kw"] + s["common_area_kw"]
        assert abs(demand_kw - sub_demand) < 1e-3, (
            f"Demand components sum mismatch at step {step}: {demand_kw} vs {sub_demand}"
        )

        # 3. Direct solar use cannot exceed either solar or demand
        assert s["solar_direct_kw"] <= solar_kw + 1e-5
        assert s["solar_direct_kw"] <= demand_kw + 1e-5

        # 4. Energy balance error logged inside snapshot must be clean
        assert s["energy_balance_error"] < 1e-4


def test_battery_physical_and_operational_constraints(sim_engine):
    """
    Verifies that battery storage operations respect:
    1. Capacity bounds (min_soc <= SOC <= max_soc: 100 kWh <= SOC <= 475 kWh).
    2. Power limits (charge <= 250 kW, discharge <= 250 kW).
    3. Strictly no simultaneous charge and discharge (charge * discharge == 0).
    Section 9.
    """
    result = sim_engine.run_baseline_simulation(run_id="test_bat_run", scenario_name="baseline")
    snapshots = result["snapshots"]

    min_soc_kwh = 500.0 * 0.20  # 100 kWh
    max_soc_kwh = 500.0 * 0.95  # 475 kWh
    rated_p = 250.0

    for s in snapshots:
        soc = s["battery_soc_kwh"]
        charge = s["battery_charge_kw"]
        discharge = s["battery_discharge_kw"]

        assert soc >= (min_soc_kwh - 1e-4), f"Battery SOC {soc} fell below minimum {min_soc_kwh} at step {s['step']}"
        assert soc <= (max_soc_kwh + 1e-4), f"Battery SOC {soc} exceeded maximum {max_soc_kwh} at step {s['step']}"

        assert charge <= (rated_p + 1e-4), f"Battery charge {charge} exceeded max power {rated_p} at step {s['step']}"
        assert discharge <= (rated_p + 1e-4), f"Battery discharge {discharge} exceeded max power {rated_p} at step {s['step']}"

        assert (charge * discharge) == pytest.approx(0.0, abs=1e-5), (
            f"Simultaneous charge ({charge}) and discharge ({discharge}) detected at step {s['step']}"
        )


def test_community_assets_and_flexible_loads(sim_engine):
    """
    Verifies modeling of community assets:
    - 100 apartments
    - 40 EV chargers + 40 EV charging sessions
    - 1 rooftop solar (250 kW)
    - 1 battery (500 kWh / 250 kW)
    - 1 water pump (50 kW / 50 kWh)
    - 1 data-center batch (200 kW / 400 kWh)
    Appendix A & Section 7.1.
    """
    assets = sim_engine.get_assets()
    asset_types = [a.type for a in assets]

    assert asset_types.count("residential") == 1
    assert asset_types.count("solar") == 1
    assert asset_types.count("battery") == 1
    assert asset_types.count("water_pump") == 1
    assert asset_types.count("data_center") == 1
    assert asset_types.count("ev_charger") == 40

    run = sim_engine.run_baseline_simulation(run_id="test_assets_run")
    loads = run["flexible_loads"]
    assert len(loads) == 42  # 40 EVs + 1 DC + 1 Pump

    ev_loads = [l for l in loads if l["load_type"] == "ev"]
    dc_loads = [l for l in loads if l["load_type"] == "data_center"]
    pump_loads = [l for l in loads if l["load_type"] == "water_pump"]

    assert len(ev_loads) == 40
    assert len(dc_loads) == 1
    assert len(pump_loads) == 1

    # Check EV energy requested ranges (8 to 24 kWh)
    for ev in ev_loads:
        assert 8.0 <= ev["energy_required_kwh"] <= 24.0
        assert ev["max_power_kw"] == 7.2
        assert ev["earliest_start"] <= ev["latest_end"]

    # Check Data Center parameters (200 kW, 400 kWh)
    assert dc_loads[0]["max_power_kw"] == 200.0
    assert dc_loads[0]["energy_required_kwh"] == 400.0

    # Check Water Pump parameters (50 kW, 50 kWh)
    assert pump_loads[0]["max_power_kw"] == 50.0
    assert pump_loads[0]["energy_required_kwh"] == 50.0


def test_reproducibility(sim_engine):
    """
    Verifies that running the simulation with the same seed (42) produces bitwise identical results.
    Section 3 & Section 22.
    """
    run_a = sim_engine.run_baseline_simulation(run_id="run_a")
    run_b = sim_engine.run_baseline_simulation(run_id="run_b")

    assert run_a["summary"]["total_cost"] == run_b["summary"]["total_cost"]
    assert run_a["summary"]["total_co2e_kg"] == run_b["summary"]["total_co2e_kg"]
    assert run_a["summary"]["peak_grid_import_kw"] == run_b["summary"]["peak_grid_import_kw"]

    for sa, sb in zip(run_a["snapshots"], run_b["snapshots"]):
        assert sa["demand_kw"] == sb["demand_kw"]
        assert sa["solar_kw"] == sb["solar_kw"]
        assert sa["grid_import_kw"] == sb["grid_import_kw"]
        assert sa["battery_soc_kwh"] == sb["battery_soc_kwh"]


def test_fastapi_endpoints(test_client):
    """
    Verifies that all API endpoints respond properly with valid status codes and data.
    """
    # 1. Health check
    res = test_client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "healthy"}

    # 2. Grid state
    res = test_client.get("/api/grid/state")
    assert res.status_code == 200
    data = res.json()
    assert "state" in data
    assert "summary" in data

    # 3. Grid timeseries
    res = test_client.get("/api/grid/timeseries")
    assert res.status_code == 200
    ts_data = res.json()
    assert len(ts_data["timeseries"]) == 96

    # 4. Assets catalog
    res = test_client.get("/api/assets")
    assert res.status_code == 200
    assert len(res.json()) >= 45

    # 5. Flexible loads
    res = test_client.get("/api/flexible-loads")
    assert res.status_code == 200
    assert len(res.json()) == 42

    # 6. What-if counterfactual simulation
    res = test_client.post("/api/simulations/what-if", json={
        "parent_run_id": "default_baseline",
        "scenario": "cloudy_day",
        "overrides": {"solar_multiplier": 0.6}
    })
    assert res.status_code == 200
    what_if_res = res.json()
    assert what_if_res["status"] == "COMPLETED"
    assert "comparison" in what_if_res


def test_carbon_and_tariff_signals(sim_engine):
    """
    Verifies that carbon intensity drops during solar-rich afternoon and peaks during evening,
    and that TOU tariffs match configured price tiers.
    Section 6 & Appendix A.
    """
    run = sim_engine.run_baseline_simulation(run_id="test_signals")
    snapshots = run["snapshots"]

    # Midday solar step (step 48 = 12:00 PM)
    midday_carbon = snapshots[48]["carbon_intensity_g_per_kwh"]
    # Evening peak step (step 80 = 20:00 PM)
    evening_carbon = snapshots[80]["carbon_intensity_g_per_kwh"]

    assert midday_carbon < 300.0, f"Expected low carbon intensity at noon, got {midday_carbon}"
    assert evening_carbon > 500.0, f"Expected high carbon intensity at evening peak, got {evening_carbon}"

    # Tariff validation: off-peak ($0.10), peak ($0.30)
    assert snapshots[8]["price_per_kwh"] == 0.10  # 02:00 AM
    assert snapshots[72]["price_per_kwh"] == 0.30  # 18:00 PM


def test_what_if_scenarios(sim_engine):
    """
    Verifies cloudy day and EV surge scenario executions.
    """
    base_run = sim_engine.run_baseline_simulation(run_id="base", scenario_name="baseline")
    cloudy_run = sim_engine.run_baseline_simulation(run_id="cloudy", scenario_name="cloudy_day")
    ev_surge_run = sim_engine.run_baseline_simulation(run_id="ev_surge", scenario_name="ev_surge")

    # Cloudy day has lower solar and higher grid import
    assert cloudy_run["summary"]["total_solar_kwh"] < base_run["summary"]["total_solar_kwh"]
    assert cloudy_run["summary"]["total_grid_import_kwh"] > base_run["summary"]["total_grid_import_kwh"]

    # EV surge has 60 EVs instead of 40, so higher total demand
    assert ev_surge_run["summary"]["total_demand_kwh"] > base_run["summary"]["total_demand_kwh"]
    assert len(ev_surge_run["flexible_loads"]) == 62
