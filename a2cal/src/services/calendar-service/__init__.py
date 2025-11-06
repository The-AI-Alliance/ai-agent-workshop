"""Shared calendar service for the A2Cal application."""
from typing import Optional
from pathlib import Path
import sys
import os

# Get the directory of this file
_current_dir = os.path.dirname(os.path.abspath(__file__))

# Import calendar classes using absolute imports from the same directory
# This works when the file is loaded directly or via importlib
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)

from calendar_api import Calendar, Event, EventStatus, BookingPreferences
from db_adapter import CalendarDBAdapter

# Default database path
CALENDAR_DB = "calendar_agent.db"

# Global shared instances (singleton pattern)
_shared_db_adapter: Optional[CalendarDBAdapter] = None
_shared_calendar: Optional[Calendar] = None


def get_shared_calendar_service(db_path: str = CALENDAR_DB, owner_agent_id: str = None):
    """Get or create shared calendar service instances.
    
    Args:
        db_path: Path to the SQLite database file
        owner_agent_id: Optional owner agent ID for the calendar
        
    Returns:
        tuple: (db_adapter, calendar) - Shared instances
    """
    global _shared_db_adapter, _shared_calendar
    
    # Initialize DB adapter if not exists
    if _shared_db_adapter is None:
        _shared_db_adapter = CalendarDBAdapter(db_path=db_path)
    
    # Initialize calendar if not exists
    if _shared_calendar is None:
        _shared_calendar = Calendar(owner_agent_id=owner_agent_id)
        # Load existing events from database
        try:
            existing_events = _shared_db_adapter.load_all_events(Event, EventStatus)
            for event in existing_events:
                _shared_calendar.add_event(event)
            print(f'Loaded {len(existing_events)} events from database into shared calendar')
        except Exception as e:
            print(f'Error loading events from database: {e}')
    
    return _shared_db_adapter, _shared_calendar


def reset_shared_calendar_service():
    """Reset shared calendar service (useful for testing)."""
    global _shared_db_adapter, _shared_calendar
    _shared_db_adapter = None
    _shared_calendar = None

