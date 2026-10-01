"""
Model training for community demand and solar forecasting using HistGradientBoostingRegressor.
Section 12.3 of System Design Specification.
"""

import os
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
import joblib
from datetime import datetime, timedelta
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from .features import extract_features_df, FEATURE_COLUMNS
from ..simulation.loads import generate_residential_profiles, generate_common_area_profile
from ..simulation.solar import generate_solar_generation

MODEL_DIR = os.path.dirname(__file__)
DEMAND_MODEL_PATH = os.path.join(MODEL_DIR, "demand_model.joblib")
SOLAR_MODEL_PATH = os.path.join(MODEL_DIR, "solar_model.joblib")


def generate_synthetic_training_dataset(num_days: int = 14, base_seed: int = 42) -> Tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    Generates multi-day synthetic historical time series for community demand and solar PV.
    Returns:
        X (pd.DataFrame): Tabular features
        y_demand (pd.Series): Target total demand (kW)
        y_solar (pd.Series): Target solar generation (kW)
    """
    all_timestamps = []
    all_demands = []
    all_solars = []
    all_clouds = []
    
    start_dt = datetime(2026, 5, 1, 0, 0)
    
    for day in range(num_days):
        day_seed = base_seed + day
        rng = np.random.RandomState(day_seed)
        day_dt = start_dt + timedelta(days=day)
        is_weekend = 1 if day_dt.weekday() >= 5 else 0
        
        # Cloud variation across days
        daily_cloud = float(rng.uniform(0.0, 0.45))
        solar_factor = max(0.2, 1.0 - daily_cloud * 1.2)
        
        # Generate 96-step profiles for this day
        res = generate_residential_profiles(num_apartments=100, horizon_steps=96, seed=day_seed)
        com = generate_common_area_profile(horizon_steps=96)
        sol = generate_solar_generation(capacity_kw=250.0, horizon_steps=96, solar_multiplier=solar_factor, seed=day_seed)
        
        # Combine residential + common area + baseline flexible noise
        day_demand = [res["aggregate_kw"][t] + com[t] for t in range(96)]
        
        # Add weekend effect: slight shift in morning peak and higher afternoon occupancy
        if is_weekend:
            day_demand = [d * 1.08 for d in day_demand]
            
        for step in range(96):
            ts = (day_dt + timedelta(minutes=15 * step)).isoformat()
            all_timestamps.append(ts)
            all_demands.append(day_demand[step])
            all_solars.append(sol[step])
            all_clouds.append(daily_cloud)
            
    # Feature engineering over full time series
    X_df = extract_features_df(all_timestamps, all_demands, all_solars, all_clouds)
    y_demand = pd.Series(all_demands, name="demand_kw")
    y_solar = pd.Series(all_solars, name="solar_kw")
    
    return X_df[FEATURE_COLUMNS], y_demand, y_solar


def train_forecasting_models(num_days: int = 14, seed: int = 42) -> Dict[str, Any]:
    """
    Trains HistGradientBoostingRegressor for aggregate demand and solar output.
    Saves trained models to joblib artifacts.
    """
    X, y_demand, y_solar = generate_synthetic_training_dataset(num_days=num_days, base_seed=seed)
    
    # 80/20 train/validation split
    split_idx = int(len(X) * 0.8)
    X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
    y_d_train, y_d_val = y_demand.iloc[:split_idx], y_demand.iloc[split_idx:]
    y_s_train, y_s_val = y_solar.iloc[:split_idx], y_solar.iloc[split_idx:]
    
    # Train demand model
    demand_model = HistGradientBoostingRegressor(
        max_iter=120,
        learning_rate=0.08,
        min_samples_leaf=15,
        random_state=seed
    )
    demand_model.fit(X_train, y_d_train)
    d_preds = demand_model.predict(X_val)
    
    d_rmse = float(np.sqrt(mean_squared_error(y_d_val, d_preds)))
    d_mae = float(mean_absolute_error(y_d_val, d_preds))
    d_r2 = float(r2_score(y_d_val, d_preds))
    
    # Train solar model
    solar_model = HistGradientBoostingRegressor(
        max_iter=120,
        learning_rate=0.08,
        min_samples_leaf=15,
        random_state=seed
    )
    solar_model.fit(X_train, y_s_train)
    s_preds = solar_model.predict(X_val)
    
    s_rmse = float(np.sqrt(mean_squared_error(y_s_val, s_preds)))
    s_mae = float(mean_absolute_error(y_s_val, s_preds))
    s_r2 = float(r2_score(y_s_val, s_preds))
    
    # Save artifacts
    joblib.dump(demand_model, DEMAND_MODEL_PATH)
    joblib.dump(solar_model, SOLAR_MODEL_PATH)
    
    return {
        "status": "TRAINED",
        "samples_trained": len(X_train),
        "samples_validated": len(X_val),
        "demand_metrics": {
            "rmse": round(d_rmse, 3),
            "mae": round(d_mae, 3),
            "r2": round(d_r2, 4)
        },
        "solar_metrics": {
            "rmse": round(s_rmse, 3),
            "mae": round(s_mae, 3),
            "r2": round(s_r2, 4)
        }
    }
