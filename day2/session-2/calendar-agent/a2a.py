"""A2A (Agent2Agent) Protocol Server for Calendar Agent.

This module exposes the calendar agent's booking capabilities through the A2A protocol,
allowing other agents to interact with the calendar system for scheduling meetings.

Based on the A2A Protocol specification: https://a2a-protocol.org
"""
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import importlib.util

# Try to import a2a-sdk
A2A_AVAILABLE = False
A2AServer = None
AgentCard = None
Tool = None
Skill = None

try:
    # Try different possible import paths
    try:
        from a2a import A2AServer, AgentCard, Tool, Skill
        A2A_AVAILABLE = True
    except ImportError:
        try:
            from a2a_sdk import A2AServer, AgentCard, Tool, Skill
            A2A_AVAILABLE = True
        except ImportError:
            try:
                from a2a.server import A2AServer
                from a2a.models import AgentCard, Tool, Skill
                A2A_AVAILABLE = True
            except ImportError:
                A2A_AVAILABLE = False
except Exception as e:
    A2A_AVAILABLE = False
    print(f"⚠️  A2A SDK import error: {e}")

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


def create_agent_card(host: str = "localhost", port: int = 10000) -> Dict[str, Any]:
    """Create the AgentCard describing this calendar agent's capabilities.
    
    Args:
        host: Host for the A2A server endpoint
        port: Port for the A2A server endpoint
    """
    endpoint = os.getenv("A2A_ENDPOINT", f"http://{host}:{port}")
    return {
        "name": "Calendar Agent",
        "description": "A calendar management agent that can check availability and book meetings. Provides tools for finding available time slots, requesting bookings, and managing calendar events.",
        "version": "0.1.0",
        "endpoint": endpoint,
        "skills": [
            {
                "name": "calendar_booking",
                "description": "Tools for calendar booking and scheduling",
                "tools": [
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


def create_a2a_server(host: str = "localhost", port: int = 10000) -> Optional[Any]:
    """Create and configure the A2A server.
    
    Args:
        host: Host to bind the server to
        port: Port to bind the server to
        
    Returns:
        Configured A2A server instance, or None if A2A SDK is not available
        
    Note:
        The actual A2A SDK API may vary. This implementation provides a flexible
        structure that can be adjusted based on the actual a2a-sdk API.
        See: https://github.com/a2aproject/a2a-python
    """
    if not A2A_AVAILABLE:
        print("❌ A2A SDK not available. Cannot create A2A server.")
        print("   Install with: uv add 'a2a-sdk[http-server]'")
        print("   Or: pip install 'a2a-sdk[http-server]'")
        return None
    
    try:
        # Create agent card dictionary with correct endpoint
        agent_card_dict = create_agent_card(host=host, port=port)
        
        # Try to create agent card object (API may vary)
        try:
            agent_card = AgentCard(**agent_card_dict) if AgentCard else None
        except Exception:
            # If AgentCard constructor fails, use dict directly
            agent_card = agent_card_dict
        
        # Create A2A server (API may vary - adjust as needed)
        try:
            # Try different possible constructor signatures
            if agent_card:
                server = A2AServer(agent_card=agent_card, host=host, port=port)
            else:
                server = A2AServer(agent_card=agent_card_dict, host=host, port=port)
        except TypeError:
            # Try alternative constructor signature
            try:
                server = A2AServer(host=host, port=port)
                if hasattr(server, 'set_agent_card'):
                    server.set_agent_card(agent_card if agent_card else agent_card_dict)
            except Exception as e:
                raise e
        
        # Register tool handlers (API may vary)
        try:
            server.register_tool("requestAvailableSlots", handle_request_available_slots)
            server.register_tool("requestBooking", handle_request_booking)
            server.register_tool("deleteBooking", handle_delete_booking)
        except AttributeError:
            # Alternative registration method
            try:
                if hasattr(server, 'add_tool'):
                    server.add_tool("requestAvailableSlots", handle_request_available_slots)
                    server.add_tool("requestBooking", handle_request_booking)
                    server.add_tool("deleteBooking", handle_delete_booking)
                elif hasattr(server, 'tools'):
                    server.tools["requestAvailableSlots"] = handle_request_available_slots
                    server.tools["requestBooking"] = handle_request_booking
                    server.tools["deleteBooking"] = handle_delete_booking
            except Exception as e:
                print(f"⚠️  Could not register tools: {e}")
                print("   Tool registration method may need adjustment based on SDK version")
        
        return server
    except Exception as e:
        print(f"❌ Failed to create A2A server: {e}")
        print("   Note: The A2A SDK API may differ from what's expected.")
        print("   Please refer to: https://github.com/a2aproject/a2a-python")
        import traceback
        traceback.print_exc()
        return None


def run_a2a_server(host: str = "localhost", port: int = 10000):
    """Run the A2A server.
    
    Args:
        host: Host to bind the server to
        port: Port to bind the server to
    """
    server = create_a2a_server(host=host, port=port)
    if server:
        print(f"🚀 Starting A2A Calendar Agent Server on http://{host}:{port}")
        print(f"📋 Agent Card: {server.agent_card.name}")
        print(f"🔧 Available tools: requestAvailableSlots, requestBooking, deleteBooking")
        server.run()
    else:
        print("❌ Cannot run A2A server - SDK not available")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Calendar Agent A2A Server")
    parser.add_argument("--host", default="localhost", help="Host to bind server to")
    parser.add_argument("--port", type=int, default=10000, help="Port to bind server to")
    args = parser.parse_args()
    
    run_a2a_server(host=args.host, port=args.port)

