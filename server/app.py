import asyncio
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from simulation_manager import SimulationManager
from websocket_handler import WebSocketManager


import os

simulation = None
ws_manager = WebSocketManager()


def get_config():
    return {
        "agent_count": int(os.getenv("THRONGLETS_AGENTS", "12")),
        "use_llm": os.getenv("THRONGLETS_LLM", "True").lower() == "true",
        "api_key": os.getenv("API_KEY", ""),
        "base_url": os.getenv("BASE_URL", "https://ai.hackclub.com/proxy/v1"),
        "model_name": os.getenv("MODEL_NAME", "openai/gpt-oss-120b"),
    }


@asynccontextmanager
async def lifespan(app):
    global simulation
    yield
    if simulation:
        simulation.cleanup()


def create_app():
    app = FastAPI(
        title="Thronglets Simulation Server",
        lifespan=lifespan,
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/api/status")
    async def get_status():
        if not simulation:
            return {"initialized": False, "running": False}
        return {
            "initialized": True,
            "tick": simulation.tick_engine.current_tick if simulation._initialized else 0,
            "running": simulation._running and not simulation._paused,
            "paused": simulation._paused,
            "agentCount": simulation.agent_manager.agent_count() if simulation.agent_manager else 0,
            "connections": ws_manager.connection_count,
        }
        
    @app.get("/api/state")
    async def get_state():
        if not simulation or not simulation._initialized:
            return {"tick": 0, "running": False, "paused": False, "agents": [], "locations": []}
        return simulation.get_state()
        
    @app.get("/api/metrics")
    async def get_metrics():
        if not simulation or not simulation._initialized:
            return {"tick": 0, "agentCount": 0, "agentTypes": {}, "wealth": {}, "trade": {}, "specialization": {}, "groups": [], "tradeVolume": [], "giniHistory": []}
        return simulation.get_metrics()
        
    @app.get("/api/events")
    async def get_events(limit: int = Query(100, ge=1, le=500)):
        if not simulation or not simulation._initialized:
            return []
        return simulation.get_events(limit)
        
    @app.get("/api/agents/{agent_id}")
    async def get_agent(agent_id: str):
        if not simulation:
            return JSONResponse({"error": "Simulation not initialized"}, status_code=503)
        detail = simulation.get_agent_detail(agent_id)
        if not detail:
            return JSONResponse({"error": "Agent not found"}, status_code=404)
        return detail
        
    @app.get("/api/locations")
    async def get_locations():
        if not simulation:
            return JSONResponse({"error": "Simulation not initialized"}, status_code=503)
        locations = []
        for loc_id, node in simulation.location_graph.nodes.items():
            pos = simulation._location_positions.get(loc_id, {"x": 450, "y": 350})
            locations.append({
                "id": loc_id,
                "name": node.name,
                "type": node.location_type,
                "x": pos["x"],
                "y": pos["y"],
                "resources": dict(node.resource_richness),
            })
        return locations
    
    @app.get("/api/config")
    async def get_api_config():
        config = get_config()
        return {
            "apiKey": "***" if config["api_key"] else "",
            "baseUrl": config["base_url"],
            "modelName": config["model_name"],
            "useLlm": config["use_llm"],
            "agentCount": config["agent_count"],
        }
    
    @app.post("/api/config")
    async def set_api_config(
        api_key: str = Query(None),
        base_url: str = Query(None),
        model_name: str = Query(None),
    ):
        if api_key is not None:
            os.environ["API_KEY"] = api_key
        if base_url is not None:
            os.environ["BASE_URL"] = base_url
        if model_name is not None:
            os.environ["MODEL_NAME"] = model_name
        os.environ["THRONGLETS_LLM"] = "True"
        return {"status": "config_updated"}
    
    @app.post("/api/simulation/initialize")
    async def initialize_simulation(agent_count: int = Query(12, ge=2, le=24)):
        global simulation
        if simulation:
            simulation.cleanup()
        
        simulation = SimulationManager(use_llm=True)
        simulation.initialize(agent_count=agent_count)
        
        def on_tick(sim, tick, stats):
            state = sim.get_state()
            ws_manager.broadcast_sync({
                "type": "state",
                "data": state,
            })
            
        simulation.add_tick_callback(on_tick)
        
        return {"status": "initialized", "agentCount": agent_count}
        
    @app.post("/api/simulation/start")
    async def start_simulation():
        if not simulation or not simulation._initialized:
            return JSONResponse({"error": "Simulation not initialized. Call /api/simulation/initialize first."}, status_code=400)
        simulation.start(tick_delay=1.0)
        return {"status": "started"}
        
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        await ws_manager.connect(websocket)
        
        try:
            if simulation:
                state = simulation.get_state()
                await websocket.send_json({"type": "state", "data": state})
                
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type")
                
                if msg_type == "subscribe":
                    channel = data.get("channel")
                    if channel:
                        await ws_manager.subscribe(websocket, channel)
                        
                elif msg_type == "unsubscribe":
                    channel = data.get("channel")
                    if channel:
                        await ws_manager.unsubscribe(websocket, channel)
                        
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    
        except WebSocketDisconnect:
            await ws_manager.disconnect(websocket)
        except Exception:
            await ws_manager.disconnect(websocket)
            
    return app
