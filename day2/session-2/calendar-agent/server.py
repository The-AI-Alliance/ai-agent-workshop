"""MCP Server for Calendar Agent using FastMCP."""
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from fastmcp import FastMCP
import sys
from pathlib import Path

# Add current directory to path to import local modules
sys.path.insert(0, str(Path(__file__).parent))

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

# Initialize MCP server
mcp = FastMCP("Calendar Agent MCP Server")

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
    """Run the MCP server with SSE transport (can be called from another process/thread).
    
    Args:
        host: Host to bind the server to
        port: Port to bind the server to
    
    Returns:
        The URL of the MCP server
    """
    server_url = f"http://{host}:{port}/sse"
    print(f"🚀 Starting MCP Server with SSE transport on {server_url}")
    # FastMCP accepts transport kwargs for HTTP-based transports
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

