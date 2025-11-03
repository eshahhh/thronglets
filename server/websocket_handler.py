import json
import asyncio
from collections import defaultdict


class WebSocketManager:
    def __init__(self):
        self._connections = set()
        self._subscriptions = defaultdict(set)
        self._lock = asyncio.Lock()
        self._main_loop = None
        
    def set_event_loop(self, loop):
        self._main_loop = loop
        
    async def connect(self, websocket):
        async with self._lock:
            self._connections.add(websocket)
            
    async def disconnect(self, websocket):
        async with self._lock:
            self._connections.discard(websocket)
            for channel in self._subscriptions.values():
                channel.discard(websocket)
                
    async def subscribe(self, websocket, channel):
        async with self._lock:
            self._subscriptions[channel].add(websocket)
            
    async def unsubscribe(self, websocket, channel):
        async with self._lock:
            self._subscriptions[channel].discard(websocket)
            
    async def broadcast(self, message):
        if not self._connections:
            return
            
        data = json.dumps(message)
        dead = []
        
        for ws in list(self._connections):
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
                
        for ws in dead:
            await self.disconnect(ws)
            
    async def broadcast_channel(self, channel, message):
        subscribers = self._subscriptions.get(channel, set())
        if not subscribers:
            return
            
        data = json.dumps(message)
        dead = []
        
        for ws in list(subscribers):
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
                
        for ws in dead:
            await self.disconnect(ws)
            
    def broadcast_sync(self, message):
        if not self._connections:
            return
            
        if self._main_loop is None:
            return
            
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.broadcast(message), 
                self._main_loop
            )
        except Exception as e:
            print(f"Broadcast error: {e}")
            
    @property
    def connection_count(self):
        return len(self._connections)
