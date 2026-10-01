import os
import yaml
from typing import Dict, Any, List, Optional
from datetime import datetime

from .loads import (
    generate_residential_profiles,
    generate_common_area_profile,
    generate_ev_sessions,
    generate_community_flexible_loads,
    FlexibleLoad,
    Asset
)
from .solar import generate_solar_generation
from .battery import BatteryStorage, BatteryConfig
from .grid import generate_tou_tariff, GridSnapshot
from .baseline import BaselineScheduler
from ..carbon.intensity import generate_carbon_intensity_signal


class SimulationEngine:
    """
    Simulation Engine and Digital Twin coordinator.
    Implements Phase 1 simulation requirements:
    - 96 timesteps at 15-minute intervals.
    - Fixed seed = 42 for complete reproducibility.
    - Community assets: 100 apartments, 40 EV chargers, rooftop solar (250 kW),
      500 kWh battery, water pump (50 kW / 50 kWh), data-center batch (200 kW / 400 kWh).
    - Produces authoritative GridSnapshots with exact energy balance conservation.
    """

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            # Default to backend/configs relative to this file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_dir = os.path.join(current_dir, "..", "..", "configs")

        self.config_dir = config_dir
        # Cache of runs: run_id -> dict of results
        self.runs: Dict[str, Dict[str, Any]] = {}
        # Execute default baseline run upon initialization
        self.run_baseline_simulation(run_id="default_baseline", scenario_name="baseline")

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        path = os.path.join(self.config_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    @property
    def default_config(self) -> Dict[str, Any]:
        return self._load_yaml("default.yaml")

    @property
    def scenarios_config(self) -> Dict[str, Any]:
        return self._load_yaml("scenarios.yaml")

    @property
    def policies_config(self) -> Dict[str, Any]:
        return self._load_yaml("policies.yaml")

    def get_assets(self) -> List[Asset]:
        """Returns catalog of community assets according to Section 7.1 & Appendix A."""
        cfg = self.default_config
        comm = cfg.get("community", {})
        bat = cfg.get("battery", {})

        assets = [
            Asset(
                id="residential_apartments",
                type="residential",
                name="100 Residential Apartments",
                rated_power_kw=250.0,
                capacity_kwh=None,
                flexibility_class="inflexible"
            ),
            Asset(
                id="rooftop_solar_pv",
                type="solar",
                name="Community Rooftop Solar Array",
                rated_power_kw=float(comm.get("solar_capacity_kw", 250.0)),
                capacity_kwh=None,
                flexibility_class="curtailable"
            ),
            Asset(
                id="bess_500kwh",
                type="battery",
                name="Community Battery Energy Storage System (BESS)",
                rated_power_kw=float(comm.get("battery_power_kw", 250.0)),
                capacity_kwh=float(comm.get("battery_capacity_kwh", 500.0)),
                flexibility_class="storage"
            ),
            Asset(
                id="water_reservoir_pump_01",
                type="water_pump",
                name="Community Water Reservoir Pump",
                rated_power_kw=50.0,
                capacity_kwh=50.0,
                flexibility_class="deferrable"
            ),
            Asset(
                id="datacenter_cluster_01",
                type="data_center",
                name="Community AI Data Center Compute Cluster",
                rated_power_kw=200.0,
                capacity_kwh=400.0,
                flexibility_class="deferrable"
            )
        ]

        # 40 EV Chargers
        for i in range(1, comm.get("ev_chargers", 40) + 1):
            assets.append(
                Asset(
                    id=f"ev_charger_{i:02d}",
                    type="ev_charger",
                    name=f"Level-2 EV Charger #{i}",
                    rated_power_kw=7.2,
                    capacity_kwh=None,
                    flexibility_class="deferrable"
                )
            )

        return assets

    def run_baseline_simulation(
        self,
        run_id: str = "default_baseline",
        scenario_name: str = "baseline",
        overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Runs full 96-step deterministic baseline simulation with reproducible seed=42.
        """
        cfg = dict(self.default_config)
        scenario = self.scenarios_config.get("scenarios", {}).get(scenario_name, {})

        # Apply scenario and overrides
        sim_cfg = cfg.get("simulation", {})
        comm_cfg = cfg.get("community", {})
        bat_cfg = cfg.get("battery", {})
        flex_cfg = cfg.get("flexible_loads", {})
        carbon_cfg = cfg.get("carbon", {})
        price_cfg = cfg.get("pricing", {})

        seed = int(sim_cfg.get("random_seed", 42))
        horizon_steps = int(sim_cfg.get("horizon_steps", 96))

        solar_mult = float(scenario.get("solar_multiplier", 1.0))
        ev_count = int(scenario.get("ev_count", comm_cfg.get("ev_chargers", 40)))
        dc_power_kw = float(scenario.get("data_center_power_kw", flex_cfg.get("data_center", {}).get("flexible_power_kw", 200.0)))
        pcc_limit_kw = float(scenario.get("pcc_limit_kw", comm_cfg.get("pcc_limit_kw", 2500.0)))
        carbon_mult = float(scenario.get("carbon_multiplier", 1.0))
        price_mult = float(scenario.get("price_multiplier", 1.0))
        res_mult = float(scenario.get("residential_demand_multiplier", 1.0))
        batt_cap = float(scenario.get("battery_capacity_kwh", comm_cfg.get("battery_capacity_kwh", 500.0)))

        if overrides:
            solar_mult = float(overrides.get("solar_multiplier", solar_mult))
            ev_count = int(overrides.get("ev_count", ev_count))
            dc_power_kw = float(overrides.get("data_center_power_kw", dc_power_kw))
            pcc_limit_kw = float(overrides.get("pcc_limit_kw", pcc_limit_kw))
            carbon_mult = float(overrides.get("carbon_multiplier", carbon_mult))
            price_mult = float(overrides.get("price_multiplier", price_mult))
            res_mult = float(overrides.get("residential_demand_multiplier", res_mult))
            batt_cap = float(overrides.get("battery_capacity_kwh", batt_cap))

        # 1. Generate residential profiles
        res_data = generate_residential_profiles(
            num_apartments=int(comm_cfg.get("apartments", 100)),
            horizon_steps=horizon_steps,
            seed=seed
        )
        residential_kw = [val * res_mult for val in res_data["aggregate_kw"]]

        # 2. Common area load
        common_area_kw = generate_common_area_profile(
            horizon_steps=horizon_steps,
            base_kw=float(cfg.get("common_area", {}).get("base_kw", 80.0)),
            peak_kw=float(cfg.get("common_area", {}).get("peak_kw", 160.0))
        )

        # 3. Flexible loads (40 EVs, Data Center, Water Pump)
        ev_sessions = generate_ev_sessions(
            num_sessions=ev_count,
            horizon_steps=horizon_steps,
            charger_kw=float(flex_cfg.get("ev", {}).get("charger_kw", 7.2)),
            min_energy_kwh=float(flex_cfg.get("ev", {}).get("min_energy_kwh", 8.0)),
            max_energy_kwh=float(flex_cfg.get("ev", {}).get("max_energy_kwh", 24.0)),
            seed=seed
        )
        flexible_loads = generate_community_flexible_loads(
            ev_sessions=ev_sessions,
            datacenter_power_kw=dc_power_kw,
            datacenter_duration_hours=float(flex_cfg.get("data_center", {}).get("default_duration_hours", 2.0)),
            datacenter_pref_start_step=int(flex_cfg.get("data_center", {}).get("preferred_start_step", 40)),
            pump_power_kw=float(flex_cfg.get("water_pump", {}).get("power_kw", 50.0)),
            pump_energy_kwh=float(flex_cfg.get("water_pump", {}).get("required_energy_kwh", 50.0)),
            pump_pref_start_step=int(flex_cfg.get("water_pump", {}).get("preferred_start_step", 16))
        )

        # 4. Solar PV Generation
        solar_capacity_kw = float(comm_cfg.get("solar_capacity_kw", 250.0))
        solar_profile = generate_solar_generation(
            capacity_kw=solar_capacity_kw,
            horizon_steps=horizon_steps,
            solar_multiplier=solar_mult,
            seed=seed
        )

        # 5. Carbon Intensity Signal
        carbon_profile = generate_carbon_intensity_signal(
            solar_profile=solar_profile,
            solar_capacity_kw=solar_capacity_kw,
            baseline_g_per_kwh=float(carbon_cfg.get("baseline_g_per_kwh", 450.0)),
            solar_day_reduction_factor=float(carbon_cfg.get("solar_day_reduction_factor", 0.55)),
            evening_peak_multiplier=float(carbon_cfg.get("evening_peak_multiplier", 1.35)),
            carbon_multiplier=carbon_mult,
            horizon_steps=horizon_steps
        )

        # 6. Dynamic TOU Pricing
        price_profile = generate_tou_tariff(
            horizon_steps=horizon_steps,
            off_peak_rate=float(price_cfg.get("off_peak_rate", 0.10)),
            shoulder_rate=float(price_cfg.get("shoulder_rate", 0.15)),
            peak_rate=float(price_cfg.get("peak_rate", 0.30)),
            price_multiplier=price_mult
        )

        # 7. Battery Initialization
        battery = BatteryStorage(
            BatteryConfig(
                capacity_kwh=batt_cap,
                rated_power_kw=float(comm_cfg.get("battery_power_kw", 250.0)),
                min_soc_pct=float(bat_cfg.get("min_soc_pct", 20.0)),
                max_soc_pct=float(bat_cfg.get("max_soc_pct", 95.0)),
                initial_soc_pct=float(bat_cfg.get("initial_soc_pct", 50.0)),
                charge_efficiency=float(bat_cfg.get("charge_efficiency", 0.95)),
                discharge_efficiency=float(bat_cfg.get("discharge_efficiency", 0.95)),
                timestep_hours=0.25
            )
        )

        # 8. Execute Baseline Scheduler
        scheduler = BaselineScheduler(
            residential_kw=residential_kw,
            common_area_kw=common_area_kw,
            flexible_loads=flexible_loads,
            solar_profile=solar_profile,
            carbon_profile=carbon_profile,
            price_profile=price_profile,
            battery=battery,
            pcc_limit_kw=pcc_limit_kw,
            horizon_steps=horizon_steps,
            timestep_hours=0.25
        )

        snapshots, summary = scheduler.run()

        result = {
            "run_id": run_id,
            "scenario": scenario_name,
            "seed": seed,
            "horizon_steps": horizon_steps,
            "created_at": datetime.now().isoformat(),
            "snapshots": [s.model_dump() for s in snapshots],
            "summary": summary,
            "flexible_loads": [load.model_dump() for load in flexible_loads],
            "residential_summary": {
                "mean_apartment_kw": res_data["mean_apartment_kw"],
                "peak_apartment_kw": res_data["peak_apartment_kw"],
                "total_apartments": int(comm_cfg.get("apartments", 100))
            }
        }

        self.runs[run_id] = result
        return result

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        return self.runs.get(run_id)


# Global singleton instance for app state
engine = SimulationEngine()
