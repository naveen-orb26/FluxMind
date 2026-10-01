import numpy as np
from typing import List, Optional


def generate_carbon_intensity_signal(
    solar_profile: List[float],
    solar_capacity_kw: float = 250.0,
    baseline_g_per_kwh: float = 450.0,
    solar_day_reduction_factor: float = 0.55,
    evening_peak_multiplier: float = 1.35,
    carbon_multiplier: float = 1.0,
    horizon_steps: int = 96
) -> List[float]:
    """
    Generates time-varying grid carbon intensity (gCO2e/kWh) across the 96 timesteps.
    Section 6 & Appendix A:
    - High solar generation reduces marginal grid carbon intensity (clean energy displacement).
    - Evening peak demands peaker plants, increasing marginal grid carbon intensity.
    - Yields ~200 gCO2e/kWh during solar-rich afternoon and ~600 gCO2e/kWh during evening peak.
    """
    timesteps = np.arange(horizon_steps)
    hours = timesteps * 0.25

    solar_arr = np.array(solar_profile)
    solar_ratio = np.clip(solar_arr / max(1.0, solar_capacity_kw), 0.0, 1.0)

    # Reduction from solar generation displacement
    solar_reduction = 1.0 - (solar_day_reduction_factor * solar_ratio)

    # Evening peak peaker plant effect (18:00 - 22:00, peak at 20:00)
    evening_peaker = np.exp(-0.5 * ((hours - 20.0) / 1.8) ** 2)
    peaker_factor = 1.0 + (evening_peak_multiplier - 1.0) * evening_peaker

    # Combined intensity
    intensity = baseline_g_per_kwh * solar_reduction * peaker_factor * carbon_multiplier

    return [round(float(c), 2) for c in intensity]


def calculate_operational_emissions(
    grid_import_kwh: List[float],
    carbon_intensity_g_per_kwh: List[float]
) -> float:
    """
    Calculates total operational CO2e emissions in kgCO2e.
    Section 6.3:
        OperationalCO2e_t = GridImportEnergy_t (kWh) * CarbonIntensity_t (gCO2e/kWh)
        TotalOperationalCO2e = sum(OperationalCO2e_t) / 1000.0 (kgCO2e)
    """
    total_g = sum(e * c for e, c in zip(grid_import_kwh, carbon_intensity_g_per_kwh))
    return round(total_g / 1000.0, 3)
