from typing import Tuple
from pydantic import BaseModel, Field


class BatteryConfig(BaseModel):
    capacity_kwh: float = 500.0
    rated_power_kw: float = 250.0
    min_soc_pct: float = 20.0
    max_soc_pct: float = 95.0
    initial_soc_pct: float = 50.0
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.95
    timestep_hours: float = 0.25


class BatteryState(BaseModel):
    step: int
    soc_kwh: float
    soc_pct: float
    charge_kw: float
    discharge_kw: float


class BatteryStorage:
    """
    Physical model of Battery Energy Storage System (BESS).
    Section 9:
        SOC_{t+1} = SOC_t + (eta_charge * ChargePower_t * dt) - (DischargePower_t * dt / eta_discharge)
        SOC_min <= SOC_t <= SOC_max
        0 <= ChargePower_t <= P_charge_max
        0 <= DischargePower_t <= P_discharge_max
        ChargePower_t * DischargePower_t = 0
    """

    def __init__(self, config: BatteryConfig):
        self.config = config
        self.min_soc_kwh = (config.min_soc_pct / 100.0) * config.capacity_kwh
        self.max_soc_kwh = (config.max_soc_pct / 100.0) * config.capacity_kwh
        self.soc_kwh = (config.initial_soc_pct / 100.0) * config.capacity_kwh
        self.dt = config.timestep_hours

    def get_max_charge_power(self) -> float:
        """Maximum power (kW) the battery can absorb during this timestep without exceeding max_soc."""
        headroom_kwh = max(0.0, self.max_soc_kwh - self.soc_kwh)
        power_by_capacity = headroom_kwh / (self.config.charge_efficiency * self.dt)
        return min(self.config.rated_power_kw, power_by_capacity)

    def get_max_discharge_power(self) -> float:
        """Maximum power (kW) the battery can deliver during this timestep without violating min_soc."""
        available_kwh = max(0.0, self.soc_kwh - self.min_soc_kwh)
        power_by_capacity = (available_kwh * self.config.discharge_efficiency) / self.dt
        return min(self.config.rated_power_kw, power_by_capacity)

    def step(self, charge_kw: float, discharge_kw: float) -> Tuple[float, float, float]:
        """
        Executes one timestep state transition.
        Enforces no simultaneous charge/discharge, clips within physical limits.
        Returns: (actual_charge_kw, actual_discharge_kw, new_soc_kwh)
        """
        if charge_kw > 0.0 and discharge_kw > 0.0:
            raise ValueError(
                f"Physically impossible simultaneous charge ({charge_kw} kW) and discharge ({discharge_kw} kW)"
            )

        actual_charge_kw = 0.0
        actual_discharge_kw = 0.0

        if charge_kw > 0.0:
            max_p = self.get_max_charge_power()
            actual_charge_kw = min(charge_kw, max_p)
            energy_in = self.config.charge_efficiency * actual_charge_kw * self.dt
            self.soc_kwh = min(self.max_soc_kwh, self.soc_kwh + energy_in)

        elif discharge_kw > 0.0:
            max_p = self.get_max_discharge_power()
            actual_discharge_kw = min(discharge_kw, max_p)
            energy_out = (actual_discharge_kw * self.dt) / self.config.discharge_efficiency
            self.soc_kwh = max(self.min_soc_kwh, self.soc_kwh - energy_out)

        # Enforce numerical bounds tolerance
        self.soc_kwh = round(self.soc_kwh, 6)
        return actual_charge_kw, actual_discharge_kw, self.soc_kwh
