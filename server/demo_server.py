#!/usr/bin/env python3
import os
import sys
import time
import random
import math
import asyncio
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from websocket_handler import WebSocketManager


NAMES = [
    "Ada", "Basil", "Cora", "Dane", "Ella", "Finn", "Gwen", "Hugo",
    "Iris", "Joel", "Kira", "Liam", "Maya", "Noel", "Opal", "Paul",
    "Quinn", "Rosa", "Seth", "Tara", "Umar", "Vera", "Wade", "Xena",
]

AGENT_TYPES = [
    "farmer", "trader", "crafter", "gatherer", "leader", 
    "specialist", "cooperator", "opportunist"
]

LOCATIONS = [
    {"id": "forest", "name": "Forest", "type": "forest"},
    {"id": "river", "name": "River", "type": "river"},
    {"id": "mountain", "name": "Mountain", "type": "mountain"},
    {"id": "village", "name": "Village", "type": "settlement"},
    {"id": "meadow", "name": "Meadow", "type": "meadow"},
    {"id": "cave", "name": "Cave", "type": "cave"},
    {"id": "lake", "name": "Lake", "type": "lake"},
    {"id": "market", "name": "Market", "type": "market"},
]

ACTIONS = ["MOVE", "HARVEST", "IDLE", "TRADE_PROPOSAL", "SPEAK", "CRAFT", "CONSUME"]
RESOURCES = ["wood", "wheat", "fish", "stone", "berries", "herbs", "water"]

REASONING_TEMPLATES = [
    "I need to gather more resources before nightfall.",
    "Trading seems profitable right now.",
    "My hunger is getting low, better find food.",
    "This location has good resources.",
    "I should conserve energy and rest.",
    "Building relationships with neighbors is important.",
    "The market prices look favorable today.",
    "I've spotted some valuable resources nearby.",
]


