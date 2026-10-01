"""
End-to-End FastAPI REST API Tests.
Sections 16, 17, and 21 of System Design Specification.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_root_and_health():
    """Verify service availability and root status."""
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ONLINE"
    assert "Phase 3" in data["phase"]

    health_res = client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"


def test_get_grid_state():
    """Verify GET /api/grid/state returns valid snapshot data."""
    res = client.get("/api/grid/state?run_id=default_baseline")
    assert res.status_code == 200
    data = res.json()
    assert "run_id" in data
    assert "state" in data
    assert "step" in data
    assert data["state"]["demand_kw"] > 0


def test_get_grid_timeseries():
    """Verify GET /api/grid/timeseries returns 96 timesteps."""
    res = client.get("/api/grid/timeseries?run_id=default_baseline")
    assert res.status_code == 200
    data = res.json()
    assert data["horizon_steps"] == 96
    assert len(data["timeseries"]) == 96
    assert "summary" in data


def test_get_ml_forecast_endpoint():
    """Verify GET /api/forecast returns 96-step forecast."""
    res = client.get("/api/forecast?horizon=96")
    assert res.status_code == 200
    data = res.json()
    assert data["horizon"] == 96
    assert len(data["predicted_demand"]) == 96
    assert len(data["predicted_solar"]) == 96
    assert len(data["forecast_table"]) == 96
    assert "summary" in data


def test_get_community_assets():
    """Verify GET /api/assets returns community asset inventory."""
    res = client.get("/api/assets")
    assert res.status_code == 200
    assets = res.json()
    assert isinstance(assets, list)
    assert len(assets) >= 5  # Apartments, EV chargers, solar, battery, data center, pump
    types = [a["type"] for a in assets]
    assert "residential" in types
    assert "battery" in types
    assert "solar" in types


def test_get_flexible_loads():
    """Verify GET /api/flexible-loads returns flexible loads."""
    res = client.get("/api/flexible-loads?run_id=default_baseline")
    assert res.status_code == 200
    loads = res.json()
    assert isinstance(loads, list)
    assert len(loads) > 0
    load_types = {load["load_type"] for load in loads}
    assert "ev" in load_types
    assert "data_center" in load_types
    assert "water_pump" in load_types


def test_post_optimize_end_to_end():
    """
    Verify POST /api/optimize executes end-to-end:
    - Returns HTTP 200
    - Solver status is OPTIMAL or FEASIBLE
    - 0 hard constraint violations
    - Non-negative metric savings / deltas
    - Retrieval via GET /api/optimization/{id}
    """
    req_payload = {
        "run_id": "test_opt_001",
        "policy": "BALANCED",
        "horizon_steps": 96,
        "weights": {
            "cost": 0.25,
            "carbon": 0.25,
            "peak": 0.25,
            "discomfort": 0.20
        },
        "scenario_name": "baseline"
    }
    
    res = client.post("/api/optimize", json=req_payload)
    assert res.status_code == 200, f"Error: {res.text}"
    data = res.json()
    
    assert data["solver_status"] in ["OPTIMAL", "FEASIBLE"]
    assert data["hard_constraint_violations"] == 0
    assert data["constraint_audit"]["hard_constraint_violations"] == 0
    assert data["constraint_audit"]["is_feasible"] is True
    assert data["schedule_id"].startswith("sched-")
    
    # Check evaluation deltas
    deltas = data["deltas"]
    # Peak reduction should be non-negative or positive
    assert deltas["peak_reduction_kw"] >= 0.0
    assert deltas["peak_reduction_pct"] >= 0.0
    
    # Cost or carbon should be reduced
    assert deltas["cost_reduction_currency"] >= 0.0
    
    # Verify retrieval endpoint
    sched_id = data["schedule_id"]
    get_res = client.get(f"/api/optimization/{sched_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["id"] == sched_id
    assert get_data["status"] == "COMPLETED"


def test_post_optimize_carbon_priority():
    """Verify POST /api/optimize under CARBON_PRIORITY policy."""
    req_payload = {
        "run_id": "test_opt_carbon",
        "policy": "CARBON_PRIORITY",
        "horizon_steps": 96
    }
    res = client.post("/api/optimize", json=req_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["solver_status"] in ["OPTIMAL", "FEASIBLE"]
    assert data["hard_constraint_violations"] == 0
    assert data["deltas"]["co2e_reduction_kg"] >= 0.0
