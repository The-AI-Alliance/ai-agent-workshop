"""MCP Server for Calendar Agent using FastMCP."""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from fastmcp import FastMCP
import sys
import json
from pathlib import Path
from starlette.requests import Request
from starlette.responses import JSONResponse
# Add current directory to path to import local modules
sys.path.insert(0, str(Path(__file__).parent))

# Import Agent class
from agent import Agent

# Initialize agent with DID Peer - A2A now on same port as MCP
agent = Agent(name="Calendar Agent", host="localhost", a2a_port=8000, mcp_port=8000)

# Import local modules
import importlib.util
spec = importlib.util.spec_from_file_location("calendar_module", Path(__file__).parent / "calendar_module.py")
calendar_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calendar_module)

spec_db = importlib.util.spec_from_file_location("db_adapter", Path(__file__).parent / "db_adapter.py")
db_adapter_module = importlib.util.module_from_spec(spec_db)
spec_db.loader.exec_module(db_adapter_module)

# Import classes
Calendar = calendar_module.Calendar
Event = calendar_module.Event
EventStatus = calendar_module.EventStatus
BookingPreferences = calendar_module.BookingPreferences
CalendarDBAdapter = db_adapter_module.CalendarDBAdapter

# Initialize MCP server with HTTP support for custom routes
# Note: stateless_http=True enables HTTP endpoints, but SSE still needs proper transport
mcp = FastMCP("Calendar Agent MCP Server", stateless_http=True)

# Add AgentFacts endpoint
@mcp.custom_route("/.well-known/agentfacts.json", methods=["GET"])
async def get_agentfacts(_: Request) -> JSONResponse:
    """Serve AgentFacts from the local file."""
    try:
        agentfacts_path = Path(__file__).parent / "agentfacts.json"
        
        if agentfacts_path.exists():
            with agentfacts_path.open('r', encoding='utf-8') as f:
                facts = json.load(f)
            return JSONResponse(facts)
        else:
            return JSONResponse({"error": "AgentFacts not found"}, status_code=404)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# Add A2A agent card endpoint (merged from A2A server)
@mcp.custom_route("/.well-known/agent-card.json", methods=["GET"])
async def get_agent_card(_: Request) -> JSONResponse:
    """Serve A2A agent card."""
    try:
        # Import a2a_server module
        from a2a_server import create_agent_card
        agent_card = create_agent_card(host="localhost", port=8000)
        return JSONResponse(agent_card)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)

# Add A2A health check endpoint
@mcp.custom_route("/health", methods=["GET"])
async def health_check(_: Request) -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "service": "Calendar Agent MCP/A2A Server",
        "endpoints": {
            "mcp": "http://localhost:8000/mcp",
            "a2a": "http://localhost:8000/a2a",
            "agent_card": "http://localhost:8000/.well-known/agent-card.json",
            "agentfacts": "http://localhost:8000/.well-known/agentfacts.json"
        }
    })

# All A2A routes are now under /a2a prefix (already set in the routes above)

# Add A2A request handling endpoint (for tool calls)
@mcp.custom_route("/a2a/request", methods=["POST"])
async def handle_a2a_request(request: Request) -> JSONResponse:
    """Handle A2A protocol requests."""
    try:
        # Import a2a_server module
        from a2a_server import handle_request_available_slots, handle_request_booking, handle_delete_booking
        
        # Parse request body
        body = await request.json()
        
        # Handle the request based on A2A protocol
        if "method" in body:
            method = body.get("method")
            params = body.get("params", {})
            
            if method == "tools/call":
                tool_name = params.get("tool_name")
                tool_input = params.get("input", {})
                
                # Call the appropriate tool handler
                if tool_name == "requestAvailableSlots":
                    result = handle_request_available_slots(tool_input)
                elif tool_name == "requestBooking":
                    result = handle_request_booking(tool_input)
                elif tool_name == "deleteBooking":
                    result = handle_delete_booking(tool_input)
                else:
                    result = {"error": f"Unknown tool: {tool_name}"}
                
                return JSONResponse({"result": result})
            else:
                return JSONResponse({"error": f"Unknown method: {method}"}, status_code=400)
        else:
            return JSONResponse({"error": "Missing 'method' in request"}, status_code=400)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": str(e)}, status_code=500)

