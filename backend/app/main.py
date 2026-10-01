from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import grid_router, simulation_router, optimization_router, forecasting_router, agent_router

app = FastAPI(
    title="AI-Powered Community Energy Orchestrator API",
    description="Digital-Twin Simulation, Carbon-Aware DER Orchestration, ML Forecasting & Agentic Copilot",
    version="1.0.0"
)

# Configure CORS for Next.js frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Section 17 & 24 routers
app.include_router(grid_router)
app.include_router(simulation_router)
app.include_router(optimization_router)
app.include_router(forecasting_router)
app.include_router(agent_router)


@app.get("/")
def root():
    return {
        "service": "AI-Powered Community Energy Orchestrator",
        "status": "ONLINE",
        "version": "1.0.0",
        "phase": "Phase 3 - ML Forecasting, Evaluation Metrics, and Full REST Endpoints"
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
