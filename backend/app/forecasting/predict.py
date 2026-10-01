"""
ML Inference engine for generating 96-step community demand and solar forecasts.
Section 12.4 of System Design Specification.
"""

import os
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
import joblib
from datetime import datetime, timedelta

from .features import extract_features_df, FEATURE_COLUMNS, build_weather_proxy
from .train import DEMAND_MODEL_PATH, SOLAR_MODEL_PATH, train_forecasting_models
from ..simulation.simulator import engine

# In-memory model cache
_cached_demand_model = None
_cached_solar_model = None


def get_or_load_models():
    """Retrieves cached models or loads/trains them if missing."""
    global _cached_demand_model, _cached_solar_model
    
    if _cached_demand_model is not None and _cached_solar_model is not None:
        return _cached_demand_model, _cached_solar_model
        
    if not os.path.exists(DEMAND_MODEL_PATH) or not os.path.exists(SOLAR_MODEL_PATH):
        train_forecasting_models(num_days=14, seed=42)
        
    _cached_demand_model = joblib.load(DEMAND_MODEL_PATH)
    _cached_solar_model = joblib.load(SOLAR_MODEL_PATH)
    return _cached_demand_model, _cached_solar_model


def predict_demand_and_solar(
    horizon: int = 96,
    scenario: str = "baseline",
    cloud_noise: float = 0.0,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Generates 96-step forecast for aggregate demand and solar output.
    Section 12.4:
      Forecast next 96 intervals -> Optimizer consumes forecast -> Schedule -> Simulator.
    """
    demand_model, solar_model = get_or_load_models()
    
    # Establish simulation reference data as seed history context
    ref_run = engine.run_baseline_simulation(run_id=f"forecast_ref_{seed}", scenario_name=scenario)
    ref_snapshots = ref_run["snapshots"]
    
    timestamps = [s["timestamp"] for s in ref_snapshots[:horizon]]
    base_demands = [s["demand_kw"] for s in ref_snapshots[:horizon]]
    base_solars = [s["solar_kw"] for s in ref_snapshots[:horizon]]
    cloud_factors = [cloud_noise] * horizon
    
    # Extract features for prediction horizon
    X_df = extract_features_df(timestamps, base_demands, base_solars, cloud_factors)
    X = X_df[FEATURE_COLUMNS]
    
    raw_demand_preds = demand_model.predict(X)
    raw_solar_preds = solar_model.predict(X)
    
    # Apply physical clipping constraints
    predicted_demand = [round(float(max(10.0, p)), 2) for p in raw_demand_preds]
    
    # Solar cannot be negative and must be 0 outside daylight (step < 24 or step > 74)
    predicted_solar = []
    for step, p in enumerate(raw_solar_preds):
        if step < 24 or step > 74:
            predicted_solar.append(0.0)
        else:
            predicted_solar.append(round(float(np.clip(p, 0.0, 250.0)), 2))
            
    forecast_table = []
    for step in range(horizon):
        forecast_table.append({
            "step": step,
            "timestamp": timestamps[step] if step < len(timestamps) else f"step_{step}",
            "predicted_demand_kw": predicted_demand[step],
            "predicted_solar_kw": predicted_solar[step]
        })
        
    return {
        "horizon": horizon,
        "model_version": "HistGradientBoosting-v1.0",
        "predicted_demand": predicted_demand,
        "predicted_solar": predicted_solar,
        "forecast_table": forecast_table,
        "summary": {
            "mean_demand_kw": round(float(np.mean(predicted_demand)), 2),
            "peak_demand_kw": round(float(np.max(predicted_demand)), 2),
            "total_demand_kwh": round(float(np.sum(predicted_demand) * 0.25), 2),
            "total_solar_kwh": round(float(np.sum(predicted_solar) * 0.25), 2),
            "peak_solar_kw": round(float(np.max(predicted_solar)), 2)
        }
    }