# Initialize database adapter
DB_PATH = "calendar_agent.db"
db_adapter = CalendarDBAdapter(db_path=DB_PATH)

# Global calendar instance (in production, you'd want per-user/agent instances)
_calendar: Optional[Calendar] = None
_preferences: Optional[BookingPreferences] = None


def get_calendar(reload: bool = True) -> Calendar:
    """Get or initialize the calendar instance.
    
    Args:
        reload: If True, reload events from database (ensures sync with Streamlit app)
    """
    global _calendar
    if _calendar is None or reload:
        _calendar = Calendar(owner_agent_id="mcp-agent")
        # Load existing events from database (always reload to stay in sync)
        saved_events = db_adapter.load_all_events(Event, EventStatus)
        for event in saved_events:
            # Ensure status is properly set (convert string to enum if needed)
            if isinstance(event.status, str) and hasattr(EventStatus, event.status.upper()):
                try:
                    event.status = EventStatus[event.status.upper()]
                except:
                    pass
            _calendar.events[event.event_id] = event
    return _calendar


def get_preferences() -> BookingPreferences:
    """Get or initialize the preferences instance."""
    global _preferences
    if _preferences is None:
        _preferences = db_adapter.load_preferences(BookingPreferences)
        if _preferences is None:
            _preferences = BookingPreferences()  # Use defaults
    return _preferences


def _parse_duration(duration_str: str) -> int:
    """Parse duration string (e.g., '30m', '1h') to minutes."""
    duration_str = duration_str.lower().strip()
    if duration_str.endswith('m'):
        return int(duration_str[:-1])
    elif duration_str.endswith('h'):
        return int(duration_str[:-1]) * 60
    else:
        return int(duration_str)


def _is_time_slot_available(calendar: Calendar, start_time: datetime, duration_minutes: int, 
                            preferences: BookingPreferences) -> bool:
    """Check if a time slot is available (no conflicts and matches preferences)."""
    # Create a temporary event to check for conflicts
    temp_event = Event(
        time=start_time,
        duration=f"{duration_minutes}m",
        partner_agent_id="temp_check",
        status=EventStatus.PROPOSED
    )
    
    # Check for conflicts
    if calendar.has_conflict(temp_event):
        return False
    
    # Check preferences
    if not preferences.is_preferred_time(start_time):
        return False
    
    # Check buffer time
    if not preferences.allow_back_to_back:
        end_time = start_time + timedelta(minutes=duration_minutes)
        for existing_event in calendar.get_confirmed_events():
            existing_end = existing_event.get_end_time()
            time_diff = abs((start_time - existing_end).total_seconds() / 60)
            if time_diff < preferences.buffer_between_meetings:
                return False
            # Also check if new event starts too close to existing event
            time_diff_start = abs((existing_event.time - end_time).total_seconds() / 60)
            if time_diff_start < preferences.buffer_between_meetings:
                return False
    
    # Check max meetings per day
    same_day_events = [e for e in calendar.get_all_events() 
                       if e.time.date() == start_time.date()]
    if len(same_day_events) >= preferences.max_meetings_per_day:
        return False
    
    return True


@mcp.tool
def requestAvailableSlots(
    start_date: str,
    end_date: str,
    duration: str = "30m",
    partner_agent_id: Optional[str] = None,
    timezone: str = "UTC",
    slot_granularity_minutes: int = 30
) -> Dict[str, Any]:
    """Request available time slots for booking a meeting.
    
    Args:
        start_date: Start date/time in ISO format (e.g., "2025-01-15T09:00:00Z")
        end_date: End date/time in ISO format (e.g., "2025-01-20T17:00:00Z")
        duration: Meeting duration (e.g., "30m", "1h", "45m")
        partner_agent_id: Optional partner agent ID for the meeting
        timezone: Timezone string (default: "UTC")
        slot_granularity_minutes: Granularity of time slots in minutes (default: 30)
    
    Returns:
        Dictionary with available slots list and metadata
    """
    try:
        calendar = get_calendar()
        preferences = get_preferences()
        
        # Parse input dates
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        duration_minutes = _parse_duration(duration)
        
        # Generate available slots
        available_slots = []
        current_time = start_dt
        
        while current_time + timedelta(minutes=duration_minutes) <= end_dt:
            # Check if this slot is available
            if _is_time_slot_available(calendar, current_time, duration_minutes, preferences):
                slot_end = current_time + timedelta(minutes=duration_minutes)
                available_slots.append({
                    "start": current_time.isoformat(),
                    "end": slot_end.isoformat(),
                    "duration_minutes": duration_minutes
                })
            
            # Move to next slot
            current_time += timedelta(minutes=slot_granularity_minutes)
        
        return {
            "available_slots": available_slots,
            "total_slots": len(available_slots),
            "duration_requested": duration,
            "start_date": start_date,
            "end_date": end_date,
            "partner_agent_id": partner_agent_id
        }
    
    except Exception as e:
        return {
            "error": str(e),
            "available_slots": [],
            "total_slots": 0
        }