class DemoSimulation:
    def __init__(self, agent_count=12):
        self._rng = random.Random(42)
        self._tick = 0
        self._running = False
        self._paused = False
        self._thread = None
        self._tick_delay = 0.8
        self._callbacks = []
        self._lock = threading.Lock()
        
        self._location_positions = {}
        self._compute_location_positions()
        
        self._agents = []
        self._spawn_agents(agent_count)
        
        self._events = []
        self._max_events = 500
        
        self._trade_volume = []
        self._gini_history = []

    def _compute_location_positions(self):
        n = len(LOCATIONS)
        center_x = 450
        center_y = 350
        radius = 280
        
        for i, loc in enumerate(LOCATIONS):
            angle = (2 * math.pi * i) / n - math.pi / 2
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            self._location_positions[loc["id"]] = {"x": x, "y": y}

    def _spawn_agents(self, count):
        type_weights = {
            "farmer": 3,
            "trader": 2,
            "crafter": 2,
            "gatherer": 2,
            "leader": 1,
            "specialist": 1,
            "cooperator": 2,
            "opportunist": 1,
        }
        
        weighted_types = []
        for t, w in type_weights.items():
            weighted_types.extend([t] * w)
        
        for i in range(min(count, len(NAMES))):
            name = NAMES[i]
            agent_type = self._rng.choice(weighted_types)
            location = self._rng.choice(LOCATIONS)["id"]
            
            pos = self._location_positions[location]
            jitter_x = (hash(name) % 80) - 40
            jitter_y = (hash(name + "y") % 80) - 40
            
            self._agents.append({
                "id": f"agent_{i}",
                "name": name,
                "displayName": f"{name} ({agent_type.title()})",
                "type": agent_type,
                "location": location,
                "x": pos["x"] + jitter_x,
                "y": pos["y"] + jitter_y,
                "inventory": self._random_inventory(),
                "needs": {
                    "food": 60 + self._rng.random() * 40,
                    "shelter": 70 + self._rng.random() * 30,
                    "reputation": 30 + self._rng.random() * 40,
                },
                "skills": {
                    "farming": self._rng.random() * 0.5,
                    "crafting": self._rng.random() * 0.5,
                    "negotiation": self._rng.random() * 0.5,
                },
                "capacity": 20,
                "lastAction": None,
                "reasoning": "",
            })

    def _random_inventory(self):
        inv = {}
        for _ in range(self._rng.randint(0, 4)):
            resource = self._rng.choice(RESOURCES)
            inv[resource] = inv.get(resource, 0) + self._rng.randint(1, 5)
        return inv

    def _simulate_tick(self):
        self._tick += 1
        
        for agent in self._agents:
            action_type = self._rng.choice(ACTIONS)
            success = self._rng.random() > 0.15
            
            details = {}
            message = ""
            
            if action_type == "MOVE":
                new_loc = self._rng.choice(LOCATIONS)["id"]
                if success:
                    agent["location"] = new_loc
                    pos = self._location_positions[new_loc]
                    jitter_x = (hash(agent["name"]) % 80) - 40
                    jitter_y = (hash(agent["name"] + "y") % 80) - 40
                    agent["x"] = pos["x"] + jitter_x
                    agent["y"] = pos["y"] + jitter_y
                details["destination"] = new_loc
                message = f"Moved to {new_loc}"
                
            elif action_type == "HARVEST":
                resource = self._rng.choice(RESOURCES)
                amount = self._rng.randint(1, 3)
                if success:
                    agent["inventory"][resource] = agent["inventory"].get(resource, 0) + amount
                details["resource_type"] = resource
                details["amount"] = amount
                message = f"Harvested {amount} {resource}"
                
            elif action_type == "TRADE_PROPOSAL":
                other = self._rng.choice([a for a in self._agents if a["id"] != agent["id"]])
                details["target"] = other["displayName"]
                message = f"Proposed trade with {other['displayName']}"
                
            elif action_type == "SPEAK":
                message = "Shared information with nearby agents"
                
            elif action_type == "CRAFT":
                message = "Crafted an item"
                
            elif action_type == "CONSUME":
                if agent["inventory"]:
                    item = self._rng.choice(list(agent["inventory"].keys()))
                    if agent["inventory"][item] > 0:
                        agent["inventory"][item] -= 1
                        if agent["inventory"][item] == 0:
                            del agent["inventory"][item]
                        agent["needs"]["food"] = min(100, agent["needs"]["food"] + 15)
                        message = f"Consumed {item}"
                    else:
                        message = "Nothing to consume"
                else:
                    message = "Empty inventory"
                    success = False
            else:
                message = "Resting"
                
            for need in agent["needs"]:
                decay = self._rng.random() * 3
                agent["needs"][need] = max(0, agent["needs"][need] - decay)
                
            agent["lastAction"] = {
                "tick": self._tick,
                "action_type": action_type,
                "details": details,
                "success": success,
                "message": message,
            }
            agent["reasoning"] = self._rng.choice(REASONING_TEMPLATES)
            
            event = {
                "tick": self._tick,
                "agent_id": agent["displayName"],
                "type": action_type,
                "details": details,
                "success": success,
                "message": message,
                "reasoning": agent["reasoning"],
                "timestamp": time.time(),
            }
            
            with self._lock:
                self._events.append(event)
                if len(self._events) > self._max_events:
                    self._events.pop(0)
                    
        self._trade_volume.append([self._tick, self._rng.randint(0, 10)])
        if len(self._trade_volume) > 100:
            self._trade_volume.pop(0)
            
        gini = 0.3 + 0.2 * math.sin(self._tick * 0.1) + self._rng.random() * 0.05
        self._gini_history.append([self._tick, gini])
        if len(self._gini_history) > 100:
            self._gini_history.pop(0)

    def start(self, tick_delay=0.8):
        if self._running:
            return
        self._tick_delay = tick_delay
        self._running = True
        self._paused = False
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        while self._running:
            if self._paused:
                time.sleep(0.1)
                continue
            self._simulate_tick()
            for callback in self._callbacks:
                try:
                    callback(self, self._tick, {})
                except Exception:
                    pass
            time.sleep(self._tick_delay)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    def step(self):
        self._simulate_tick()
        for callback in self._callbacks:
            try:
                callback(self, self._tick, {})
            except Exception:
                pass
        return type("Stats", (), {"tick": self._tick})()

    def add_tick_callback(self, callback):
        self._callbacks.append(callback)

    def get_state(self):
        locations = []
        for loc in LOCATIONS:
            pos = self._location_positions[loc["id"]]
            locations.append({
                "id": loc["id"],
                "name": loc["name"],
                "type": loc["type"],
                "x": pos["x"],
                "y": pos["y"],
                "resources": {self._rng.choice(RESOURCES): self._rng.randint(5, 20)},
            })
            
        return {
            "tick": self._tick,
            "running": self._running and not self._paused,
            "paused": self._paused,
            "agents": self._agents,
            "locations": locations,
        }

    def get_metrics(self):
        type_counts = {}
        total_wealth = 0
        
        for agent in self._agents:
            t = agent["type"]
            type_counts[t] = type_counts.get(t, 0) + 1
            total_wealth += sum(agent["inventory"].values())
            
        return {
            "tick": self._tick,
            "agentCount": len(self._agents),
            "agentTypes": type_counts,
            "wealth": {
                "total_wealth": total_wealth,
                "mean_wealth": total_wealth / len(self._agents) if self._agents else 0,
                "gini_coefficient": self._gini_history[-1][1] if self._gini_history else 0.3,
                "top_10_percent_share": 0.35,
            },
            "trade": {
                "num_nodes": len(self._agents),
                "num_edges": self._rng.randint(5, 20),
                "num_communities": 2,
                "avg_clustering": 0.4 + self._rng.random() * 0.2,
            },
            "specialization": {
                "avg_specialization": 0.5 + self._rng.random() * 0.3,
                "diversity_index": 0.6 + self._rng.random() * 0.2,
            },
            "groups": [],
            "tradeVolume": self._trade_volume[-50:],
            "giniHistory": self._gini_history[-50:],
        }

    def get_events(self, limit=100):
        with self._lock:
            return list(self._events[-limit:])

    def get_agent_detail(self, agent_id):
        for agent in self._agents:
            if agent["id"] == agent_id:
                return agent
        return None

    def cleanup(self):
        self.stop()


