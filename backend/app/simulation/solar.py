import numpy as np
from typing import List


def generate_solar_generation(
    capacity_kw: float = 250.0,
    horizon_steps: int = 96,
    solar_multiplier: float = 1.0,
    seed: int = 42
) -> List[float]:
    """
    Generates synthetic 24-hour rooftop solar PV generation profile (96 timesteps).
    Section 8.1:
        SolarPower_t = SolarCapacity * SolarShape(hour_t) * WeatherFactor_t
        0 <= SolarPower_t <= SolarCapacity
    Sunrise at ~06:00 (step 24), Solar noon at ~12:30 (step 50), Sunset at ~19:00 (step 76).
    """
    rng = np.random.RandomState(seed)
    timesteps = np.arange(horizon_steps)
    hours = timesteps * 0.25

    sunrise_hour = 6.0
    sunset_hour = 19.0
    daylight_mask = (hours >= sunrise_hour) & (hours <= sunset_hour)

    # Normalized daylight curve using half-sine profile
    daylight_progress = (hours - sunrise_hour) / (sunset_hour - sunrise_hour)
    raw_shape = np.sin(np.pi * np.clip(daylight_progress, 0.0, 1.0))

    # Add slight bell-curve concentration around solar noon
    solar_noon_hour = (sunrise_hour + sunset_hour) / 2.0  # 12.5h
    bell = np.exp(-0.5 * ((hours - solar_noon_hour) / 3.0) ** 2)
    normalized_shape = 0.7 * raw_shape + 0.3 * bell
    normalized_shape = np.where(daylight_mask, normalized_shape, 0.0)

    # Slight realistic atmospheric noise for clear sky
    weather_noise = rng.normal(1.0, 0.02, horizon_steps)
    weather_noise = np.clip(weather_noise, 0.90, 1.05)

    solar_kw = capacity_kw * normalized_shape * weather_noise * solar_multiplier
    solar_kw = np.clip(solar_kw, 0.0, capacity_kw)

    # Zero out strictly outside daylight hours
    solar_kw = np.where(daylight_mask, solar_kw, 0.0)

    return [round(float(p), 3) for p in solar_kw]
