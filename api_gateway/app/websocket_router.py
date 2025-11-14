# api_gateway/app/websocket_router.py
import logging
from fastapi import WebSocket
from typing import List

class ConnectionManager:
    """Manages active WebSocket connections."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logging.info(f"New WebSocket connection. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

async def broadcast_to_clients(manager: ConnectionManager, message: str):
    """Broadcasts a message to all connected WebSocket clients."""
    for connection in manager.active_connections:
        try:
            await connection.send_text(message)
        except Exception as e:
            logging.error(f"Failed to send message to a client: {e}")
            # The connection might be dead, but disconnect will handle cleanup.
