import asyncio
import json
import websockets

clients = set()


async def ui_handler(websocket):
    clients.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        clients.remove(websocket)


async def start_ui_server():
    server = await websockets.serve(ui_handler, "localhost", 8765)
    print("UI WebSocket running on ws://localhost:8765")
    return server


async def set_ui_status(status: str, message: str = ""):
    if not clients:
        return

    data = json.dumps({
        "status": status,
        "message": message,
    })

    await asyncio.gather(
        *[client.send(data) for client in clients],
        return_exceptions=True,
    )