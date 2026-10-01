"""
Simulation & Community Asset Endpoints.
Sections 16, 17, and 26 of System Design Specification.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import uuid

from ..simulation.simulator import engine
from .schemas import AssetResponse, FlexibleLoadResponse

router = APIRouter(prefix="/api", tags=["Simulation"])


class SimulationCreateRequest(BaseModel):
    scenario: str = "baseline"
    run_id: Optional[str] = None
    overrides: Optional[Dict[str, Any]] = None


class WhatIfRequest(BaseModel):
    parent_run_id: str = "default_baseline"
    scenario: str = "baseline"
    overrides: Dict[str, Any] = Field(default_factory=dict)


@router.get("/config")
def get_default_config() -> Dict[str, Any]:
    """Returns the default configuration loaded from backend/configs/default.yaml."""
    return engine.default_config


@router.get("/assets", response_model=List[AssetResponse])
def get_community_assets() -> List[AssetResponse]:
    """Returns catalog of community assets (100 apartments, 40 EV chargers, solar, battery, pump, data center)."""
    assets = engine.get_assets()
    return [AssetResponse(**a.model_dump()) for a in assets]


@router.get("/flexible-loads", response_model=List[FlexibleLoadResponse])
def get_flexible_loads(run_id: str = "default_baseline") -> List[FlexibleLoadResponse]:
    """Returns flexible workload constraints and scheduled power."""
    run = engine.get_run(run_id)
    if not run:
        if run_id == "default_baseline":
            run = engine.run_baseline_simulation(run_id="default_baseline")
        else:
            raise HTTPException(status_code=404, detail=f"Simulation run '{run_id}' not found.")
            
    return [FlexibleLoadResponse(**load) for load in run["flexible_loads"]]


@router.post("/simulations")
def create_simulation(req: SimulationCreateRequest) -> Dict[str, Any]:
    """Creates and executes a new simulation run."""
    run_id = req.run_id or f"sim_{uuid.uuid4().hex[:8]}"
    result = engine.run_baseline_simulation(
        run_id=run_id,
        scenario_name=req.scenario,
        overrides=req.overrides
    )
    return {
        "status": "COMPLETED",
        "run_id": run_id,
        "scenario": req.scenario,
        "summary": result["summary"]
    }


@router.post("/simulations/what-if")
def simulate_what_if(req: WhatIfRequest) -> Dict[str, Any]:
    """
    Executes what-if counterfactual scenario without mutating parent run.
    Section 26.
    """
    what_if_run_id = f"what_if_{uuid.uuid4().hex[:8]}"
    result = engine.run_baseline_simulation(
        run_id=what_if_run_id,
        scenario_name=req.scenario,
        overrides=req.overrides
    )

    parent_run = engine.get_run(req.parent_run_id)
    if not parent_run and req.parent_run_id == "default_baseline":
        parent_run = engine.run_baseline_simulation(run_id="default_baseline")
        
    comparison = None
    if parent_run:
        comparison = {
            "parent_peak_kw": parent_run["summary"]["peak_grid_import_kw"],
            "what_if_peak_kw": result["summary"]["peak_grid_import_kw"],
            "parent_cost": parent_run["summary"]["total_cost"],
            "what_if_cost": result["summary"]["total_cost"],
            "parent_co2e_kg": parent_run["summary"]["total_co2e_kg"],
            "what_if_co2e_kg": result["summary"]["total_co2e_kg"]
        }

    return {
        "status": "COMPLETED",
        "run_id": what_if_run_id,
        "parent_run_id": req.parent_run_id,
        "summary": result["summary"],
        "comparison": comparison
    }


@router.get("/results/{run_id}")
def get_simulation_results(run_id: str) -> Dict[str, Any]:
    """Returns metrics and time series for a specific simulation run."""
    run = engine.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Simulation run '{run_id}' not found.")
    return run
