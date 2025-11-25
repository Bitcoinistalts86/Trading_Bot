# api_gateway/app/websocket_router.py
import logging
from fastapi import APIRouter, WebSocket, Depends
from typing import List

# Placeholder for token verification logic
def verify_token(token: str) -> bool:
    # In a real implementation, this would call the auth service
    # or decode a JWT token to verify its authenticity.
    return token is not None and token != ""

# Placeholder for a streaming service
class Streamer:
    async def forward(self, ws: WebSocket):
        # This would connect to a backend service (e.g., another Pub/Sub topic)
        # and forward messages to the WebSocket.
        # For now, we'll just keep the connection open.
        try:
            while True:
                await ws.receive_text()
        except Exception:
            pass # Connection closed

streamer = Streamer()

router = APIRouter()

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

@router.websocket("/ws/portfolio")
async def portfolio_ws(ws: WebSocket):
    token = ws.query_params.get("token")
    if not verify_token(token):
        await ws.close(code=1008)
        return

    await ws.accept()
    await streamer.forward(ws)