@mcp.tool
def requestBooking(
    start_time: str,
    duration: str,
    partner_agent_id: str,
    initial_status: str = "proposed"
) -> Dict[str, Any]:
    """Request a booking for a meeting.
    
    Args:
        start_time: Start time in ISO format (e.g., "2025-01-15T10:00:00Z")
        duration: Meeting duration (e.g., "30m", "1h", "45m")
        partner_agent_id: Partner agent ID for the meeting
        initial_status: Initial status of the event (default: "proposed")
    
    Returns:
        Dictionary with booking details and status
    """
    try:
        calendar = get_calendar()
        preferences = get_preferences()
        
        # Parse start time
        event_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        duration_minutes = _parse_duration(duration)
        
        # Check if partner is blocked
        if partner_agent_id in preferences.blocked_partners:
            return {
                "success": False,
                "error": f"Partner {partner_agent_id} is in the blocked list",
                "event_id": None
            }
        
        # Create event based on initial status
        if initial_status.lower() == "proposed":
            event = calendar.propose_event(
                time=event_time,
                duration=duration,
                partner_agent_id=partner_agent_id
            )
        else:
            # Try to parse status
            try:
                status_enum = EventStatus[initial_status.upper()]
            except KeyError:
                status_enum = EventStatus.PROPOSED
            
            event = Event(
                time=event_time,
                duration=duration,
                partner_agent_id=partner_agent_id,
                status=status_enum
            )
            
            # Check for conflicts before adding
            if calendar.has_conflict(event):
                return {
                    "success": False,
                    "error": "Time slot conflicts with existing event",
                    "event_id": None
                }
            
            calendar.add_event(event)
        
        # Save to database
        db_adapter.save_event(event)
        
        return {
            "success": True,
            "event_id": event.event_id,
            "start_time": event.time.isoformat(),
            "duration": event.duration,
            "status": event.status.value if hasattr(event.status, 'value') else str(event.status),
            "partner_agent_id": event.partner_agent_id,
            "matches_preferences": preferences.is_preferred_time(event_time)
        }
    
    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
            "event_id": None
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "event_id": None
        }


@mcp.tool
def deleteBooking(event_id: str) -> Dict[str, Any]:
    """Delete/cancel a booking by event ID.
    
    Args:
        event_id: The event ID to delete
    
    Returns:
        Dictionary with deletion status
    """
    try:
        calendar = get_calendar()
        
        # Get event first to return info
        event = calendar.get_event(event_id)
        
        if event is None:
            return {
                "success": False,
                "error": f"Event {event_id} not found",
                "event_id": event_id
            }
        
        # Remove from calendar
        removed = calendar.remove_event(event_id)
        
        if removed:
            # Delete from database
            db_adapter.delete_event(event_id)
            
            return {
                "success": True,
                "event_id": event_id,
                "deleted_time": event.time.isoformat(),
                "status": event.status.value if hasattr(event.status, 'value') else str(event.status)
            }
        else:
            return {
                "success": False,
                "error": "Failed to remove event from calendar",
                "event_id": event_id
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
            "event_id": event_id
        }


