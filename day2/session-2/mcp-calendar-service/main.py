from datetime import datetime, timedelta
import json
from pathlib import Path

import fastmcp
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, FileResponse

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
    return JSONResponse({"message": "Hello from FastMCP!"})

@app.custom_route("/", methods=["POST"])
async def read_root(_: Request) -> JSONResponse:
    return JSONResponse({"message": "OK!"})

@app.custom_route("/.well-known/agentfacts.json", methods=["GET"])
async def get_agentfacts(_: Request) -> JSONResponse:
    """Serve AgentFacts from the calendar-agent directory."""
    try:
        # Agent facts are stored in the calendar-agent directory
        agentfacts_path = Path(__file__).parent.parent / "calendar-agent" / "agentfacts.json"
        
        if agentfacts_path.exists():
            with agentfacts_path.open('r', encoding='utf-8') as f:
                facts = json.load(f)
            return JSONResponse(facts)
        else:
            return JSONResponse({"error": "AgentFacts not found"}, status_code=404)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

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
    app.run(transport="streamable-http", middleware=http_middleware,path="/mcp/calendar")
