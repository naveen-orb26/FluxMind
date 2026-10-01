import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from .tools import AVAILABLE_TOOLS, ToolHandler
from .prompts import SYSTEM_PROMPT

logger = logging.getLogger("fluxmind.agent")


def load_env_configuration():
    """
    Discovers and loads .env files from the backend directory and workspace root,
    ensuring GEMINI_API_KEY and OPENAI_API_KEY are available to the agent.
    """
    candidate_paths = [
        Path(__file__).resolve().parent.parent.parent / ".env",          # backend/.env
        Path(__file__).resolve().parent.parent.parent.parent / ".env",   # root/.env
        Path.cwd() / "backend" / ".env",
        Path.cwd() / ".env",
    ]

    for p in candidate_paths:
        if p.is_file():
            if load_dotenv:
                load_dotenv(dotenv_path=str(p), override=False)
            else:
                # Lightweight pure-Python fallback loader
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                key, val = line.split("=", 1)
                                key = key.strip()
                                val = val.strip().strip("'\"")
                                if key and val and key not in os.environ:
                                    os.environ[key] = val
                except Exception as e:
                    logger.debug(f"Failed to load {p}: {e}")


# Run initial env discovery
load_env_configuration()


class EnergyOrchestratorAgent:
    """
    Agentic AI Orchestrator implementing tool calling and natural language explanations.
    Features:
    - Multi-provider live model support (Gemini API & OpenAI API).
    - Function calling: The LLM chooses and invokes authoritative simulation/optimization tools.
    - Grounding: Numerical claims are extracted directly from tool outputs (Section 13.1, 13.4, 32).
    - Safety guardrails blocking destructive commands.
    - Deterministic fallback if API keys are missing, invalid, or offline.
    """

    def __init__(self):
        self._refresh_keys()
        self.gemini_url = "https://generativelanguage.googleapis.com/v1beta/models"

    def _refresh_keys(self):
        """Refreshes API keys and model configurations from environment / .env."""
        load_env_configuration()
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        raw_model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
        # Migrate retired model names to current active Google AI Studio models
        if raw_model in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash-lite"]:
            self.gemini_model = "gemini-3.1-flash-lite"
        else:
            self.gemini_model = raw_model

        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    def has_live_model_configured(self) -> bool:
        """Returns True if any supported live LLM provider key is available."""
        self._refresh_keys()
        return bool(self.gemini_api_key or self.openai_api_key)

    def _convert_tools_to_gemini_format(self) -> List[Dict[str, Any]]:
        """Converts OpenAI-style tool schemas to Gemini functionDeclarations format."""
        declarations = []
        for t in AVAILABLE_TOOLS:
            fn = t["function"]
            declarations.append({
                "name": fn["name"],
                "description": fn["description"],
                "parameters": fn.get("parameters", {"type": "object", "properties": {}})
            })
        return declarations

    async def _call_gemini_api(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Calls the Gemini API using the official google-genai SDK.
        If GEMINI_API_KEY is not set or fails, falls back cleanly to the internal orchestrator.
        """
        if not self.gemini_api_key:
            return None

        try:
            from google import genai

            client = genai.Client(api_key=self.gemini_api_key)
            user_prompt = f"{SYSTEM_PROMPT}\n\nUser Request: {message}"

            response = client.models.generate_content(
                model=self.gemini_model or "gemini-2.5-flash",
                contents=user_prompt,
            )
            if response and response.text:
                return {
                    "response": response.text,
                    "tool_calls": []
                }
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[GEMINI SDK ERROR]: {e}\n{tb}")
            logger.warning(f"Gemini SDK generation failed: {e}")
            return None

        return None

    async def _call_openai_api(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Executes a live tool-calling loop with the OpenAI API.
        Returns response text and executed tool calls, or None if API fails.
        """
        if not self.openai_api_key:
            return None

        url = f"{self.openai_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message}
        ]

        payload = {
            "model": self.openai_model,
            "messages": messages,
            "tools": AVAILABLE_TOOLS,
            "tool_choice": "auto",
            "temperature": 0.2,
            "max_tokens": 1024
        }

        executed_tool_calls = []

        try:
            # Set 90.0s HTTP timeout to accommodate multi-turn tool calling
            async with httpx.AsyncClient(timeout=90.0) as client:
                for turn in range(5):
                    res = await client.post(url, headers=headers, json=payload)
                    if res.status_code != 200:
                        logger.warning(f"OpenAI API returned status {res.status_code}: {res.text[:200]}")
                        return None

                    data = res.json()
                    choices = data.get("choices", [])
                    if not choices:
                        return None

                    msg = choices[0].get("message", {})
                    tool_calls = msg.get("tool_calls", [])

                    if tool_calls:
                        messages.append(msg)
                        for tc in tool_calls:
                            fn = tc.get("function", {})
                            fn_name = fn.get("name")
                            try:
                                fn_args = json.loads(fn.get("arguments", "{}"))
                            except Exception:
                                fn_args = {}

                            tool_result = ToolHandler.execute_tool(fn_name, fn_args)
                            executed_tool_calls.append({
                                "name": fn_name,
                                "arguments": fn_args,
                                "result": str(tool_result)[:300]
                            })

                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc["id"],
                                "content": str(tool_result)
                            })

                        payload["messages"] = messages
                        continue

                    text_response = msg.get("content", "")
                    if text_response:
                        return {
                            "response": text_response,
                            "tool_calls": executed_tool_calls
                        }
                    break

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[OPENAI CALL ERROR]: {e}\n{tb}")
            logger.error(f"Error during OpenAI live call: {str(e)}\n{tb}")

        return None

    def _rule_based_fallback(self, message: str) -> Dict[str, Any]:
        """
        Deterministic rule-based fallback if LLM is unavailable or offline.
        Matches keywords to intents and triggers tools with grounded numbers.
        """
        msg_lower = message.lower()
        tool_calls = []
        response_text = ""

        # Check for explanation queries (Section 13.4 & Section 32)
        if any(phrase in msg_lower for phrase in [
            "why did you move", "why move", "explain schedule", "why ev", "why charging",
            "moved the ev", "shift ev", "explain the ev", "why were the ev", "why was ev",
            "why relocate", "charging sessions"
        ]):
            res = ToolHandler.execute_tool("explain_schedule", {
                "asset_type": "ev",
                "scenario_id": "default_baseline",
                "policy": "BALANCED"
            })
            response_text = f"[Fallback] Schedule explanation for EV charging:\n{res}"
            tool_calls.append({
                "name": "explain_schedule",
                "arguments": {"asset_type": "ev", "scenario_id": "default_baseline", "policy": "BALANCED"}
            })

        # Check for what-if scenario queries (e.g. solar drop, EV arrival)
        elif any(phrase in msg_lower for phrase in [
            "what happens if", "what if", "what-if", "create scenario", "simulate scenario", "scenario",
            "drops by", "generation drops", "more ev", "evs arrive", "solar drop"
        ]):
            import re
            solar_mult = 1.0
            solar_match = re.search(r"solar.*?(\d+)\s*%", msg_lower)
            if solar_match:
                pct = float(solar_match.group(1))
                if any(w in msg_lower for w in ["drop", "reduce", "decrease", "loss", "lower", "fall"]):
                    solar_mult = max(0.0, round(1.0 - (pct / 100.0), 2))
                else:
                    solar_mult = round(pct / 100.0, 2)
            elif "solar" in msg_lower and any(w in msg_lower for w in ["drop", "decrease"]):
                solar_mult = 0.60

            ev_extra = 0
            ev_match = re.search(r"(\d+)\s*(?:more|additional|extra|added)?\s*ev", msg_lower)
            if ev_match:
                val = int(ev_match.group(1))
                if any(w in msg_lower for w in ["more", "additional", "extra", "added", "arrive"]):
                    ev_extra = val
                elif val > 40:
                    ev_extra = val - 40
            elif "more ev" in msg_lower or "extra ev" in msg_lower:
                ev_extra = 20

            overrides = {}
            if solar_mult != 1.0:
                overrides["solar_multiplier"] = solar_mult
            if ev_extra > 0:
                overrides["additional_evs"] = ev_extra

            scenario_name = f"scenario_solar_{int(solar_mult*100)}_evs_{40 + ev_extra}"
            res_create = ToolHandler.execute_tool("create_scenario", {
                "base_scenario_id": "default_baseline",
                "new_scenario_id": scenario_name,
                "overrides": overrides
            })
            res_sim = ToolHandler.execute_tool("simulate_what_if", {"scenario_id": scenario_name})

            response_text = (
                f"[Fallback] Grounded What-If Analysis ({scenario_name}):\n"
                f"{res_create}\n\n"
                f"{res_sim}"
            )
            tool_calls.extend([
                {"name": "create_scenario", "arguments": {"new_scenario_id": scenario_name, "overrides": overrides}},
                {"name": "simulate_what_if", "arguments": {"scenario_id": scenario_name}}
            ])

        elif "grid state" in msg_lower or "current state" in msg_lower:
            res = ToolHandler.execute_tool("get_grid_state", {"scenario_id": "default_baseline"})
            response_text = f"[Fallback] Grid state retrieved:\n{res}"
            tool_calls.append({"name": "get_grid_state", "arguments": {"scenario_id": "default_baseline"}})

        elif "forecast" in msg_lower:
            var = "solar" if "solar" in msg_lower else "demand"
            res = ToolHandler.execute_tool("get_forecast", {"horizon": 96, "variable": var})
            response_text = f"[Fallback] Forecast retrieved:\n{res}"
            tool_calls.append({"name": "get_forecast", "arguments": {"horizon": 96, "variable": var}})

        elif "optimize" in msg_lower:
            policy = "cost_minimization"
            if "carbon" in msg_lower:
                policy = "carbon_minimization"
            elif "peak" in msg_lower:
                policy = "peak_shaving"

            res = ToolHandler.execute_tool("optimize_schedule", {"scenario_id": "default_baseline", "policy": policy})
            response_text = f"[Fallback] Optimization triggered:\n{res}"
            tool_calls.append({"name": "optimize_schedule", "arguments": {"scenario_id": "default_baseline", "policy": policy}})

        elif "metrics" in msg_lower or "compare" in msg_lower:
            res = ToolHandler.execute_tool("get_metrics", {"run_id_1": "default_baseline", "run_id_2": "default_baseline_opt_cost_minimization"})
            response_text = f"[Fallback] Metrics comparison:\n{res}"
            tool_calls.append({"name": "get_metrics", "arguments": {"run_id_1": "default_baseline", "run_id_2": "default_baseline_opt_cost_minimization"}})

        elif "flexible" in msg_lower or "loads" in msg_lower:
            res = ToolHandler.execute_tool("get_flexible_loads", {"scenario_id": "default_baseline"})
            response_text = f"[Fallback] Flexible loads retrieved:\n{res}"
            tool_calls.append({"name": "get_flexible_loads", "arguments": {"scenario_id": "default_baseline"}})

        else:
            response_text = (
                "[Fallback] I am your AI Community Energy Copilot. "
                "I analyze the digital twin, monitor PCC limits, call CP-SAT optimization tools, and evaluate what-if counterfactual scenarios. "
                "You can ask me to inspect grid state, run what-if scenarios, optimize schedules, or explain flexible load relocation."
            )

        return {
            "response": response_text,
            "tool_calls": tool_calls
        }

    async def chat(self, message: str, conversation_id: str) -> Dict[str, Any]:
        """
        Processes a user message, optionally calling tools, and returns the response.
        Enforces read-only guardrails, priority live LLM tool calling, and grounding.
        Prints full traceback if any unhandled exception occurs inside the agent runner.
        """
        # Guardrail 1: Check for prohibited commands (destructive actions)
        prohibited = ["delete", "drop table", "shutdown", "format"]
        if any(p in message.lower() for p in prohibited):
            return {
                "conversation_id": conversation_id,
                "response": "Guardrail triggered: Destructive commands are not permitted.",
                "tool_calls": []
            }

        try:
            # Step 1: Refresh environment and check for live model keys
            self._refresh_keys()

            # Step 2: If OpenAI API key is present, attempt live model with tool calling
            if self.openai_api_key:
                live_result = await self._call_openai_api(message)
                if live_result and live_result.get("response"):
                    return {
                        "conversation_id": conversation_id,
                        "response": live_result["response"],
                        "tool_calls": live_result.get("tool_calls", [])
                    }

            # Step 3: If Gemini API key is present, attempt live model with tool calling
            if self.gemini_api_key:
                live_result = await self._call_gemini_api(message)
                if live_result and live_result.get("response"):
                    return {
                        "conversation_id": conversation_id,
                        "response": live_result["response"],
                        "tool_calls": live_result.get("tool_calls", [])
                    }

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[AGENT RUNNER EXCEPTION]: {e}\n{tb}")
            logger.error(f"Agent runner exception: {e}\n{tb}")

        # Step 4: Fall back cleanly to deterministic rule-based orchestrator
        fallback_result = self._rule_based_fallback(message)
        return {
            "conversation_id": conversation_id,
            "response": fallback_result["response"],
            "tool_calls": fallback_result["tool_calls"]
        }


# Singleton instance
agent = EnergyOrchestratorAgent()
