"""
Unit & Integration Tests for ML Forecasting Layer.
Section 12 of System Design Specification.
"""

import pytest
import numpy as np
import pandas as pd

from app.forecasting.features import extract_features_df, FEATURE_COLUMNS, build_weather_proxy
from app.forecasting.train import train_forecasting_models, generate_synthetic_training_dataset
from app.forecasting.predict import predict_demand_and_solar


def test_weather_proxy_features():
    """Verify physical weather proxy calculations across 24 hours."""
    night = build_weather_proxy(step=10)  # ~02:30 AM
    midday = build_weather_proxy(step=50)  # ~12:30 PM
    
    assert night["solar_elevation_proxy"] == 0.0
    assert midday["solar_elevation_proxy"] > 0.8
    assert midday["temperature_c"] > night["temperature_c"]


def test_feature_engineering_structure():
    """Verify feature extractor generates expected tabular columns and shape."""
    timestamps = [f"2026-06-01T{h:02d}:{m:02d}:00" for h in range(24) for m in (0, 15, 30, 45)]
    loads = [100.0 + 10.0 * np.sin(i / 10.0) for i in range(96)]
    solars = [max(0.0, 200.0 * np.sin(np.pi * i / 96.0)) for i in range(96)]
    
    df = extract_features_df(timestamps, loads, solars)
    assert len(df) == 96
    for col in FEATURE_COLUMNS:
        assert col in df.columns
        assert not df[col].isnull().any(), f"Column {col} contains NaN values"


def test_model_training_pipeline():
    """Verify HistGradientBoostingRegressor training on synthetic dataset."""
    result = train_forecasting_models(num_days=7, seed=42)
    assert result["status"] == "TRAINED"
    assert result["samples_trained"] > 0
    assert result["demand_metrics"]["r2"] > 0.70
    assert result["solar_metrics"]["r2"] > 0.70


def test_ml_forecast_inference_96_steps():
    """Verify 96-step forecast generation, shapes, and physical validity."""
    forecast = predict_demand_and_solar(horizon=96, scenario="baseline", seed=42)
    
    assert forecast["horizon"] == 96
    assert len(forecast["predicted_demand"]) == 96
    assert len(forecast["predicted_solar"]) == 96
    assert len(forecast["forecast_table"]) == 96
    
    # Check all are floats and non-negative
    for d in forecast["predicted_demand"]:
        assert isinstance(d, float)
        assert d >= 0.0
        
    for s in forecast["predicted_solar"]:
        assert isinstance(s, float)
        assert s >= 0.0
        
    # Check night steps have 0 solar
    assert forecast["predicted_solar"][0] == 0.0
    assert forecast["predicted_solar"][10] == 0.0
    assert forecast["predicted_solar"][90] == 0.0
    
    # Check midday has positive solar
    assert forecast["predicted_solar"][48] > 0.0
    
    # Check summary metrics
    summary = forecast["summary"]
    assert summary["peak_demand_kw"] > summary["mean_demand_kw"]
    assert summary["total_demand_kwh"] > 0.0
    assert summary["total_solar_kwh"] > 0.0
