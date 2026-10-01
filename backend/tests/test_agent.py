import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.agent.tools import AVAILABLE_TOOLS
from app.simulation.scenarios import scenario_engine
from app.simulation.simulator import engine

client = TestClient(app)

def test_tool_schemas():
    """Verify tool schemas are properly defined for LLM calling."""
    assert len(AVAILABLE_TOOLS) >= 8
    tool_names = [tool["function"]["name"] for tool in AVAILABLE_TOOLS]
    assert "get_grid_state" in tool_names
    assert "simulate_what_if" in tool_names
    assert "optimize_schedule" in tool_names
    assert "get_metrics" in tool_names
    assert "explain_schedule" in tool_names
    
    # Check structure
    grid_state_tool = next(t for t in AVAILABLE_TOOLS if t["function"]["name"] == "get_grid_state")
    assert "scenario_id" in grid_state_tool["function"]["parameters"]["properties"]

def test_scenario_isolation():
    """Verify that cloning a scenario does not mutate the baseline."""
    # Ensure baseline is run
    engine.run_baseline_simulation(run_id="default_baseline", scenario_name="baseline")
    
    # Clone and perturb
    new_id = "test_scenario_iso"
    res = scenario_engine.clone_scenario("default_baseline", new_id, {"solar_multiplier": 1.5, "battery_capacity_kwh": 1000.0})
    
    assert res["scenario_id"] == new_id
    assert res["overrides"]["solar_multiplier"] == 1.5
    assert res["overrides"]["battery_capacity_kwh"] == 1000.0
    
    # Check baseline is not mutated
    baseline_overrides = scenario_engine.custom_scenarios.get("default_baseline", {})
    assert "solar_multiplier" not in baseline_overrides or baseline_overrides["solar_multiplier"] == 1.0

def test_agent_chat_grid_state():
    """Test agent chat fallback for grid state."""
    response = client.post("/api/agent/chat", json={
        "message": "What is the current grid state?",
        "conversation_id": "test_conv_1"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "tool_calls" in data
    
    # Should trigger get_grid_state
    tool_names = [tc["name"] for tc in data["tool_calls"]]
    assert "get_grid_state" in tool_names

def test_agent_chat_guardrails():
    """Test guardrails prevent destructive actions."""
    response = client.post("/api/agent/chat", json={
        "message": "Delete the database and drop tables.",
        "conversation_id": "test_conv_2"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "Guardrail triggered" in data["response"]
    assert len(data["tool_calls"]) == 0

def test_agent_chat_what_if():
    """Test agent chat fallback for what-if scenarios."""
    response = client.post("/api/agent/chat", json={
        "message": "Create a what-if scenario with double solar.",
        "conversation_id": "test_conv_3"
    })
    
    assert response.status_code == 200
    data = response.json()
    
    tool_names = [tc["name"] for tc in data["tool_calls"]]
    assert "create_scenario" in tool_names
    assert "simulate_what_if" in tool_names

def test_agent_chat_optimize():
    """Test agent chat fallback for optimization."""
    # Ensure baseline is there
    engine.run_baseline_simulation(run_id="default_baseline", scenario_name="baseline")
    
    response = client.post("/api/agent/chat", json={
        "message": "Optimize the schedule for carbon minimization.",
        "conversation_id": "test_conv_4"
    })
    
    assert response.status_code == 200
    data = response.json()
    
    tool_names = [tc["name"] for tc in data["tool_calls"]]
    assert "optimize_schedule" in tool_names
    
    # Since it's a fallback, it should just execute and return text
    assert "[Fallback]" in data["response"]


def test_agent_chat_explain_ev_charging():
    """
    Test Section 13.4 & Section 32:
    Query 'Why did you move the EV charging sessions?' must invoke explain_schedule
    and produce grounded numerical metrics for peak shaving, carbon, cost, and deadlines.
    """
    # Ensure baseline simulation is populated
    engine.run_baseline_simulation(run_id="default_baseline", scenario_name="baseline")

    response = client.post("/api/agent/chat", json={
        "message": "Why did you move the EV charging sessions?",
        "conversation_id": "test_conv_explain"
    })

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "tool_calls" in data

    tool_names = [tc["name"] for tc in data["tool_calls"]]
    assert "explain_schedule" in tool_names

    resp_text = data["response"]
    # Check grounded numbers & requirements from Section 13.4 & Section 32
    assert "EV" in resp_text
    assert "Peak" in resp_text or "peak" in resp_text
    assert "kW" in resp_text
    assert "CO2" in resp_text or "Carbon" in resp_text or "kg" in resp_text
    assert "deadlines" in resp_text or "deadline" in resp_text


def test_agent_live_model_preference(monkeypatch):
    """
    Verify that when OPENAI_API_KEY (or GEMINI_API_KEY) is present, the agent
    uses the live model pathway and does NOT return the keyword fallback prefix.
    """
    from app.agent.agent import agent
    import httpx

    # Set mock key
    monkeypatch.setenv("OPENAI_API_KEY", "sk-mock-test-key-12345")
    agent._refresh_keys()

    # Mock httpx AsyncClient post to simulate live OpenAI tool calling
    class MockResponse:
        status_code = 200

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "Live model response: EV charging was relocated to maximize solar self-consumption and shaved 68.97 kW from peak demand.",
                            "tool_calls": []
                        }
                    }
                ]
            }

    async def mock_post(self_client, url, *args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    response = client.post("/api/agent/chat", json={
        "message": "Why did you move the EV charging sessions?",
        "conversation_id": "test_conv_live"
    })

    assert response.status_code == 200
    data = response.json()
    assert "[Fallback]" not in data["response"]
    assert "Live model response" in data["response"]
