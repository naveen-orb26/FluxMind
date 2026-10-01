import numpy as np
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class FlexibleLoad(BaseModel):
    id: str
    asset_id: str
    name: str
    load_type: str  # "ev", "data_center", "water_pump"
    energy_required_kwh: float
    earliest_start: int  # Timestep index (0..95)
    latest_end: int  # Timestep deadline index (0..95)
    max_power_kw: float
    priority: int = 1  # 1 = High, 2 = Medium, 3 = Low
    interruptible: bool = True
    # Baseline assignment tracking
    scheduled_power: List[float] = Field(default_factory=list)


class Asset(BaseModel):
    id: str
    type: str  # "residential", "ev_charger", "solar", "battery", "data_center", "water_pump"
    name: str
    rated_power_kw: float
    capacity_kwh: Optional[float] = None
    flexibility_class: str  # "inflexible", "deferrable", "storage", "curtailable"


def generate_residential_profiles(
    num_apartments: int = 100,
    horizon_steps: int = 96,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Generates synthetic daily residential demand profiles for 100 apartments.
    Section 7.3: Base curve (occupancy, appliances, HVAC) + bounded stochastic variance.
    15-minute intervals (96 timesteps per day).
    Average baseline: 0.8 - 1.2 kW per apartment.
    Evening peak: 1.5 - 2.5 kW per apartment.
    """
    rng = np.random.RandomState(seed)
    timesteps = np.arange(horizon_steps)
    hours = timesteps * 0.25  # 0.0 to 23.75

    # Diurnal normalized component templates
    # Overnight low (00:00 - 06:00): ~0.35 kW
    # Morning wake peak (07:00 - 09:00): ~1.3 kW
    # Daytime lull/plateau (10:00 - 16:00): ~0.85 kW
    # Evening dinner/entertainment peak (18:00 - 22:00): ~2.1 kW
    morning_bell = np.exp(-0.5 * ((hours - 7.5) / 1.2) ** 2)
    evening_bell = np.exp(-0.5 * ((hours - 20.0) / 1.8) ** 2)
    day_plateau = 0.5 * (1.0 / (1.0 + np.exp(-(hours - 9.0))) - 1.0 / (1.0 + np.exp(-(hours - 17.0))))

    base_curve = 0.35 + 0.95 * morning_bell + 0.45 * day_plateau + 1.65 * evening_bell

    apartment_profiles = np.zeros((num_apartments, horizon_steps))

    for i in range(num_apartments):
        # Apartment specific scaling factors
        scale = rng.uniform(0.85, 1.15)
        # Shift peak slightly to represent individual occupant schedules
        phase_shift = rng.randint(-3, 4)
        shifted_base = np.roll(base_curve, phase_shift)

        # High-frequency bounded noise
        noise = rng.normal(0, 0.08, horizon_steps)
        # Random appliance spikes (e.g. microwave, kettle, toaster, oven)
        spike_prob = rng.uniform(0.02, 0.06)
        spikes = (rng.rand(horizon_steps) < spike_prob) * rng.uniform(0.5, 1.8, horizon_steps)

        apt_load = np.maximum(0.2, (shifted_base * scale) + noise + spikes)
        apartment_profiles[i, :] = apt_load

    community_residential_kw = np.sum(apartment_profiles, axis=0)

    return {
        "apartment_profiles": apartment_profiles.tolist(),
        "aggregate_kw": community_residential_kw.tolist(),
        "mean_apartment_kw": float(np.mean(apartment_profiles)),
        "peak_apartment_kw": float(np.max(np.mean(apartment_profiles, axis=0)))
    }


def generate_common_area_profile(
    horizon_steps: int = 96,
    base_kw: float = 80.0,
    peak_kw: float = 160.0
) -> List[float]:
    """
    Common-area / commercial baseline: lighting, water pressurization, hallway HVAC, elevators.
    Peaks in morning and evening activity hours.
    """
    timesteps = np.arange(horizon_steps)
    hours = timesteps * 0.25

    # Daytime lighting and HVAC increase
    activity = 0.4 * np.exp(-0.5 * ((hours - 8.0) / 2.0) ** 2) + 0.6 * np.exp(-0.5 * ((hours - 19.0) / 2.5) ** 2)
    day_offset = 0.3 * np.sin(np.pi * np.clip((hours - 6.0) / 16.0, 0, 1))

    curve = base_kw + (peak_kw - base_kw) * np.clip(activity + day_offset, 0.0, 1.0)
    return curve.tolist()


def generate_ev_sessions(
    num_sessions: int = 40,
    horizon_steps: int = 96,
    charger_kw: float = 7.2,
    min_energy_kwh: float = 8.0,
    max_energy_kwh: float = 24.0,
    seed: int = 42
) -> List[FlexibleLoad]:
    """
    Generates 40 EV charging sessions with arrival times, departure deadlines, and energy requests.
    Appendix A & Section 7.1.
    """
    rng = np.random.RandomState(seed)
    sessions: List[FlexibleLoad] = []

    # Majority arrive in afternoon/evening (16:00 to 20:00 -> steps 64 to 80)
    # A few arrive during daytime or morning
    for i in range(num_sessions):
        session_id = f"ev_session_{i+1:02d}"
        asset_id = f"ev_charger_{(i % 40) + 1:02d}"

        energy_req = round(float(rng.uniform(min_energy_kwh, max_energy_kwh)), 2)
        # Compute minimum timesteps needed to deliver energy at max charger power
        # Each step delivers charger_kw * 0.25 kWh = 1.8 kWh
        steps_needed = int(np.ceil(energy_req / (charger_kw * 0.25)))

        # 80% evening commuters (16:00 - 20:30), 20% morning/midday (08:00 - 13:00)
        is_commuter = rng.rand() < 0.8
        if is_commuter:
            # Arrival between 16:00 (step 64) and 20:30 (step 82)
            arr = rng.randint(64, 82)
            # Departure deadline: next morning (steps 92 to 95 or step 95)
            deadline = min(horizon_steps - 1, arr + steps_needed + rng.randint(4, 16))
        else:
            # Daytime arrival between 08:30 (step 34) and 12:30 (step 50)
            arr = rng.randint(34, 50)
            # Departure in evening (steps 68 to 80)
            deadline = min(horizon_steps - 1, arr + steps_needed + rng.randint(8, 20))

        # Ensure deadline is feasible
        if deadline < arr + steps_needed:
            deadline = min(horizon_steps - 1, arr + steps_needed + 2)

        sessions.append(
            FlexibleLoad(
                id=session_id,
                asset_id=asset_id,
                name=f"EV Session #{i+1} ({energy_req} kWh)",
                load_type="ev",
                energy_required_kwh=energy_req,
                earliest_start=int(arr),
                latest_end=int(deadline),
                max_power_kw=charger_kw,
                priority=2,
                interruptible=True
            )
        )

    return sessions


def generate_community_flexible_loads(
    ev_sessions: List[FlexibleLoad],
    datacenter_power_kw: float = 200.0,
    datacenter_duration_hours: float = 2.0,
    datacenter_pref_start_step: int = 40,
    pump_power_kw: float = 50.0,
    pump_energy_kwh: float = 50.0,
    pump_pref_start_step: int = 16
) -> List[FlexibleLoad]:
    """
    Creates complete list of flexible loads including:
    - 40 EV charging sessions
    - 1 Batch Data Center workload (200 kW, 2h = 400 kWh)
    - 1 Water Pump workload (50 kW, 1h = 50 kWh)
    """
    loads: List[FlexibleLoad] = list(ev_sessions)

    # 1. Batch Data Center Load
    # 200 kW * 2h = 400 kWh (8 intervals)
    dc_steps = int(datacenter_duration_hours / 0.25)
    loads.append(
        FlexibleLoad(
            id="datacenter_batch_01",
            asset_id="datacenter_cluster_01",
            name="Community AI Data Center Batch Processing",
            load_type="data_center",
            energy_required_kwh=datacenter_power_kw * datacenter_duration_hours,
            earliest_start=datacenter_pref_start_step,
            latest_end=min(95, datacenter_pref_start_step + dc_steps + 20),
            max_power_kw=datacenter_power_kw,
            priority=3,  # Discretionary/deferrable computation
            interruptible=True
        )
    )

    # 2. Water Pump Load
    # 50 kW * 1h = 50 kWh (4 intervals)
    pump_steps = int(np.ceil(pump_energy_kwh / (pump_power_kw * 0.25)))
    loads.append(
        FlexibleLoad(
            id="water_pump_01",
            asset_id="water_reservoir_pump_01",
            name="Community Water Reservoir Pumping",
            load_type="water_pump",
            energy_required_kwh=pump_energy_kwh,
            earliest_start=pump_pref_start_step,
            latest_end=min(95, pump_pref_start_step + pump_steps + 16),
            max_power_kw=pump_power_kw,
            priority=2,
            interruptible=False
        )
    )

    return loads
