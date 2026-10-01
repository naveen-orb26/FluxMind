"""
Feature Engineering for Community Demand and Solar ML Forecasting.
Section 12.2 of System Design Specification.
"""

from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd
from datetime import datetime, timedelta


def build_weather_proxy(step: int, horizon_steps: int = 96, cloud_noise: float = 0.0) -> Dict[str, float]:
    """
    Synthesizes physical weather proxy features for a given 15-minute interval:
    - temperature_c: diurnal temperature curve (cool at night ~16°C, peak at 14:00 ~30°C)
    - cloud_factor: 0.0 (clear sky) to 1.0 (overcast)
    - solar_elevation_proxy: geometric proxy for clear-sky solar availability
    """
    hour_float = (step % 96) / 4.0  # 0.0 to 24.0
    
    # Temperature diurnal curve: min at 05:00, max at 15:00
    temp_base = 22.0
    temp_swing = 7.0 * np.sin(np.pi * (hour_float - 9.0) / 12.0)
    temperature_c = float(temp_base + temp_swing)
    
    # Solar elevation proxy: positive only during daylight (approx 06:00 to 18:30)
    # 06:00 is step 24, 18:30 is step 74
    if 24 <= (step % 96) <= 74:
        rel_daylight = ((step % 96) - 24) / 50.0  # 0 to 1
        solar_elevation = float(np.sin(np.pi * rel_daylight))
    else:
        solar_elevation = 0.0
        
    cloud_factor = float(np.clip(cloud_noise, 0.0, 1.0))
    
    return {
        "temperature_c": round(temperature_c, 2),
        "cloud_factor": round(cloud_factor, 3),
        "solar_elevation_proxy": round(solar_elevation, 4)
    }


def extract_features_df(
    timestamps: List[str],
    load_history: List[float],
    solar_history: List[float],
    cloud_factors: Optional[List[float]] = None
) -> pd.DataFrame:
    """
    Converts sequential time series into a rich tabular feature matrix:
    - Time: hour, minute_bucket (0..3), day_of_week, is_weekend
    - Lagged load: lag_1 (t-1), lag_4 (t-4, 1 hour prior), lag_96 (t-24h)
    - Rolling averages: rolling_load_4, rolling_load_12, rolling_solar_4
    - Weather proxy: temperature_c, cloud_factor, solar_elevation_proxy
    """
    n = len(timestamps)
    records = []
    
    for i in range(n):
        ts_str = timestamps[i]
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except Exception:
            dt = datetime(2026, 6, 1, 0, 0) + timedelta(minutes=15 * i)
            
        hour = dt.hour
        minute_bucket = dt.minute // 15
        day_of_week = dt.weekday()
        is_weekend = 1 if day_of_week >= 5 else 0
        
        # Lags with safe boundary fallback
        lag_1 = load_history[i - 1] if i >= 1 else load_history[0]
        lag_4 = load_history[i - 4] if i >= 4 else load_history[0]
        lag_96 = load_history[i - 96] if i >= 96 else (load_history[i % 96] if len(load_history) >= 96 else load_history[0])
        
        # Rolling averages
        start_4 = max(0, i - 3)
        rolling_load_4 = float(np.mean(load_history[start_4:i + 1]))
        rolling_solar_4 = float(np.mean(solar_history[start_4:i + 1]))
        
        start_12 = max(0, i - 11)
        rolling_load_12 = float(np.mean(load_history[start_12:i + 1]))
        
        cloud_val = cloud_factors[i] if (cloud_factors and i < len(cloud_factors)) else 0.0
        weather = build_weather_proxy(i, 96, cloud_noise=cloud_val)
        
        row = {
            "hour": hour,
            "minute_bucket": minute_bucket,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "load_lag_1": lag_1,
            "load_lag_4": lag_4,
            "load_lag_96": lag_96,
            "load_rolling_mean_4": rolling_load_4,
            "load_rolling_mean_12": rolling_load_12,
            "solar_rolling_mean_4": rolling_solar_4,
            "temperature_c": weather["temperature_c"],
            "cloud_factor": weather["cloud_factor"],
            "solar_elevation_proxy": weather["solar_elevation_proxy"]
        }
        records.append(row)
        
    return pd.DataFrame(records)


FEATURE_COLUMNS = [
    "hour",
    "minute_bucket",
    "day_of_week",
    "is_weekend",
    "load_lag_1",
    "load_lag_4",
    "load_lag_96",
    "load_rolling_mean_4",
    "load_rolling_mean_12",
    "solar_rolling_mean_4",
    "temperature_c",
    "cloud_factor",
    "solar_elevation_proxy"
]