def run_mcp_server(host: str = "localhost", port: int = 8000):
    """Run the MCP server with SSE transport and merged A2A server (can be called from another process/thread).
    
    Args:
        host: Host to bind the server to
        port: Port to bind the server to
    
    Returns:
        The URL of the MCP server
    """
    # MCP server is mounted under /mcp path
    server_url = f"http://{host}:{port}/mcp"
    print(f"\n{'='*60}")
    print(f"🚀 Starting MCP Server with merged A2A on port {port}")
    print(f"📋 Agent DID: {agent.get_did()}")
    print(f"🔗 Service Endpoints:")
    for service_name, endpoint in agent.get_service_endpoints().items():
        print(f"   {service_name}: {endpoint}")
    print(f"{'='*60}\n")
    
    # FastMCP accepts transport kwargs for HTTP-based transports
    # Use streamable-http to support both SSE and custom HTTP routes
    try:
        from starlette.middleware import Middleware
        from starlette.middleware.cors import CORSMiddleware
        import uvicorn
        from fastapi import FastAPI
        from starlette.routing import Mount
        
        # Create A2A Starlette app to mount under /a2a
        from a2a_server import create_a2a_server
        a2a_starlette_app = create_a2a_server(host=host, port=port)
        
        http_middleware = [
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        ]
        
        # Create a unified FastAPI app that mounts both MCP and A2A
        if a2a_starlette_app:
            try:
                # Create a main FastAPI app
                main_app = FastAPI(title="Calendar Agent Server", middleware=http_middleware)
                
                # Get the FastMCP's SSE app - this is the Starlette app that handles SSE
                # FastMCP creates this when using streamable-http transport
                # We need to get the app that FastMCP would create
                try:
                    # Try to get the SSE app from FastMCP
                    if hasattr(mcp, 'sse_app'):
                        mcp_sse_app = mcp.sse_app()
                    elif hasattr(mcp, '_sse_app'):
                        mcp_sse_app = mcp._sse_app()
                    else:
                        # FastMCP may not expose this directly
                        # We'll need to mount the MCP routes manually
                        mcp_sse_app = None
                    
                    if mcp_sse_app:
                        # Mount MCP SSE app under /mcp
                        main_app.mount("/mcp", mcp_sse_app)
                        print(f"✅ MCP SSE app mounted at /mcp")
                    
                    # Mount A2A Starlette app under /a2a
                    main_app.mount("/a2a", a2a_starlette_app)
                    print(f"✅ A2A FastAPI app mounted at /a2a")
                    
                    # Also add the agent card route at root (it's already in A2A app, but we want it accessible)
                    # The A2A app should have it at /.well-known/agent-card.json
                    # But when mounted at /a2a, it becomes /a2a/.well-known/agent-card.json
                    # So we add a route at root to proxy to the mounted location
                    @main_app.get("/.well-known/agent-card.json")
                    async def get_agent_card_root():
                        from a2a_server import create_agent_card
                        agent_card = create_agent_card(host=host, port=port)
                        from fastapi.responses import JSONResponse
                        return JSONResponse(agent_card)
                    
                    print(f"✅ Running unified MCP + A2A server")
                    print(f"   MCP endpoint: http://{host}:{port}/mcp")
                    print(f"   A2A base: http://{host}:{port}/a2a")
                    print(f"   A2A agent card: http://{host}:{port}/.well-known/agent-card.json")
                    
                    uvicorn.run(main_app, host=host, port=port, log_level="info")
                    return
                except Exception as sse_error:
                    print(f"⚠️  Could not get MCP SSE app: {sse_error}")
                    import traceback
                    traceback.print_exc()
            except Exception as mount_error:
                print(f"⚠️  Could not create unified app: {mount_error}")
                import traceback
                traceback.print_exc()
        
        # Fallback: Run FastMCP normally (A2A may not be available or mounting failed)
        print(f"✅ Running MCP server")
        print(f"   MCP endpoint: http://{host}:{port}/mcp")
        if a2a_starlette_app:
            print(f"   A2A agent card: http://{host}:{port}/.well-known/agent-card.json")
        
        # Run with streamable-http to support both SSE and custom routes
        # Mount MCP server under /mcp path
        mcp.run(transport="streamable-http", middleware=http_middleware, host=host, port=port, path="/mcp")
        print(f"✅ MCP server running at http://{host}:{port}/mcp (SSE endpoint)")
    except Exception as e:
        print(f"⚠️ Error running MCP server: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to SSE only
        try:
            mcp.run(transport="sse", host=host, port=port)
        except TypeError:
            # If host/port not supported, try without them (will use stdio)
            print(f"⚠️ Host/port not supported, using stdio transport")
            server_url = "stdio://sse"
            mcp.run(transport="sse")
    return server_url


if __name__ == "__main__":
    # Run the MCP server
    run_mcp_server()