simulation = None
ws_manager = WebSocketManager()


@asynccontextmanager
async def lifespan(app):
    global simulation
    simulation = DemoSimulation(agent_count=12)
    
    def on_tick(sim, tick, stats):
        state = sim.get_state()
        ws_manager.broadcast_sync({"type": "state", "data": state})
        
    simulation.add_tick_callback(on_tick)
    yield
    if simulation:
        simulation.cleanup()


def create_app():
    app = FastAPI(title="Thronglets Demo Server", lifespan=lifespan)
    
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
            return JSONResponse({"error": "Not initialized"}, status_code=503)
        return {
            "tick": simulation._tick,
            "running": simulation._running and not simulation._paused,
            "paused": simulation._paused,
            "agentCount": len(simulation._agents),
            "connections": ws_manager.connection_count,
            "mode": "demo",
        }

    @app.get("/api/state")
    async def get_state():
        if not simulation:
            return JSONResponse({"error": "Not initialized"}, status_code=503)
        return simulation.get_state()

    @app.get("/api/metrics")
    async def get_metrics():
        if not simulation:
            return JSONResponse({"error": "Not initialized"}, status_code=503)
        return simulation.get_metrics()

    @app.get("/api/events")
    async def get_events(limit: int = Query(100, ge=1, le=500)):
        if not simulation:
            return JSONResponse({"error": "Not initialized"}, status_code=503)
        return simulation.get_events(limit)

    @app.get("/api/agents/{agent_id}")
    async def get_agent(agent_id: str):
        if not simulation:
            return JSONResponse({"error": "Not initialized"}, status_code=503)
        detail = simulation.get_agent_detail(agent_id)
        if not detail:
            return JSONResponse({"error": "Agent not found"}, status_code=404)
        return detail

    @app.get("/api/locations")
    async def get_locations():
        if not simulation:
            return JSONResponse({"error": "Not initialized"}, status_code=503)
        return simulation.get_state()["locations"]

    @app.post("/api/simulation/start")
    async def start_simulation(tick_delay: float = Query(0.8, ge=0.1, le=10.0)):
        if not simulation:
            return JSONResponse({"error": "Not initialized"}, status_code=503)
        simulation.start(tick_delay=tick_delay)
        return {"status": "started"}

    @app.post("/api/simulation/stop")
    async def stop_simulation():
        if not simulation:
            return JSONResponse({"error": "Not initialized"}, status_code=503)
        simulation.stop()
        return {"status": "stopped"}

    @app.post("/api/simulation/pause")
    async def pause_simulation():
        if not simulation:
            return JSONResponse({"error": "Not initialized"}, status_code=503)
        simulation.pause()
        return {"status": "paused"}

    @app.post("/api/simulation/resume")
    async def resume_simulation():
        if not simulation:
            return JSONResponse({"error": "Not initialized"}, status_code=503)
        simulation.resume()
        return {"status": "resumed"}

    @app.post("/api/simulation/step")
    async def step_simulation():
        if not simulation:
            return JSONResponse({"error": "Not initialized"}, status_code=503)
        stats = simulation.step()
        state = simulation.get_state()
        await ws_manager.broadcast({"type": "state", "data": state})
        return {"status": "stepped", "tick": stats.tick}

    @app.post("/api/simulation/reset")
    async def reset_simulation(agent_count: int = Query(12, ge=1, le=24)):
        global simulation
        if simulation:
            simulation.cleanup()
        simulation = DemoSimulation(agent_count=agent_count)
        
        def on_tick(sim, tick, stats):
            state = sim.get_state()
            ws_manager.broadcast_sync({"type": "state", "data": state})
            
        simulation.add_tick_callback(on_tick)
        return {"status": "reset", "agentCount": agent_count}

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
                
                if msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    
        except WebSocketDisconnect:
            await ws_manager.disconnect(websocket)
        except Exception:
            await ws_manager.disconnect(websocket)

    return app


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Thronglets Demo Server (Fake Data)")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    
    args = parser.parse_args()
    
    print(f"Starting Thronglets Demo Server on http://{args.host}:{args.port}")
    print("Mode: DEMO (fake data, no LLM)")
    print(f"Frontend: http://localhost:{args.port}")
    print()
    
    uvicorn.run(
        "demo_server:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,
    )


if __name__ == "__main__":
    main()
