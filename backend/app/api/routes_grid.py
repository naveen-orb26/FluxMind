"""
Virtual Grid Endpoints.
Sections 16 and 17 of System Design Specification.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from ..simulation.simulator import engine
from .schemas import GridStateResponse, GridTimeseriesResponse
import yaml
from pathlib import Path



router = APIRouter(prefix="/api/grid", tags=["Grid"])

# Locate your simulation.yaml path
CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "simulation.yaml"

@router.get("/config")
def get_simulation_config():
    with open(CONFIG_PATH, "r") as f:
        config_data = yaml.safe_load(f)
    return config_data


@router.get("/state", response_model=GridStateResponse)
def get_grid_state(
    run_id: str = Query(default="default_baseline", description="Simulation run identifier"),
    step: Optional[int] = Query(default=None, description="Timestep index (0..95)")
) -> GridStateResponse:
    """
    Returns current or specific timestep virtual grid state and snapshot.
    Section 16 & 17.
    """
    run = engine.get_run(run_id)
    if not run:
        # Run baseline if default_baseline requested but not yet in memory
        if run_id == "default_baseline":
            run = engine.run_baseline_simulation(run_id="default_baseline")
        else:
            raise HTTPException(status_code=404, detail=f"Simulation run '{run_id}' not found.")

    snapshots = run["snapshots"]
    if not snapshots:
        raise HTTPException(status_code=404, detail="No snapshots found in run.")

    if step is None:
        selected_snapshot = snapshots[48]  # Step 48 = 12:00 PM solar midday
    else:
        if step < 0 or step >= len(snapshots):
            raise HTTPException(status_code=400, detail=f"Step {step} out of bounds (0..{len(snapshots)-1}).")
        selected_snapshot = snapshots[step]

    return GridStateResponse(
        run_id=run_id,
        scenario=run["scenario"],
        step=selected_snapshot["step"],
        timestamp=selected_snapshot["timestamp"],
        state=selected_snapshot,
        summary=run["summary"]
    )


@router.get("/timeseries", response_model=GridTimeseriesResponse)
def get_grid_timeseries(
    run_id: str = Query(default="default_baseline", description="Simulation run identifier")
) -> GridTimeseriesResponse:
    """
    Returns full 96-interval time series data for charts and analysis.
    Section 17.
    """
    run = engine.get_run(run_id)
    if not run:
        if run_id == "default_baseline":
            run = engine.run_baseline_simulation(run_id="default_baseline")
        else:
            raise HTTPException(status_code=404, detail=f"Simulation run '{run_id}' not found.")

    return GridTimeseriesResponse(
        run_id=run_id,
        scenario=run["scenario"],
        horizon_steps=run["horizon_steps"],
        timeseries=run["snapshots"],
        summary=run["summary"]
    )
