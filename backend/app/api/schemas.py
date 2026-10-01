"""
Pydantic Request and Response Schemas for FastAPI Endpoints.
Sections 16, 17, and 21 of System Design Specification.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


# -------------------------------------------------------------------------
# Grid State & Timeseries Schemas (Section 16 & 17)
# -------------------------------------------------------------------------

class GridSnapshotModel(BaseModel):
    step: int
    timestamp: str
    demand_kw: float
    solar_kw: float
    grid_import_kw: float
    grid_export_kw: float
    battery_charge_kw: float
    battery_discharge_kw: float
    battery_soc_kwh: float
    carbon_intensity_g_per_kwh: float
    price_per_kwh: float
    solar_direct_kw: Optional[float] = None
    net_need_kw: Optional[float] = None
    energy_balance_error: Optional[float] = None


class GridStateResponse(BaseModel):
    run_id: str
    scenario: str
    step: int
    timestamp: str
    state: Dict[str, Any]
    summary: Dict[str, Any]


class GridTimeseriesResponse(BaseModel):
    run_id: str
    scenario: str
    horizon_steps: int
    timeseries: List[Dict[str, Any]]
    summary: Dict[str, Any]


# -------------------------------------------------------------------------
# Forecasting Schemas (Section 12 & 17)
# -------------------------------------------------------------------------

class ForecastStepItem(BaseModel):
    step: int
    timestamp: str
    predicted_demand_kw: float
    predicted_solar_kw: float


class ForecastSummaryModel(BaseModel):
    mean_demand_kw: float
    peak_demand_kw: float
    total_demand_kwh: float
    total_solar_kwh: float
    peak_solar_kw: float


class ForecastResponse(BaseModel):
    horizon: int
    model_version: str
    predicted_demand: List[float]
    predicted_solar: List[float]
    forecast_table: List[ForecastStepItem]
    summary: ForecastSummaryModel


# -------------------------------------------------------------------------
# Asset & Flexible Load Schemas (Section 5 & 16)
# -------------------------------------------------------------------------

class AssetResponse(BaseModel):
    id: str
    type: str
    name: str
    rated_power_kw: float
    capacity_kwh: Optional[float] = None
    flexibility_class: str


class FlexibleLoadResponse(BaseModel):
    id: str
    asset_id: str
    name: str
    load_type: str
    energy_required_kwh: float
    earliest_start: int
    latest_end: int
    max_power_kw: float
    priority: int = 1
    interruptible: bool = True
    scheduled_power: List[float] = Field(default_factory=list)


# -------------------------------------------------------------------------
# Optimization Schemas (Section 17.1 & 17.2)
# -------------------------------------------------------------------------

class OptimizeRequest(BaseModel):
    run_id: str = Field(default="demo-001", description="Identifier for reference run")
    policy: str = Field(default="BALANCED", description="BALANCED, CARBON_PRIORITY, or PEAK_PROTECTION")
    horizon_steps: int = Field(default=96, ge=1, le=96)
    weights: Optional[Dict[str, float]] = Field(
        default=None,
        description="Optional objective weights (cost, carbon, peak, discomfort)"
    )
    allow_export: bool = Field(default=False)
    scenario_name: str = Field(default="baseline")
    overrides: Optional[Dict[str, Any]] = None


class MetricSnapshotModel(BaseModel):
    total_demand_kwh: float
    total_solar_kwh: float
    total_grid_import_kwh: float
    total_grid_export_kwh: float
    peak_demand_kw: float
    peak_grid_import_kw: float
    total_cost: float
    total_co2e_kg: float
    renewable_self_consumption_pct: float
    curtailment_pct: float
    pcc_violation_count: int
    soc_violation_count: int
    max_energy_balance_error_kw: float


class MetricDeltasModel(BaseModel):
    peak_reduction_kw: float
    peak_reduction_pct: float
    co2e_reduction_kg: float
    co2e_reduction_pct: float
    cost_reduction_currency: float
    cost_reduction_pct: float
    renewable_self_consumption_gain_pct: float


class ConstraintAuditModel(BaseModel):
    hard_constraint_violations: int
    pcc_violations: int
    soc_violations: int
    missed_deadlines: int
    unserved_load_energy_kwh: float
    is_feasible: bool


class OptimizeResponse(BaseModel):
    solver_status: str
    objective_value: float
    solve_time_seconds: float
    peak_grid_import_kw: float
    total_cost: float
    total_co2e_kg: float
    hard_constraint_violations: int
    schedule_id: str
    policy: str
    deltas: MetricDeltasModel
    baseline_metrics: MetricSnapshotModel
    optimized_metrics: MetricSnapshotModel
    constraint_audit: ConstraintAuditModel
    snapshots: Optional[List[Dict[str, Any]]] = None
    flexible_loads: Optional[List[Dict[str, Any]]] = None
