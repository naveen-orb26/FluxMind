from pydantic import BaseModel
from typing import Dict, Any, List, Optional

class OptimizationRequest(BaseModel):
    run_id: str
    scenario_name: str = "baseline"
    policy: str = "BALANCED"
    weights: Optional[Dict[str, float]] = None
    overrides: Optional[Dict[str, Any]] = None

class OptimizationResult(BaseModel):
    status: str
    solve_time_seconds: float
    objective_value: float
    snapshots: List[Dict[str, Any]]
    summary: Dict[str, Any]
    flexible_loads: List[Dict[str, Any]]
