from typing import Dict, Any, Optional
import copy
from .simulator import engine

class ScenarioEngine:
    """
    What-If Scenario Engine.
    Implements parameter perturbation engine (Section 26).
    Enforces scenario isolation: cloning a scenario never mutates the parent.
    """

    def __init__(self):
        # Cache for customized scenarios: scenario_id -> override dict
        self.custom_scenarios: Dict[str, Dict[str, Any]] = {}
        # We also need a mapping to keep track of policies, etc.
        self.scenario_metadata: Dict[str, Dict[str, Any]] = {}

    def clone_scenario(
        self,
        base_scenario_id: str,
        new_scenario_id: str,
        overrides: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Clones an existing scenario and applies parameter perturbations.
        Creates a new, isolated set of overrides.
        """
        if base_scenario_id == "baseline" or base_scenario_id == "default_baseline":
            base_overrides = {}
            base_metadata = {"policy": "baseline"}
        else:
            base_overrides = copy.deepcopy(self.custom_scenarios.get(base_scenario_id, {}))
            base_metadata = copy.deepcopy(self.scenario_metadata.get(base_scenario_id, {"policy": "baseline"}))
        
        # Apply new overrides (perturbations)
        # Supported overrides: solar_multiplier, residential_demand_multiplier, ev_count,
        # data_center_power_kw, battery_capacity_kwh, pcc_limit_kw, policy.
        
        if isinstance(overrides, str):
            try:
                import json
                overrides = json.loads(overrides)
            except Exception:
                overrides = {}

        new_overrides = {**base_overrides}

        # 1. Flexible solar perturbations (multiplier vs percentage drop)
        if "solar_multiplier" in overrides:
            val = float(overrides["solar_multiplier"])
            new_overrides["solar_multiplier"] = max(0.0, val)
        elif any(k in overrides for k in ["solar_drop_pct", "solar_reduction_pct", "solar_drop", "cloud_cover_pct", "cloudy_pct", "solar_decrease_pct", "solar_reduction"]):
            for k in ["solar_drop_pct", "solar_reduction_pct", "solar_drop", "cloud_cover_pct", "cloudy_pct", "solar_decrease_pct", "solar_reduction"]:
                if k in overrides:
                    drop = float(overrides[k])
                    if drop > 1.0:
                        drop = drop / 100.0
                    new_overrides["solar_multiplier"] = max(0.0, round(1.0 - drop, 4))
                    break

        # 2. Flexible EV count perturbations (total vs additional EVs)
        base_evs = int(engine.default_config.get("community", {}).get("ev_chargers", 40))
        if any(k in overrides for k in ["additional_evs", "extra_evs", "new_evs", "added_evs", "ev_delta"]):
            for k in ["additional_evs", "extra_evs", "new_evs", "added_evs", "ev_delta"]:
                if k in overrides:
                    extra = int(overrides[k])
                    new_overrides["ev_count"] = base_evs + extra
                    break
        elif "ev_count" in overrides:
            new_overrides["ev_count"] = int(overrides["ev_count"])

        # 3. Flexible residential demand perturbations
        if "residential_demand_multiplier" in overrides:
            new_overrides["residential_demand_multiplier"] = float(overrides["residential_demand_multiplier"])
        elif any(k in overrides for k in ["demand_increase_pct", "demand_growth_pct"]):
            for k in ["demand_increase_pct", "demand_growth_pct"]:
                if k in overrides:
                    inc = float(overrides[k])
                    if inc > 1.0:
                        inc = inc / 100.0
                    new_overrides["residential_demand_multiplier"] = round(1.0 + inc, 4)
                    break

        # 4. Standard community overrides
        for key in ["data_center_power_kw", "battery_capacity_kwh", "pcc_limit_kw",
                    "carbon_multiplier", "price_multiplier"]:
            if key in overrides:
                new_overrides[key] = float(overrides[key])

        if "policy" in overrides:
            base_metadata["policy"] = overrides["policy"]

        self.custom_scenarios[new_scenario_id] = new_overrides
        self.scenario_metadata[new_scenario_id] = base_metadata
        
        return {
            "scenario_id": new_scenario_id,
            "base_scenario_id": base_scenario_id,
            "overrides": new_overrides,
            "metadata": base_metadata
        }

    def run_scenario(self, scenario_id: str) -> Dict[str, Any]:
        """
        Runs the simulation for a given scenario using the isolated overrides.
        If optimization policy is set and not 'baseline', it should ideally
        run the optimization engine. For now, it delegates to SimulationEngine
        if it's just a baseline parameter perturbation.
        (Integration with optimization is handled at a higher level or by the agent).
        """
        overrides = self.custom_scenarios.get(scenario_id, {})
        # Note: the actual execution of an optimized scenario vs baseline 
        # is handled by calling OptimizationEngine vs SimulationEngine.
        # This method just runs the baseline with the new parameters.
        result = engine.run_baseline_simulation(
            run_id=scenario_id,
            scenario_name="baseline",  # Base scenario structure is always baseline
            overrides=overrides
        )
        # Attach policy metadata to result
        metadata = self.scenario_metadata.get(scenario_id, {"policy": "baseline"})
        result["policy"] = metadata["policy"]
        return result

scenario_engine = ScenarioEngine()
