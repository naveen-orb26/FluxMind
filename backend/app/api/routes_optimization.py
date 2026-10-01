"""
Optimization REST Endpoints.
Sections 10, 17.1, 17.2, and 21 of System Design Specification.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import uuid

from .schemas import OptimizeRequest, OptimizeResponse
from ..optimization.solver import solve_schedule
from ..simulation.simulator import engine
from ..evaluation.metrics import evaluate_baseline_vs_optimized

router = APIRouter(prefix="/api", tags=["Optimization"])

# Store completed optimization runs for GET /api/optimization/{id}
_optimization_store: Dict[str, Dict[str, Any]] = {}


@router.post("/optimize", response_model=OptimizeResponse)
def run_optimization(req: OptimizeRequest) -> OptimizeResponse:
    """
    Executes CP-SAT multi-objective DER optimization.
    Section 17.1 & 17.2:
      Accepts policy (BALANCED, CARBON_PRIORITY, PEAK_PROTECTION) and custom weights,
      runs CP-SAT solver, evaluates against baseline, and returns schedule and evaluation deltas.
    """
    # 1. Run baseline reference
    base_run_id = f"{req.run_id}_base"
    baseline_run = engine.run_baseline_simulation(
        run_id=base_run_id,
        scenario_name=req.scenario_name,
        overrides=req.overrides
    )

    # 2. Solve CP-SAT optimization model
    problem_spec = {
        "run_id": req.run_id,
        "scenario_name": req.scenario_name,
        "policy": req.policy,
        "weights": req.weights,
        "overrides": req.overrides
    }
    opt_result = solve_schedule(problem_spec)

    if opt_result["status"] not in ["OPTIMAL", "FEASIBLE"]:
        raise HTTPException(
            status_code=422,
            detail=f"Solver was unable to find a feasible solution. Status: {opt_result['status']}"
        )

    # 3. Calculate baseline vs optimized comparative metrics (Section 21)
    eval_comparison = evaluate_baseline_vs_optimized(baseline_run, opt_result)

    schedule_id = f"sched-{uuid.uuid4().hex[:6]}"
    
    response_data = OptimizeResponse(
        solver_status=opt_result["status"],
        objective_value=round(float(opt_result["objective_value"]), 4),
        solve_time_seconds=round(float(opt_result["solve_time_seconds"]), 3),
        peak_grid_import_kw=opt_result["summary"]["peak_grid_import_kw"],
        total_cost=opt_result["summary"]["total_cost"],
        total_co2e_kg=opt_result["summary"]["total_co2e_kg"],
        hard_constraint_violations=eval_comparison["constraint_audit"]["hard_constraint_violations"],
        schedule_id=schedule_id,
        policy=req.policy,
        deltas=eval_comparison["deltas"],
        baseline_metrics=eval_comparison["baseline"],
        optimized_metrics=eval_comparison["optimized"],
        constraint_audit=eval_comparison["constraint_audit"],
        snapshots=opt_result["snapshots"],
        flexible_loads=opt_result["flexible_loads"]
    )

    # Persist in memory store for retrieval
    _optimization_store[schedule_id] = {
        "id": schedule_id,
        "run_id": req.run_id,
        "request": req.model_dump(),
        "response": response_data.model_dump(),
        "snapshots": opt_result["snapshots"],
        "flexible_loads": opt_result["flexible_loads"]
    }

    return response_data


@router.get("/optimization/{id}")
def get_optimization_status(id: str) -> Dict[str, Any]:
    """Returns optimization status, schedule, and result metrics by schedule_id."""
    if id in _optimization_store:
        record = _optimization_store[id]
        return {
            "id": id,
            "status": "COMPLETED",
            "solver_status": record["response"]["solver_status"],
            "schedule": record["response"],
            "snapshots_count": len(record["snapshots"])
        }
    raise HTTPException(status_code=404, detail=f"Optimization schedule '{id}' not found.")
