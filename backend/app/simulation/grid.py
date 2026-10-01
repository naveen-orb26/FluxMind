from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class GridSnapshot(BaseModel):
    step: int
    timestamp: str
    demand_kw: float
    residential_kw: float
    ev_kw: float
    datacenter_kw: float
    pump_kw: float
    common_area_kw: float
    solar_kw: float
    solar_direct_kw: float
    solar_surplus_kw: float
    battery_charge_kw: float
    battery_discharge_kw: float
    battery_soc_kwh: float
    battery_soc_pct: float
    grid_import_kw: float
    grid_export_kw: float
    carbon_intensity_g_per_kwh: float
    price_per_kwh: float
    pcc_limit_kw: float
    pcc_violation: bool
    energy_balance_error: float


def generate_tou_tariff(
    horizon_steps: int = 96,
    off_peak_rate: float = 0.10,
    shoulder_rate: float = 0.15,
    peak_rate: float = 0.30,
    price_multiplier: float = 1.0
) -> List[float]:
    """
    Generates Time-Of-Use (TOU) tariff profile ($/kWh) for 96 timesteps.
    - Off-peak (00:00 - 06:00, steps 0..23): $0.10/kWh
    - Shoulder (06:00 - 16:00, steps 24..63): $0.15/kWh
    - Peak (16:00 - 21:00, steps 64..83): $0.30/kWh
    - Shoulder (21:00 - 24:00, steps 84..95): $0.15/kWh
    """
    prices: List[float] = []
    for step in range(horizon_steps):
        hour = step * 0.25
        if hour < 6.0:
            rate = off_peak_rate
        elif 6.0 <= hour < 16.0:
            rate = shoulder_rate
        elif 16.0 <= hour < 21.0:
            rate = peak_rate
        else:
            rate = shoulder_rate
        prices.append(round(rate * price_multiplier, 4))
    return prices


def compute_interval_balance(
    step: int,
    timestamp: str,
    residential_kw: float,
    ev_kw: float,
    datacenter_kw: float,
    pump_kw: float,
    common_area_kw: float,
    solar_kw: float,
    battery_charge_kw: float,
    battery_discharge_kw: float,
    battery_soc_kwh: float,
    battery_capacity_kwh: float,
    carbon_intensity_g_per_kwh: float,
    price_per_kwh: float,
    pcc_limit_kw: float = 2500.0,
    allow_export: bool = True
) -> GridSnapshot:
    """
    Computes exact energy balance at timestep t according to Section 8.3 & Section 22.
    Formula:
        Demand_t = Residential + EV + DataCenter + Pump + CommonArea
        SolarUsedDirectly_t = min(SolarPower_t, Demand_t)
        NetGridNeed_t = Demand_t - SolarUsedDirectly_t - BatteryDischarge_t
        GridImport_t = max(NetGridNeed_t, 0)
        GridExport_t = max(SolarPower_t - SolarUsedDirectly_t - BatteryCharge_t, 0) if allow_export else 0
    Validation:
        Demand_t + BatteryCharge_t + GridExport_t == SolarPower_t + BatteryDischarge_t + GridImport_t
    """
    # Pre-round all inputs to 3 decimal places to ensure component reconciliation
    res_kw = round(residential_kw, 3)
    ev_r_kw = round(ev_kw, 3)
    dc_r_kw = round(datacenter_kw, 3)
    pump_r_kw = round(pump_kw, 3)
    common_r_kw = round(common_area_kw, 3)
    demand_kw = round(res_kw + ev_r_kw + dc_r_kw + pump_r_kw + common_r_kw, 3)

    solar_kw = round(solar_kw, 3)
    bat_charge_kw = round(battery_charge_kw, 3)
    bat_discharge_kw = round(battery_discharge_kw, 3)

    solar_direct_kw = round(min(solar_kw, demand_kw), 3)
    solar_surplus_kw = round(max(0.0, solar_kw - solar_direct_kw), 3)

    # Battery charge cannot exceed surplus solar when charging from surplus
    bat_charge_kw = round(min(solar_surplus_kw, battery_charge_kw), 3)

    # Net remaining demand to be served by battery discharge and/or grid
    remaining_demand = round(demand_kw - solar_direct_kw, 3)
    bat_discharge_kw = round(min(remaining_demand, battery_discharge_kw), 3)

    net_grid_need = round(remaining_demand - bat_discharge_kw, 3)

    grid_import_kw = round(max(0.0, net_grid_need), 3)

    if allow_export:
        grid_export_kw = round(max(0.0, solar_surplus_kw - bat_charge_kw), 3)
    else:
        grid_export_kw = 0.0

    # Energy balance check: Total Consumption vs Total Generation/Supply
    total_sink = round(demand_kw + bat_charge_kw + grid_export_kw, 3)
    total_source = round(solar_kw + bat_discharge_kw + grid_import_kw, 3)
    balance_error = abs(total_sink - total_source)

    soc_pct = (battery_soc_kwh / max(1.0, battery_capacity_kwh)) * 100.0
    pcc_violation = grid_import_kw > pcc_limit_kw

    return GridSnapshot(
        step=step,
        timestamp=timestamp,
        demand_kw=demand_kw,
        residential_kw=res_kw,
        ev_kw=ev_r_kw,
        datacenter_kw=dc_r_kw,
        pump_kw=pump_r_kw,
        common_area_kw=common_r_kw,
        solar_kw=solar_kw,
        solar_direct_kw=solar_direct_kw,
        solar_surplus_kw=solar_surplus_kw,
        battery_charge_kw=bat_charge_kw,
        battery_discharge_kw=bat_discharge_kw,
        battery_soc_kwh=round(battery_soc_kwh, 3),
        battery_soc_pct=round(soc_pct, 2),
        grid_import_kw=grid_import_kw,
        grid_export_kw=grid_export_kw,
        carbon_intensity_g_per_kwh=round(carbon_intensity_g_per_kwh, 2),
        price_per_kwh=round(price_per_kwh, 4),
        pcc_limit_kw=pcc_limit_kw,
        pcc_violation=pcc_violation,
        energy_balance_error=round(balance_error, 6)
    )
