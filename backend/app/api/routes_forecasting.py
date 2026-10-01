"""
ML Forecasting REST Endpoints.
Section 12 and 17 of System Design Specification.
"""

from fastapi import APIRouter, Query
from typing import Optional

from .schemas import ForecastResponse
from ..forecasting.predict import predict_demand_and_solar

router = APIRouter(prefix="/api", tags=["Forecasting"])


@router.get("/forecast", response_model=ForecastResponse)
def get_ml_forecast(
    horizon: int = Query(default=96, ge=1, le=96, description="Forecast horizon steps (1..96)"),
    run_id: Optional[str] = Query(default=None, description="Optional run identifier reference"),
    scenario: str = Query(default="baseline", description="Simulation scenario reference")
) -> ForecastResponse:
    """
    Returns tabular ML demand & solar forecasts for the next 96 15-minute intervals.
    Section 12 & 17.
    """
    forecast_data = predict_demand_and_solar(horizon=horizon, scenario=scenario)
    return ForecastResponse(**forecast_data)
