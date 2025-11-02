from dataclasses import dataclass, field
import json
import asyncio
import threading
import time
import hashlib

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn


@dataclass
class DashboardState:
    current_tick: int = 0
    is_running: bool = False
    agent_count: int = 0
    total_trades: int = 0


@dataclass
class AgentVisualState:
    id: str
    x: float = 0.0
    y: float = 0.0
    color: str = "#6b7280"
    action: str = "idle"
    status: str = "active"
    location: str = ""
    thinking: str = ""
    speech: str = ""
    inventory: dict = field(default_factory=dict)
    needs: dict = field(default_factory=dict)
    skills: dict = field(default_factory=dict)
    reputation: float = 0.5
    memory: str = ""


@dataclass
class LocationVisualState:
    id: str
    name: str
    x: float
    y: float
    color: str = "#4a5568"


@dataclass
class EventRecord:
    agent_id: str
    tick: int
    event_type: str
    message: str
    timestamp: float = 0.0
    details: dict = field(default_factory=dict)


class DashboardServer:

    def __init__(
        self,
        trade_network=None,
        wealth_dashboard=None,
        specialization_map=None,
        governance_timeline=None,
        host="127.0.0.1",
        port=8080,
    ):
        self.host = host
        self.port = port
        self.trade_network = trade_network
        self.wealth_dashboard = wealth_dashboard
        self.specialization_map = specialization_map
        self.governance_timeline = governance_timeline

        self.app = FastAPI(title="Thronglets Dashboard")
        self.agents = {}
        self.locations = {}
        self.events = []
        self.websockets = []
        self.current_tick = 0
        self.running = False
        self.api_key = None
        self.total_trades = 0

        self.state = DashboardState()

        self.metrics_timeline = {
            "transactions": [],
            "messages": [],
            "trades": [],
        }
        self.current_tick_metrics = {
            "transactions": 0,
            "messages": 0,
            "trades": 0,
        }

        self._agent_colors = [
            "#7c9885", "#8b7e74", "#7a8b99", "#9c8a7b", "#6b8e8a",
            "#8a7d91", "#7e8f7a", "#94857e", "#6d899e", "#8f8a79",
        ]

        self._setup_routes()

    def _setup_routes(self):
        @self.app.get("/", response_class=HTMLResponse)
        async def get_dashboard():
            return self._get_dashboard_html()

        @self.app.get("/api/status")
        async def get_status():
            return {
                "tick": self.current_tick,
                "running": self.running,
                "agents": len(self.agents),
                "trades": self.total_trades,
                "metrics": {
                    "timeline": self.metrics_timeline,
                    "latest": self.current_tick_metrics.copy(),
                },
            }

        @self.app.get("/api/agents")
        async def get_agents():
            return {
                agent_id: {
                    "id": state.id,
                    "x": state.x,
                    "y": state.y,
                    "color": state.color,
                    "action": state.action,
                    "status": state.status,
                    "location": state.location,
                    "thinking": state.thinking,
                    "speech": state.speech,
                    "inventory": state.inventory,
                    "needs": state.needs,
                    "memory": state.memory,
                }
                for agent_id, state in self.agents.items()
            }

        @self.app.get("/api/locations")
        async def get_locations():
            return {
                loc_id: {
                    "id": state.id,
                    "name": state.name,
                    "x": state.x,
                    "y": state.y,
                    "color": state.color,
                }
                for loc_id, state in self.locations.items()
            }

        @self.app.get("/api/events")
        async def get_events():
            return [
                {
                    "agent_id": e.agent_id,
                    "tick": e.tick,
                    "type": e.event_type,
                    "message": e.message,
                    "timestamp": e.timestamp,
                    "details": e.details,
                }
                for e in self.events[-100:]
            ]

        @self.app.post("/api/config")
        async def set_config(config: dict):
            if "api_key" in config:
                self.api_key = config["api_key"]
            return {"status": "ok"}

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.websockets.append(websocket)
            try:
                while True:
                    data = await websocket.receive_text()
                    if data == "ping":
                        await websocket.send_text("pong")
            except WebSocketDisconnect:
                if websocket in self.websockets:
                    self.websockets.remove(websocket)

    def _compute_agent_position(self, agent_id, location):
        seed = int(hashlib.md5(agent_id.encode()).hexdigest()[:8], 16)
        base_x = 100 + (seed % 600)
        base_y = 100 + ((seed // 600) % 400)

        if location and location in self.locations:
            loc = self.locations[location]
            offset_x = ((seed % 60) - 30)
            offset_y = (((seed // 60) % 60) - 30)
            return loc.x + offset_x, loc.y + offset_y

        return float(base_x), float(base_y)

    def _get_agent_color(self, agent_id):
        seed = int(hashlib.md5(agent_id.encode()).hexdigest()[:8], 16)
        return self._agent_colors[seed % len(self._agent_colors)]

    async def _broadcast(self, message):
        dead = []
        for ws in self.websockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self.websockets:
                self.websockets.remove(ws)

    def broadcast_sync(self, message):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._broadcast(message))
            else:
                loop.run_until_complete(self._broadcast(message))
        except RuntimeError:
            pass

    def set_tick(self, tick):
        self.current_tick = tick
        self.state.current_tick = tick
        self.broadcast_sync({"type": "tick", "tick": tick, "running": self.running})

    def update_state(
        self,
        tick=None,
        is_running=None,
        agents=None,
        trades=None,
    ):
        if tick is not None:
            self.current_tick = tick
            self.state.current_tick = tick
        if is_running is not None:
            self.running = is_running
            self.state.is_running = is_running
        if agents is not None:
            self.state.agent_count = agents
        if trades is not None:
            self.total_trades = trades
            self.state.total_trades = trades

        self.broadcast_sync({
            "type": "tick",
            "tick": self.current_tick,
            "running": self.running,
        })

    def sync_agents(
        self,
        agents=None,
        agent_states=None,
        tick=None,
        stats=None,
    ):
        states_list = agents if agents is not None else (agent_states or [])

        if tick is not None:
            self.set_tick(tick)

        for state in states_list:
            agent_id = state.get("id", "")
            if not agent_id:
                continue

            location = state.get("location", "")
            x, y = self._compute_agent_position(agent_id, location)

            if agent_id not in self.agents:
                self.agents[agent_id] = AgentVisualState(
                    id=agent_id,
                    color=self._get_agent_color(agent_id),
                )

            agent = self.agents[agent_id]
            agent.x = x
            agent.y = y
            agent.location = location
            agent.action = state.get("action", "idle")
            agent.status = state.get("status", "active")
            agent.thinking = state.get("thinking", "")
            agent.speech = state.get("speech", "")
            agent.inventory = state.get("inventory", {})
            agent.needs = state.get("needs", {})
            agent.memory = state.get("memory", "")

            self.broadcast_sync({
                "type": "agent_update",
                "agent": {
                    "id": agent.id,
                    "x": agent.x,
                    "y": agent.y,
                    "color": agent.color,
                    "action": agent.action,
                    "location": agent.location,
                    "thinking": agent.thinking,
                    "speech": agent.speech,
                    "inventory": agent.inventory,
                    "needs": agent.needs,
                    "memory": agent.memory,
                },
            })

    def update_agent(
        self,
        agent_id,
        location=None,
        action=None,
        thinking=None,
        speech=None,
        inventory=None,
        needs=None,
        memory=None,
    ):
        if agent_id not in self.agents:
            x, y = self._compute_agent_position(agent_id, location or "")
            self.agents[agent_id] = AgentVisualState(
                id=agent_id,
                x=x,
                y=y,
                color=self._get_agent_color(agent_id),
            )

        agent = self.agents[agent_id]
        if location is not None:
            agent.location = location
            agent.x, agent.y = self._compute_agent_position(agent_id, location)
        if action is not None:
            agent.action = action
        if thinking is not None:
            agent.thinking = thinking
        if speech is not None:
            agent.speech = speech
        if inventory is not None:
            agent.inventory = inventory
        if needs is not None:
            agent.needs = needs
        if memory is not None:
            agent.memory = memory

        self.broadcast_sync({
            "type": "agent_update",
            "agent": {
                "id": agent.id,
                "x": agent.x,
                "y": agent.y,
                "color": agent.color,
                "action": agent.action,
                "thinking": agent.thinking,
                "speech": agent.speech,
                "inventory": agent.inventory,
                "needs": agent.needs,
                "memory": agent.memory,
            },
        })

    def add_location(self, loc_id, name, x, y, color="#4a5568"):
        self.locations[loc_id] = LocationVisualState(
            id=loc_id,
            name=name,
            x=x,
            y=y,
            color=color,
        )

    def log_event(
        self,
        agent_id=None,
        event_type=None,
        message=None,
        details=None,
        tick=None,
    ):
        event = EventRecord(
            agent_id=agent_id or "SYSTEM",
            tick=tick if tick is not None else self.current_tick,
            event_type=event_type or "info",
            message=message or "",
            timestamp=time.time(),
            details=details or {},
        )
        self.events.append(event)

        if event_type in ("trade", "trade_result", "harvest", "consume"):
            self.current_tick_metrics["transactions"] += 1
            if event_type in ("trade", "trade_result"):
                self.current_tick_metrics["trades"] += 1
                self.total_trades += 1
        elif event_type == "message":
            self.current_tick_metrics["messages"] += 1

        if len(self.events) > 500:
            self.events = self.events[-400:]

        self.broadcast_sync({
            "type": "event",
            "event": {
                "agent_id": event.agent_id,
                "tick": event.tick,
                "type": event.event_type,
                "message": event.message,
                "timestamp": event.timestamp,
                "details": event.details,
            },
        })

    def finalize_tick_metrics(self):
        for key in self.metrics_timeline:
            self.metrics_timeline[key].append(self.current_tick_metrics.get(key, 0))
            if len(self.metrics_timeline[key]) > 100:
                self.metrics_timeline[key] = self.metrics_timeline[key][-100:]

        self.broadcast_sync({
            "type": "metrics",
            "metrics": {
                "timeline": self.metrics_timeline,
                "latest": self.current_tick_metrics.copy(),
            },
        })

        self.current_tick_metrics = {k: 0 for k in self.current_tick_metrics}

    def start(self, blocking=True):
        self.running = True
        if blocking:
            uvicorn.run(self.app, host=self.host, port=self.port, log_level="warning")
        else:
            thread = threading.Thread(
                target=uvicorn.run,
                kwargs={"app": self.app, "host": self.host, "port": self.port, "log_level": "warning"},
                daemon=True,
            )
            thread.start()
            return thread

    def stop(self):
        self.running = False

    def _get_dashboard_html(self):
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thronglets - Research Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', 'Segoe UI', system-ui, sans-serif; background: #050607; color: #e5e7eb; overflow: hidden; }
        
        .container { display: grid; grid-template-columns: 1fr 420px; grid-template-rows: 56px 1fr; height: 100vh; }
        .header { grid-column: 1 / -1; background: #080a0f; border-bottom: 1px solid #151823; display: flex; align-items: center; justify-content: space-between; padding: 0 24px; }
        .header h1 { font-size: 1.05rem; font-weight: 600; color: #f8fafc; letter-spacing: -0.02em; }
        .status-bar { display: flex; gap: 32px; align-items: center; }
        .stat { text-align: center; min-width: 70px; }
        .stat-value { font-size: 1.35rem; font-weight: 600; color: #f4f7ff; font-variant-numeric: tabular-nums; }
        .stat-label { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 1px; color: #7c859f; }
        .status-indicator { width: 9px; height: 9px; border-radius: 50%; background: #4ade80; box-shadow: 0 0 10px rgba(74, 222, 128, 0.45); }
        .status-indicator.stopped { background: #f87171; box-shadow: none; }
        .config-btn { background: #0f131c; color: #cbd5f5; border: 1px solid #1f2534; padding: 8px 16px; border-radius: 6px; font-size: 0.78rem; cursor: pointer; transition: border-color 0.2s ease; }
        .config-btn:hover { border-color: #3a4256; }

        .world { background: radial-gradient(circle at top, #0f121a 0%, #050607 60%); position: relative; overflow: hidden; }
        .sidebar { background: #080a0f; border-left: 1px solid #151823; display: flex; flex-direction: column; overflow: hidden; }
        .sidebar-section { border-bottom: 1px solid #151823; padding: 18px 20px; }
        .sidebar-section h3 { font-size: 0.68rem; color: #7c859f; letter-spacing: 1.6px; text-transform: uppercase; margin-bottom: 12px; }

        .chart-container { background: #0c1018; border: 1px solid #1d2432; border-radius: 10px; padding: 12px; margin-bottom: 12px; position: relative; }
        .chart-title { font-size: 0.72rem; color: #8a94ad; margin-bottom: 6px; }
        .chart-value { position: absolute; top: 12px; right: 14px; font-size: 1.1rem; font-weight: 600; color: #f5f7ff; }
        .chart-canvas { width: 100%; height: 70px; }

        .agents-panel { max-height: 220px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; }
        .agent-card { background: #0b0f17; border: 1px solid #1d2432; border-radius: 10px; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
        .agent-card-header { display: flex; justify-content: space-between; align-items: baseline; }
        .agent-name { font-weight: 600; color: #f4f7ff; }
        .agent-location { font-size: 0.75rem; color: #94a3b8; }
        .agent-action-pill { font-size: 0.65rem; text-transform: uppercase; letter-spacing: 1px; color: #6ee7b7; }
        .agent-metrics { display: flex; flex-direction: column; gap: 6px; font-size: 0.75rem; color: #cbd5f5; }
        .needs-row { display: flex; gap: 6px; flex-wrap: wrap; }
        .need { flex: 1 1 45%; background: #0f1725; border: 1px solid #1a2130; border-radius: 6px; padding: 4px 6px; }
        .need-label { font-size: 0.65rem; color: #94a3b8; margin-bottom: 3px; text-transform: uppercase; }
        .need-bar { height: 4px; border-radius: 2px; background: #131b2c; position: relative; }
        .need-bar span { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 2px; background: #60a5fa; }
        .agent-memory { font-size: 0.7rem; color: #9da8c7; background: #0f131d; border-radius: 6px; padding: 6px 8px; border: 1px solid #151b29; white-space: pre-line; }

        .log-header { padding-bottom: 10px; }
        .event-log { flex: 1; overflow-y: auto; padding: 12px 16px; background: #07090e; }
        .event { padding: 14px 16px; margin-bottom: 12px; border-radius: 8px; border: 1px solid #1c212f; background: #0c0f16; }
        .event.message { border-color: #1f3c5c; }
        .event.trade { border-color: #3d2c18; }
        .event.trade_result { border-color: #4d3315; }
        .event.decision { border-color: #312341; }
        .event.llm_request { border-color: #1d3b4f; }
        .event.warning { border-color: #4a1f2c; }
        .event-header { display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 0.78rem; }
        .event-agent { color: #f4f7ff; font-weight: 600; }
        .event-tick { color: #7d859d; font-variant-numeric: tabular-nums; }
        .event-type { font-size: 0.65rem; letter-spacing: 1px; text-transform: uppercase; color: #8d95aa; margin-bottom: 6px; }
        .event-reason { font-size: 0.72rem; color: #c7d2fe; background: #181d2d; border-radius: 4px; padding: 6px 8px; margin-bottom: 6px; }
        .event-recipient { font-size: 0.72rem; color: #fcd7a2; margin-bottom: 6px; }
        .event-msg { font-size: 0.82rem; line-height: 1.5; color: #d5d9e5; }
        .empty-state { color: #5a6175; text-align: center; padding: 40px 12px; font-size: 0.78rem; }

        .agent { position: absolute; transition: left 0.45s ease, top 0.45s ease; }
        .agent-body { width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 0.75rem; color: #050607; border: 2px solid rgba(255,255,255,0.1); }
        .agent-label { position: absolute; bottom: -18px; left: 50%; transform: translateX(-50%); font-size: 0.6rem; color: #8d95aa; }
        .agent-action { position: absolute; top: -18px; left: 50%; transform: translateX(-50%); font-size: 0.58rem; color: #4ade80; letter-spacing: 0.5px; text-transform: uppercase; }
        .bubble { position: absolute; left: 50%; transform: translateX(-50%); background: #111728; border: 1px solid #1f273a; color: #cbd5f5; border-radius: 8px; padding: 8px 10px; font-size: 0.7rem; width: 180px; opacity: 0; transition: opacity 0.2s ease; pointer-events: none; }
        .bubble.thinking { bottom: 42px; }
        .bubble.speech { top: -64px; }
        .agent:hover .bubble, .bubble.active { opacity: 1; }

        .location { position: absolute; transform: translate(-50%, -50%); pointer-events: none; }
        .location-marker { width: 80px; height: 80px; border-radius: 50%; background: rgba(148, 163, 184, 0.08); }
        .location-name { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 0.68rem; color: #6c7289; text-transform: uppercase; letter-spacing: 1px; }

        .modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.85); z-index: 1000; align-items: center; justify-content: center; }
        .modal.active { display: flex; }
        .modal-content { background: #0c0f16; border: 1px solid #1c212f; border-radius: 12px; width: 380px; padding: 26px; }
        .modal h2 { color: #f8fafc; margin-bottom: 18px; font-size: 1rem; }
        .modal label { font-size: 0.7rem; color: #a5adc5; margin-bottom: 6px; letter-spacing: 0.5px; }
        .modal input { width: 100%; padding: 10px 12px; background: #05070b; border: 1px solid #1f2534; border-radius: 6px; color: #f4f7ff; margin-bottom: 16px; font-family: 'JetBrains Mono', monospace; }
        .modal-btns { display: flex; justify-content: flex-end; gap: 10px; }
        .btn-secondary, .btn-primary { padding: 8px 18px; border-radius: 6px; font-size: 0.78rem; cursor: pointer; }
        .btn-secondary { background: #0b0f17; color: #cbd5f5; border: 1px solid #1f2534; }
        .btn-primary { background: #2563eb; border: none; color: white; }

        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-thumb { background: #1c2130; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>Thronglets - Field Operations Monitor</h1>
            <div class="status-bar">
                <div class="status-indicator" id="status-indicator"></div>
                <div class="stat"><div class="stat-value" id="tick-val">0</div><div class="stat-label">Tick</div></div>
                <div class="stat"><div class="stat-value" id="agents-val">-</div><div class="stat-label">Agents</div></div>
                <div class="stat"><div class="stat-value" id="trades-val">0</div><div class="stat-label">Trades</div></div>
            </div>
            <button class="config-btn" onclick="openConfig()">Configure API</button>
        </header>

        <main class="world" id="world"></main>

        <aside class="sidebar">
            <div class="sidebar-section">
                <h3>Real-Time Metrics</h3>
                <div class="chart-container">
                    <div class="chart-title">Per-Tick Transactions</div>
                    <div class="chart-value" id="actions-val">0</div>
                    <canvas class="chart-canvas" id="actions-chart"></canvas>
                </div>
                <div class="chart-container">
                    <div class="chart-title">Agent Communications</div>
                    <div class="chart-value" id="messages-val">0</div>
                    <canvas class="chart-canvas" id="messages-chart"></canvas>
                </div>
            </div>
            <div class="sidebar-section">
                <div class="agent-card-header" style="margin-bottom: 6px;">
                    <h3 style="margin-bottom:0;">Agents</h3>
                    <span class="agent-location" id="agent-panel-count">0 online</span>
                </div>
                <div class="agents-panel" id="agents-panel">
                    <div class="empty-state">Waiting for first snapshot...</div>
                </div>
            </div>
            <div class="sidebar-section log-header">
                <h3>Agent Activity Log</h3>
            </div>
            <div class="event-log" id="event-log">
                <div class="empty-state">Awaiting agent activity...</div>
            </div>
        </aside>
    </div>

    <div class="modal" id="config-modal">
        <div class="modal-content">
            <h2>API Configuration</h2>
            <label>OpenAI API Key</label>
            <input type="password" id="api-key" placeholder="sk-..." autocomplete="off" />
            <div class="modal-btns">
                <button class="btn-secondary" onclick="closeConfig()">Cancel</button>
                <button class="btn-primary" onclick="saveConfig()">Save</button>
            </div>
        </div>
    </div>

    <script>
        const world = document.getElementById('world');
        const eventLog = document.getElementById('event-log');
        const agentPanel = document.getElementById('agents-panel');
        let agents = {};
        let locations = {};
        let ws = null;
        let reconnectTimeout = null;
        let hasEvents = false;
        const metricsSeries = {
            transactions: new Array(48).fill(0),
            messages: new Array(48).fill(0),
        };
        const chartColors = {
            transactions: { line: '#9ccfd8', fill: 'rgba(156, 207, 216, 0.16)' },
            messages: { line: '#f6c177', fill: 'rgba(246, 193, 119, 0.14)' },
        };
        const pendingEvents = [];
        let flushHandle = null;

        const actionsChart = document.getElementById('actions-chart');
        const messagesChart = document.getElementById('messages-chart');
        const actionsCtx = actionsChart.getContext('2d');
        const messagesCtx = messagesChart.getContext('2d');

        function drawChart(ctx, data, colors) {
            const w = ctx.canvas.width;
            const h = ctx.canvas.height;
            ctx.clearRect(0, 0, w, h);
            if (!data.length) return;
            const max = Math.max(...data, 1);
            const step = w / Math.max(data.length - 1, 1);

            ctx.strokeStyle = 'rgba(255,255,255,0.04)';
            ctx.lineWidth = 1;
            for (let i = 0; i <= 4; i++) {
                const y = (h / 4) * i;
                ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
            }

            ctx.beginPath();
            ctx.moveTo(0, h);
            data.forEach((val, idx) => {
                const x = idx * step;
                const y = h - (val / max) * (h * 0.8) - 4;
                ctx.lineTo(x, y);
            });
            ctx.lineTo(w, h);
            ctx.closePath();
            ctx.fillStyle = colors.fill;
            ctx.fill();

            ctx.beginPath();
            ctx.strokeStyle = colors.line;
            ctx.lineWidth = 2;
            data.forEach((val, idx) => {
                const x = idx * step;
                const y = h - (val / max) * (h * 0.8) - 4;
                if (idx === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            });
            ctx.stroke();
        }

        function resizeCharts() {
            [actionsChart, messagesChart].forEach(canvas => {
                const { offsetWidth, offsetHeight } = canvas;
                canvas.width = offsetWidth * 2;
                canvas.height = offsetHeight * 2;
                canvas.getContext('2d').scale(2, 2);
            });
            drawChart(actionsCtx, metricsSeries.transactions, chartColors.transactions);
            drawChart(messagesCtx, metricsSeries.messages, chartColors.messages);
        }
        resizeCharts();
        window.addEventListener('resize', () => requestAnimationFrame(resizeCharts));

        function connectWebSocket() {
            if (ws && ws.readyState === WebSocket.OPEN) return;
            ws = new WebSocket(`ws://${location.host}/ws`);
            ws.onopen = () => {
                document.getElementById('status-indicator').classList.remove('stopped');
            };
            ws.onmessage = (evt) => {
                if (evt.data === 'pong') return;
                try {
                    handleMessage(JSON.parse(evt.data));
                } catch (_) {}
            };
            ws.onclose = () => {
                document.getElementById('status-indicator').classList.add('stopped');
                reconnectTimeout = setTimeout(connectWebSocket, 2000);
            };
            ws.onerror = () => {};
        }

        function handleMessage(msg) {
            switch (msg.type) {
                case 'tick':
                    document.getElementById('tick-val').textContent = msg.tick;
                    if (!msg.running) document.getElementById('status-indicator').classList.add('stopped');
                    break;
                case 'agent_update':
                    updateAgentVisual(msg.agent);
                    break;
                case 'event':
                    enqueueEvent(msg.event);
                    break;
                case 'metrics':
                    updateMetricsFromStatus(msg.metrics || {});
                    break;
            }
        }

        function enqueueEvent(event) {
            pendingEvents.push(event);
            pendingEvents.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
            if (!flushHandle) {
                flushHandle = setInterval(flushEventQueue, 250);
            }
        }

        function flushEventQueue() {
            if (!pendingEvents.length) {
                clearInterval(flushHandle);
                flushHandle = null;
                return;
            }
            const evt = pendingEvents.shift();
            renderEvent(evt);
        }

        function updateAgentVisual(data) {
            if (!data || typeof data.x !== 'number') return;
            let agentEl = agents[data.id];
            if (!agentEl) {
                agentEl = document.createElement('div');
                agentEl.className = 'agent';
                agentEl.innerHTML = `
                    <div class="bubble thinking"></div>
                    <div class="agent-action"></div>
                    <div class="agent-body" style="background:${data.color || '#6b7280'}">${data.id}</div>
                    <div class="agent-label">${data.id}</div>
                    <div class="bubble speech"></div>
                `;
                world.appendChild(agentEl);
                agents[data.id] = agentEl;
            }
            agentEl.style.left = data.x + 'px';
            agentEl.style.top = data.y + 'px';
            const actionEl = agentEl.querySelector('.agent-action');
            actionEl.textContent = data.action && data.action !== 'idle' ? data.action : '';
            actionEl.style.opacity = data.action && data.action !== 'idle' ? '1' : '0';

            const thinkBubble = agentEl.querySelector('.bubble.thinking');
            const speechBubble = agentEl.querySelector('.bubble.speech');
            if (data.thinking) {
                thinkBubble.textContent = data.thinking;
                thinkBubble.classList.add('active');
                setTimeout(() => thinkBubble.classList.remove('active'), 3500);
            }
            if (data.speech) {
                speechBubble.textContent = data.speech;
                speechBubble.classList.add('active');
                setTimeout(() => speechBubble.classList.remove('active'), 3500);
            }
        }

        function renderEvent(event) {
            if (!hasEvents) {
                eventLog.innerHTML = '';
                hasEvents = true;
            }
            const div = document.createElement('div');
            div.className = `event ${event.type}`;
            const details = event.details || {};
            const message = event.message || details.content || '';
            const reason = details.reason ? `<div class="event-reason">Reason: ${details.reason}</div>` : '';
            const typeLabel = event.type.replace('_', ' ').toUpperCase();
            const tick = Number.isFinite(event.tick) ? event.tick : '?';
            const agentId = event.agent_id || 'UNKNOWN';
            let extra = '';
            if (event.type === 'message') {
                extra = `<div class="event-recipient">To: ${details.recipient || 'broadcast'}</div>`;
            } else if (event.type === 'trade_result') {
                const status = details.accepted ? 'ACCEPTED' : 'REJECTED';
                extra = `<div class="event-recipient">Outcome: ${status}</div>`;
            } else if (event.type === 'decision') {
                const action = details.action ? ` - ${details.action.toUpperCase()}` : '';
                extra = `<div class="event-recipient">Decision${action}</div>`;
            } else if (event.type === 'llm_request') {
                extra = `<div class="event-recipient">Model: ${details.model || 'LLM'}</div>`;
            }

            div.innerHTML = `
                <div class="event-header">
                    <span class="event-agent">${agentId}</span>
                    <span class="event-tick">T${tick}</span>
                </div>
                <div class="event-type">${typeLabel}</div>
                ${reason}
                ${extra}
                <div class="event-msg">${message}</div>
            `;
            eventLog.insertBefore(div, eventLog.firstChild);
            while (eventLog.children.length > 80) {
                eventLog.removeChild(eventLog.lastChild);
            }
        }

        async function fetchLocations() {
            try {
                const res = await fetch('/api/locations');
                locations = await res.json();
                renderLocations();
            } catch (_) {}
        }

        function renderLocations() {
            Object.values(locations).forEach(loc => {
                const div = document.createElement('div');
                div.className = 'location';
                div.style.left = loc.x + 'px';
                div.style.top = loc.y + 'px';
                div.innerHTML = `
                    <div class="location-marker"></div>
                    <div class="location-name">${loc.name}</div>
                `;
                world.appendChild(div);
            });
        }

        function updateMetricsFromStatus(metrics) {
            const timeline = metrics.timeline || {};
            const transactions = Array.isArray(timeline.transactions) ? timeline.transactions : [];
            const messages = Array.isArray(timeline.messages) ? timeline.messages : [];
            metricsSeries.transactions = [...transactions].slice(-48);
            metricsSeries.messages = [...messages].slice(-48);
            document.getElementById('actions-val').textContent = metrics.latest?.transactions ?? 0;
            document.getElementById('messages-val').textContent = metrics.latest?.messages ?? 0;
            drawChart(actionsCtx, metricsSeries.transactions, chartColors.transactions);
            drawChart(messagesCtx, metricsSeries.messages, chartColors.messages);
        }

        async function fetchStats() {
            try {
                const status = await fetch('/api/status').then(r => r.json());
                document.getElementById('tick-val').textContent = status.tick;
                document.getElementById('agents-val').textContent = status.agents ?? '-';
                document.getElementById('trades-val').textContent = status.trades ?? 0;
                if (!status.running) document.getElementById('status-indicator').classList.add('stopped');
                if (status.metrics) updateMetricsFromStatus(status.metrics);
            } catch (_) {}
        }

        function formatInventory(inv) {
            const entries = Object.entries(inv || {});
            if (!entries.length) return 'Inventory empty';
            return entries.sort((a, b) => b[1] - a[1]).slice(0, 3)
                .map(([item, qty]) => `${qty}x ${item}`).join(', ');
        }

        function renderNeeds(needs) {
            const entries = Object.entries(needs || {}).slice(0, 4);
            if (!entries.length) return '<span style="color:#556070;">No needs tracked</span>';
            return entries.map(([need, value]) => {
                const pct = Math.min(100, Math.max(0, Number(value) || 0));
                return `
                <div class="need">
                    <div class="need-label">${need}</div>
                    <div class="need-bar"><span style="width:${pct}%"></span></div>
                </div>
            `;
            }).join('');
        }

        function renderAgentCards(agentMap) {
            const values = Object.values(agentMap || {});
            if (!values.length) {
                agentPanel.innerHTML = '<div class="empty-state">Waiting for first snapshot...</div>';
                document.getElementById('agent-panel-count').textContent = '0 online';
                return;
            }
            document.getElementById('agent-panel-count').textContent = `${values.length} online`;
            agentPanel.innerHTML = '';
            values.sort((a, b) => (a.id || '').localeCompare(b.id || '')).forEach(agent => {
                const card = document.createElement('div');
                card.className = 'agent-card';
                const locationName = (agent.location && locations[agent.location]?.name) || agent.location || 'Unknown';
                const memory = agent.memory ? agent.memory.split('\\n').slice(0, 4).join('\\n') : 'No recent memories.';
                const agentId = agent.id || 'UNKNOWN';
                card.innerHTML = `
                    <div class="agent-card-header">
                        <div>
                            <div class="agent-name">${agentId}</div>
                            <div class="agent-location">${locationName}</div>
                        </div>
                        <div class="agent-action-pill">${agent.action || agent.status || 'IDLE'}</div>
                    </div>
                    <div class="agent-metrics">
                        <div>Inventory - ${formatInventory(agent.inventory)}</div>
                        <div>Reasoning - ${agent.thinking || 'None'}</div>
                        <div class="needs-row">${renderNeeds(agent.needs)}</div>
                    </div>
                    <div class="agent-memory">${memory}</div>
                `;
                agentPanel.appendChild(card);
            });
        }

        async function fetchAgents() {
            try {
                const res = await fetch('/api/agents');
                const data = await res.json();
                Object.values(data).forEach(agent => updateAgentVisual(agent));
                renderAgentCards(data);
            } catch (_) {}
        }

        function openConfig() { document.getElementById('config-modal').classList.add('active'); }
        function closeConfig() { document.getElementById('config-modal').classList.remove('active'); }
        async function saveConfig() {
            const apiKey = document.getElementById('api-key').value;
            if (!apiKey) return;
            try {
                await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ api_key: apiKey })
                });
                closeConfig();
            } catch (_) {}
        }

        fetchLocations();
        fetchStats();
        fetchAgents();
        connectWebSocket();
        setInterval(fetchStats, 1200);
        setInterval(fetchAgents, 900);
        setInterval(() => { if (ws?.readyState === WebSocket.OPEN) ws.send('ping'); }, 5000);
    </script>
</body>
</html>'''


def create_dashboard(
    trade_network=None,
    wealth_dashboard=None,
    specialization_map=None,
    governance_timeline=None,
    host="127.0.0.1",
    port=8080,
):
    return DashboardServer(
        trade_network=trade_network,
        wealth_dashboard=wealth_dashboard,
        specialization_map=specialization_map,
        governance_timeline=governance_timeline,
        host=host,
        port=port,
    )
