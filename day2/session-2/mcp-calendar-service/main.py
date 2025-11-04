from datetime import datetime, timedelta
import json
from pathlib import Path

import fastmcp
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from agent import Agent

# Initialize agent with DID Peer
agent = Agent(name="Calendar Service", host="localhost", a2a_port=10000, mcp_port=8000)

app = fastmcp.FastMCP(name="Calendar Service",stateless_http=True)

http_middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

@app.custom_route("/", methods=["GET"])
async def read_root(_: Request) -> JSONResponse:
    return JSONResponse({
        "message": "Hello from FastMCP!",
        "did": agent.get_did(),
        "services": agent.get_service_endpoints()
    })

@app.custom_route("/", methods=["POST"])
async def read_root(_: Request) -> JSONResponse:
    return JSONResponse({"message": "OK!"})

@app.custom_route("/did", methods=["GET"])
async def get_did(_: Request) -> JSONResponse:
    """Get the agent's DID Peer identifier."""
    return JSONResponse({"did": agent.get_did()})

@app.custom_route("/services", methods=["GET"])
async def get_services(_: Request) -> JSONResponse:
    """Get the agent's service endpoints."""
    return JSONResponse(agent.get_service_endpoints())

@app.tool("request_meeting")
def request_meeting(requester: str, start: datetime, duration: int, message: str) -> str:
    """Request a meeting with the given parameters."""

    calendar_path = Path(__file__).with_name("calendar.json")

    try:
        with calendar_path.open("r", encoding="utf-8") as calendar_file:
            calendar_data = json.load(calendar_file)
    except (FileNotFoundError, json.JSONDecodeError):
        return "ERROR"

    events = calendar_data.get("events", [])

    new_start = start
    new_end = new_start + timedelta(minutes=duration)

    for event in events:
        try:
            existing_start = datetime.fromisoformat(event["start"])
        except (KeyError, TypeError, ValueError):
            return "ERROR"

        existing_end = existing_start + timedelta(minutes=int(event.get("duration", 0)))

        if not (new_end <= existing_start or new_start >= existing_end):
            return "CONFLICT"

    new_event = {
        "requester": requester,
        "start": new_start.isoformat(),
        "duration": duration,
        "message": message,
    }

    events.append(new_event)
    calendar_data["events"] = events

    try:
        with calendar_path.open("w", encoding="utf-8") as calendar_file:
            json.dump(calendar_data, calendar_file, indent=4)
    except OSError:
        return "ERROR"

    return "SUCCESS"


if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"🚀 Starting MCP Calendar Service")
    print(f"📋 Agent DID: {agent.get_did()}")
    print(f"🔗 Service Endpoints:")
    for service_name, endpoint in agent.get_service_endpoints().items():
        print(f"   {service_name}: {endpoint}")
    print(f"{'='*60}\n")
    app.run(transport="streamable-http", middleware=http_middleware,path="/mcp/calendar")
