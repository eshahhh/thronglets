import json
import asyncio
from collections import defaultdict


class WebSocketManager:
    def __init__(self):
        self._connections = set()
        self._subscriptions = defaultdict(set)
        self._lock = asyncio.Lock()
        
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
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.broadcast(message))
            else:
                loop.run_until_complete(self.broadcast(message))
        except RuntimeError:
            pass
            
    @property
    def connection_count(self):
        return len(self._connections)
