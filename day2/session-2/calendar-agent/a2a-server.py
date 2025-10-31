"""A2A (Agent2Agent) Protocol Server for Calendar Agent.

This module exposes the calendar agent's booking capabilities through the A2A protocol,
allowing other agents to interact with the calendar system for scheduling meetings.

Based on the A2A Protocol specification: https://a2a-protocol.org
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import importlib.util

# Import A2A SDK - no conflict since this file is named a2a-server.py
A2A_AVAILABLE = False
A2AServer = None
AgentCard = None
Tool = None
Skill = None
A2AStarletteApplication = None
RequestHandler = None
RESTHandler = None
uvicorn = None

try:
    from a2a.types import AgentCard as A2AAgentCard, AgentSkill, AgentCapabilities
    from a2a.server.apps.rest.fastapi_app import A2ARESTFastAPIApplication as A2AFastAPIApp
    from a2a.server.request_handlers.request_handler import RequestHandler as A2ARequestHandler
    
    try:
        import uvicorn
    except ImportError:
        uvicorn = None
    
    A2A_AVAILABLE = True
    AgentCard = A2AAgentCard
    A2ARESTFastAPIApplication = A2AFastAPIApp
    RequestHandler = A2ARequestHandler
    
    print("✅ A2A SDK imported successfully")
except Exception as e:
    A2A_AVAILABLE = False
    print(f"⚠️  A2A SDK import error: {e}")
    import traceback
    traceback.print_exc()

if not A2A_AVAILABLE:
    print("⚠️  A2A SDK not installed. Install with: uv add 'a2a-sdk[http-server]'")
    print("   Or: pip install 'a2a-sdk[http-server]'")
    print("   See: https://github.com/a2aproject/a2a-python")

# Import local calendar modules
spec = importlib.util.spec_from_file_location("calendar_module", Path(__file__).parent / "calendar_module.py")
calendar_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calendar_module)

spec_db = importlib.util.spec_from_file_location("db_adapter", Path(__file__).parent / "db_adapter.py")
db_adapter_module = importlib.util.module_from_spec(spec_db)
spec_db.loader.exec_module(db_adapter_module)

Calendar = calendar_module.Calendar
Event = calendar_module.Event
EventStatus = calendar_module.EventStatus
BookingPreferences = calendar_module.BookingPreferences
CalendarDBAdapter = db_adapter_module.CalendarDBAdapter

# Initialize database adapter
DB_PATH = "calendar_agent.db"
db_adapter = CalendarDBAdapter(db_path=DB_PATH)

# Global calendar instance
_calendar: Optional[Calendar] = None
_preferences: Optional[BookingPreferences] = None


def get_calendar(reload: bool = True) -> Calendar:
    """Get or initialize the calendar instance."""
    global _calendar
    if _calendar is None or reload:
        _calendar = Calendar(owner_agent_id="a2a-agent")
        saved_events = db_adapter.load_all_events(Event, EventStatus)
        for event in saved_events:
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
            _preferences = BookingPreferences()
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
    """Check if a time slot is available."""
    temp_event = Event(
        time=start_time,
        duration=f"{duration_minutes}m",
        partner_agent_id="temp_check",
        status=EventStatus.PROPOSED
    )
    
    if calendar.has_conflict(temp_event):
        return False
    
    if not preferences.is_preferred_time(start_time):
        return False
    
    return True


def create_agent_card(host: str = "localhost", port: int = 10000):
    """Create the AgentCard describing this calendar agent's capabilities.
    
    Args:
        host: Host for the A2A server endpoint
        port: Port for the A2A server endpoint
    
    Returns:
        AgentCard object matching the A2A protocol specification
    """
    if not A2A_AVAILABLE or not AgentCard or not AgentSkill or not AgentCapabilities:
        raise RuntimeError("A2A SDK not available. Cannot create AgentCard.")
    
    url = os.getenv("A2A_ENDPOINT", f"http://{host}:{port}")
    
    # Create tools list (tools are stored as part of the skill's additional data)
    # Note: Tools are not directly part of AgentSkill in A2A spec, but we can store them
    # in the skill's description or as part of the skill structure
    tools_data = [
                    {
                        "name": "requestAvailableSlots",
                        "description": "Get available time slots for booking within a date range",
                        "input_schema": {
                            "type": "object",
                            "required": ["start_date", "end_date"],
                            "properties": {
                                "start_date": {
                                    "type": "string",
                                    "format": "date",
                                    "description": "Start date for availability check (YYYY-MM-DD)"
                                },
                                "end_date": {
                                    "type": "string",
                                    "format": "date",
                                    "description": "End date for availability check (YYYY-MM-DD)"
                                },
                                "duration": {
                                    "type": "string",
                                    "default": "30m",
                                    "description": "Desired meeting duration (e.g., '30m', '1h', '45m')"
                                },
                                "partner_agent_id": {
                                    "type": "string",
                                    "description": "Optional partner agent ID to filter availability"
                                },
                                "timezone": {
                                    "type": "string",
                                    "default": "UTC",
                                    "description": "Timezone for the availability check"
                                },
                                "slot_granularity_minutes": {
                                    "type": "integer",
                                    "default": 30,
                                    "description": "Granularity of time slots in minutes"
                                }
                            }
                        },
                        "output_schema": {
                            "type": "object",
                            "properties": {
                                "available_slots": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "start": {"type": "string", "format": "date-time"},
                                            "end": {"type": "string", "format": "date-time"},
                                            "duration_minutes": {"type": "integer"}
                                        }
                                    }
                                },
                                "total_slots": {"type": "integer"},
                                "preferences_matched": {"type": "boolean"}
                            }
                        }
                    },
                    {
                        "name": "requestBooking",
                        "description": "Request a booking for a meeting at a specific time",
                        "input_schema": {
                            "type": "object",
                            "required": ["start_time", "duration", "partner_agent_id"],
                            "properties": {
                                "start_time": {
                                    "type": "string",
                                    "format": "date-time",
                                    "description": "Start time in ISO format (e.g., '2025-01-15T10:00:00Z')"
                                },
                                "duration": {
                                    "type": "string",
                                    "description": "Meeting duration (e.g., '30m', '1h', '45m')"
                                },
                                "partner_agent_id": {
                                    "type": "string",
                                    "description": "Agent ID of the partner requesting the meeting"
                                },
                                "initial_status": {
                                    "type": "string",
                                    "enum": ["proposed", "accepted", "confirmed"],
                                    "default": "proposed",
                                    "description": "Initial status of the booking"
                                }
                            }
                        },
                        "output_schema": {
                            "type": "object",
                            "properties": {
                                "success": {"type": "boolean"},
                                "event_id": {"type": "string"},
                                "start_time": {"type": "string", "format": "date-time"},
                                "duration": {"type": "string"},
                                "status": {"type": "string"},
                                "matches_preferences": {"type": "boolean"},
                                "error": {"type": "string"}
                            }
                        }
                    },
                    {
                        "name": "deleteBooking",
                        "description": "Delete or cancel a booking by event ID",
                        "input_schema": {
                            "type": "object",
                            "required": ["event_id"],
                            "properties": {
                                "event_id": {
                                    "type": "string",
                                    "description": "The event ID to delete"
                                }
                            }
                        },
                        "output_schema": {
                            "type": "object",
                            "properties": {
                                "success": {"type": "boolean"},
                                "event_id": {"type": "string"},
                                "error": {"type": "string"}
                            }
                        }
                    }
                ]
    
    # Return the agent card dictionary
    return {
        "name": "Calendar Agent",
        "description": "A calendar management agent that can check availability and book meetings. Provides tools for finding available time slots, requesting bookings, and managing calendar events.",
        "version": "0.1.0",
        "url": url,
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["text/plain", "application/json"],
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False
        },
        "skills": [
            {
                "id": "calendar_booking",
                "name": "calendar_booking",
                "description": "Tools for calendar booking and scheduling",
                "tags": ["calendar", "scheduling", "booking", "meetings", "availability"],
                "tools": tools_data
            }
        ]
    }


def handle_request_available_slots(tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """Handle requestAvailableSlots tool call."""
    try:
        calendar = get_calendar()
        preferences = get_preferences()
        
        start_date = datetime.fromisoformat(tool_input["start_date"])
        end_date = datetime.fromisoformat(tool_input["end_date"])
        duration = tool_input.get("duration", "30m")
        duration_minutes = _parse_duration(duration)
        slot_granularity = tool_input.get("slot_granularity_minutes", 30)
        
        # Generate time slots
        available_slots = []
        current_time = start_date.replace(hour=preferences.preferred_start_hour, minute=0, second=0)
        end_time = end_date.replace(hour=preferences.preferred_end_hour, minute=0, second=0)
        
        while current_time < end_time:
            slot_end = current_time + timedelta(minutes=duration_minutes)
            
            if slot_end <= end_time:
                # Check if slot is available
                if _is_time_slot_available(calendar, current_time, duration_minutes, preferences):
                    available_slots.append({
                        "start": current_time.isoformat(),
                        "end": slot_end.isoformat(),
                        "duration_minutes": duration_minutes
                    })
            
            current_time += timedelta(minutes=slot_granularity)
        
        return {
            "available_slots": available_slots,
            "total_slots": len(available_slots),
            "preferences_matched": True
        }
    except Exception as e:
        return {
            "available_slots": [],
            "total_slots": 0,
            "error": str(e)
        }


def handle_request_booking(tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """Handle requestBooking tool call."""
    try:
        calendar = get_calendar()
        preferences = get_preferences()
        
        start_time_str = tool_input["start_time"]
        duration = tool_input["duration"]
        partner_agent_id = tool_input["partner_agent_id"]
        initial_status = tool_input.get("initial_status", "proposed")
        
        # Parse start time
        event_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        
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
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "event_id": None
        }


def handle_delete_booking(tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """Handle deleteBooking tool call."""
    try:
        calendar = get_calendar()
        event_id = tool_input["event_id"]
        
        if calendar.remove_event(event_id):
            db_adapter.delete_event(event_id)
            return {
                "success": True,
                "event_id": event_id
            }
        else:
            return {
                "success": False,
                "error": f"Event {event_id} not found or could not be removed",
                "event_id": event_id
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "event_id": tool_input.get("event_id", "unknown")
        }


class SimpleCalendarRequestHandler(RequestHandler if RequestHandler else object):
    """A simple request handler for calendar operations."""
    
    def __init__(self):
        if RequestHandler:
            super().__init__()
    
    async def on_get_task(self, params, context=None):
        from a2a.utils.errors import ServerError
        from a2a.types import TaskNotFoundError
        raise ServerError(error=TaskNotFoundError())
    
    async def on_cancel_task(self, params, context=None):
        from a2a.utils.errors import ServerError
        from a2a.types import TaskNotFoundError
        raise ServerError(error=TaskNotFoundError())
    
    async def on_message_send(self, params, context=None):
        # TODO: Implement proper tool handling
        from a2a.types import Message, Task
        # For now, return a simple message
        return Message(content="Calendar agent ready")
    
    async def on_message_send_stream(self, params, context=None):
        from a2a.utils.errors import ServerError
        from a2a.types import UnsupportedOperationError
        raise ServerError(error=UnsupportedOperationError())
    
    async def on_set_task_push_notification_config(self, params, context=None):
        return params
    
    async def on_get_task_push_notification_config(self, params, context=None):
        from a2a.utils.errors import ServerError
        from a2a.types import TaskNotFoundError
        raise ServerError(error=TaskNotFoundError())
    
    async def on_resubscribe_to_task(self, params, context=None):
        from a2a.utils.errors import ServerError
        from a2a.types import UnsupportedOperationError
        raise ServerError(error=UnsupportedOperationError())
    
    async def on_delete_task_push_notification_config(self, params, context=None):
        from a2a.utils.errors import ServerError
        from a2a.types import TaskNotFoundError
        raise ServerError(error=TaskNotFoundError())
    
    async def on_list_task_push_notification_config(self, params, context=None):
        return []


def create_a2a_server(host: str = "localhost", port: int = 10000) -> Optional[Any]:
    """Create and configure the A2A server using the actual SDK.
    
    Args:
        host: Host to bind the server to
        port: Port to bind the server to
        
    Returns:
        FastAPI app instance configured with A2A, or None if SDK not available
    """
    if not A2A_AVAILABLE or not A2ARESTFastAPIApplication or not AgentCard:
        print("❌ A2A SDK not available. Cannot create A2A server.")
        print("   Install with: uv add 'a2a-sdk[http-server]'")
        print("   Or: pip install 'a2a-sdk[http-server]'")
        return None
    
    try:
        # Create agent card from dict
        agent_card_dict = create_agent_card(host=host, port=port)
        
        try:
            # Convert dict to AgentCard object
            agent_card = AgentCard.model_validate(agent_card_dict)
        except Exception as e:
            print(f"⚠️  Could not create AgentCard object: {e}")
            print("   Using dict directly...")
            # Try to construct from dict fields
            try:
                agent_card = AgentCard(**agent_card_dict)
            except Exception:
                print("❌ Failed to create AgentCard. Check agent card structure.")
                return None
        
        # Create request handler
        request_handler = SimpleCalendarRequestHandler()
        
        # Create A2A FastAPI application
        a2a_app = A2ARESTFastAPIApplication(
            agent_card=agent_card,
            http_handler=request_handler
        )
        
        # Build the FastAPI app - this automatically adds .well-known/agent-card.json route!
        fastapi_app = a2a_app.build()
        
        # Add health check endpoint
        @fastapi_app.get("/health")
        async def health_check():
            """Health check endpoint for the A2A server."""
            return {
                "status": "healthy",
                "service": "Calendar Agent A2A Server",
                "agent_card": {
                    "name": agent_card.name if hasattr(agent_card, 'name') else "Calendar Agent",
                    "version": agent_card.version if hasattr(agent_card, 'version') else "0.1.0",
                    "url": agent_card.url if hasattr(agent_card, 'url') else url
                },
                "endpoints": {
                    "health": f"http://{host}:{port}/health",
                    "agent_card": f"http://{host}:{port}/.well-known/agent-card.json"
                }
            }
        
        print(f"✅ A2A FastAPI app created")
        print(f"📍 Agent card will be served at: http://{host}:{port}/.well-known/agent-card.json")
        print(f"💚 Health check available at: http://{host}:{port}/health")
        
        # Store app and config for later
        fastapi_app._a2a_host = host
        fastapi_app._a2a_port = port
        fastapi_app._a2a_agent_card = agent_card
        
        return fastapi_app
        
    except Exception as e:
        print(f"❌ Failed to create A2A server: {e}")
        import traceback
        traceback.print_exc()
        return None


def _add_agent_card_route_after_init(server, agent_card_dict, host, port):
    """Try to add agent card route after server initialization."""
    try:
        import time
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        
        # Wait a moment for server to initialize
        time.sleep(0.1)
        
        # Try to find the app again
        app = None
        for attr_name in ['app', '_app', 'fastapi_app', 'server', '_server']:
            if hasattr(server, attr_name):
                try:
                    potential_app = getattr(server, attr_name)
                    if isinstance(potential_app, FastAPI) or hasattr(potential_app, 'get') or hasattr(potential_app, 'router'):
                        app = potential_app
                        break
                except:
                    pass
        
        if app:
            try:
                if isinstance(app, FastAPI) or hasattr(app, 'get'):
                    @app.get("/.well-known/agent-card.json", response_model=None)
                    async def get_agent_card():
                        return JSONResponse(content=agent_card_dict)
                    print(f"✅ Agent card route added at http://{host}:{port}/.well-known/agent-card.json")
                    return True
            except Exception as e:
                print(f"⚠️  Could not add route to app: {e}")
        
        return False
    except Exception as e:
        return False


def run_a2a_server(host: str = "localhost", port: int = 10000):
    """Run the A2A server using uvicorn.
    
    Args:
        host: Host to bind the server to
        port: Port to bind the server to
    """
    if not uvicorn:
        print("❌ uvicorn not available. Cannot run A2A server.")
        print("   Install with: uv add 'uvicorn' or pip install 'uvicorn'")
        return
    
    fastapi_app = create_a2a_server(host=host, port=port)
    if fastapi_app:
        agent_card_name = "Calendar Agent"
        if hasattr(fastapi_app, '_a2a_agent_card'):
            agent_card = fastapi_app._a2a_agent_card
            if hasattr(agent_card, 'name'):
                agent_card_name = agent_card.name
        
        print(f"🚀 Starting A2A Calendar Agent Server on http://{host}:{port}")
        print(f"📋 Agent Card: {agent_card_name}")
        print(f"📍 Agent Card Endpoint: http://{host}:{port}/.well-known/agent-card.json")
        print(f"🔧 Available tools: requestAvailableSlots, requestBooking, deleteBooking")
        print(f"✅ Server will serve agent card at /.well-known/agent-card.json automatically")
        
        # Run the FastAPI app with uvicorn
        uvicorn.run(fastapi_app, host=host, port=port, log_level="info")
    else:
        print("❌ Cannot run A2A server - SDK not available")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Calendar Agent A2A Server")
    parser.add_argument("--host", default="localhost", help="Host to bind server to")
    parser.add_argument("--port", type=int, default=10000, help="Port to bind server to")
    args = parser.parse_args()
    
    run_a2a_server(host=args.host, port=args.port)

