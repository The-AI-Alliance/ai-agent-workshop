"""SQLite adapter for persisting Calendar and BookingPreferences to local database."""
import sqlite3
import json
from datetime import datetime
from typing import Optional, List
from pathlib import Path


class CalendarDBAdapter:
    """Adapter for persisting calendar events and preferences to SQLite database."""
    
    def __init__(self, db_path: str = "calendar_agent.db"):
        """Initialize the database adapter.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    time TEXT NOT NULL,
                    duration TEXT NOT NULL,
                    status TEXT NOT NULL,
                    partner_agent_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # Preferences table (single row)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS preferences (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    preferred_start_hour INTEGER,
                    preferred_end_hour INTEGER,
                    preferred_days TEXT,
                    preferred_duration TEXT,
                    min_duration TEXT,
                    max_duration TEXT,
                    buffer_between_meetings INTEGER,
                    max_meetings_per_day INTEGER,
                    max_meetings_per_week INTEGER,
                    auto_accept_preferred_times INTEGER,
                    require_confirmation INTEGER,
                    preferred_partners TEXT,
                    blocked_partners TEXT,
                    min_trust_score REAL,
                    allow_new_partners INTEGER,
                    timezone TEXT,
                    allow_back_to_back INTEGER,
                    instructions TEXT,
                    updated_at TEXT
                )
            """)
            
            conn.commit()
    
    def save_event(self, event) -> bool:
        """Save a single event to the database.
        
        Args:
            event: Event object to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get status value (handle both enum and string)
                status_value = event.status.value if hasattr(event.status, 'value') else str(event.status)
                
                cursor.execute("""
                    INSERT OR REPLACE INTO events 
                    (event_id, time, duration, status, partner_agent_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id,
                    event.time.isoformat() if isinstance(event.time, datetime) else str(event.time),
                    event.duration,
                    status_value,
                    event.partner_agent_id,
                    event.created_at.isoformat() if isinstance(event.created_at, datetime) else str(event.created_at),
                    event.updated_at.isoformat() if isinstance(event.updated_at, datetime) else str(event.updated_at)
                ))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"🔍 DEBUG: Error saving event {event.event_id}: {e}")
            return False
    
    def load_event(self, event_id: str, event_class):
        """Load a single event from the database.
        
        Args:
            event_id: ID of the event to load
            event_class: Event class to instantiate
            
        Returns:
            Event object or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM events WHERE event_id = ?", (event_id,))
                row = cursor.fetchone()
                
                if row:
                    return self._row_to_event(row, event_class)
                return None
        except Exception as e:
            print(f"🔍 DEBUG: Error loading event {event_id}: {e}")
            return None
    
    def load_all_events(self, event_class, event_status_class):
        """Load all events from the database.
        
        Args:
            event_class: Event class to instantiate
            event_status_class: EventStatus enum class
            
        Returns:
            List of Event objects
        """
        events = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM events ORDER BY time ASC")
                rows = cursor.fetchall()
                
                for row in rows:
                    event = self._row_to_event(row, event_class, event_status_class)
                    if event:
                        events.append(event)
        except Exception as e:
            print(f"🔍 DEBUG: Error loading all events: {e}")
        
        return events
    
    def _row_to_event(self, row, event_class, event_status_class=None):
        """Convert a database row to an Event object."""
        try:
            # Parse status (try enum first, fallback to string)
            status_value = str(row['status']).strip()
            status = status_value  # Default to string
            
            if event_status_class:
                # Try to convert string status back to enum
                status_found = False
                
                # First try: direct lookup by name (PROPOSED, ACCEPTED, etc.)
                try:
                    status = event_status_class[status_value.upper()]
                    status_found = True
                except (KeyError, AttributeError, TypeError):
                    pass
                
                # Second try: lookup by value
                if not status_found:
                    for status_enum in event_status_class:
                        enum_value = status_enum.value if hasattr(status_enum, 'value') else str(status_enum)
                        enum_str = str(enum_value).lower()
                        status_str = str(status_value).lower()
                        
                        if enum_str == status_str or enum_value == status_value:
                            status = status_enum
                            status_found = True
                            break
                
                # If still not found, keep as string (Event model should handle it)
                if not status_found:
                    print(f"🔍 DEBUG: Could not convert status '{status_value}' to enum, keeping as string")
                    status = status_value
            
            return event_class(
                event_id=row['event_id'],
                time=datetime.fromisoformat(row['time']),
                duration=row['duration'],
                status=status,
                partner_agent_id=row['partner_agent_id'],
                created_at=datetime.fromisoformat(row['created_at']),
                updated_at=datetime.fromisoformat(row['updated_at'])
            )
        except Exception as e:
            print(f"🔍 DEBUG: Error converting row to event: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def delete_event(self, event_id: str) -> bool:
        """Delete an event from the database.
        
        Args:
            event_id: ID of the event to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"🔍 DEBUG: Error deleting event {event_id}: {e}")
            return False
    
    def save_all_events(self, events: List) -> bool:
        """Save all events to the database.
        
        Args:
            events: List of Event objects
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for event in events:
                    status_value = event.status.value if hasattr(event.status, 'value') else str(event.status)
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO events 
                        (event_id, time, duration, status, partner_agent_id, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event.event_id,
                        event.time.isoformat() if isinstance(event.time, datetime) else str(event.time),
                        event.duration,
                        status_value,
                        event.partner_agent_id,
                        event.created_at.isoformat() if isinstance(event.created_at, datetime) else str(event.created_at),
                        event.updated_at.isoformat() if isinstance(event.updated_at, datetime) else str(event.updated_at)
                    ))
                
                conn.commit()
                print(f"🔍 DEBUG: Saved {len(events)} events to database")
                return True
        except Exception as e:
            print(f"🔍 DEBUG: Error saving all events: {e}")
            return False
    
    def save_preferences(self, preferences) -> bool:
        """Save preferences to the database.
        
        Args:
            preferences: BookingPreferences object to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO preferences (
                        id, preferred_start_hour, preferred_end_hour, preferred_days,
                        preferred_duration, min_duration, max_duration,
                        buffer_between_meetings, max_meetings_per_day, max_meetings_per_week,
                        auto_accept_preferred_times, require_confirmation,
                        preferred_partners, blocked_partners,
                        min_trust_score, allow_new_partners, timezone,
                        allow_back_to_back, instructions, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    1,  # Always ID = 1 since we only store one preferences object
                    preferences.preferred_start_hour,
                    preferences.preferred_end_hour,
                    json.dumps(preferences.preferred_days),
                    preferences.preferred_duration,
                    preferences.min_duration,
                    preferences.max_duration,
                    preferences.buffer_between_meetings,
                    preferences.max_meetings_per_day,
                    preferences.max_meetings_per_week,
                    1 if preferences.auto_accept_preferred_times else 0,
                    1 if preferences.require_confirmation else 0,
                    json.dumps(preferences.preferred_partners),
                    json.dumps(preferences.blocked_partners),
                    preferences.min_trust_score,
                    1 if preferences.allow_new_partners else 0,
                    preferences.timezone,
                    1 if preferences.allow_back_to_back else 0,
                    preferences.instructions,
                    datetime.utcnow().isoformat()
                ))
                
                conn.commit()
                print(f"🔍 DEBUG: Saved preferences to database")
                return True
        except Exception as e:
            print(f"🔍 DEBUG: Error saving preferences: {e}")
            return False
    
    def load_preferences(self, preferences_class):
        """Load preferences from the database.
        
        Args:
            preferences_class: BookingPreferences class to instantiate
            
        Returns:
            BookingPreferences object or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM preferences WHERE id = 1")
                row = cursor.fetchone()
                
                if row:
                    return self._row_to_preferences(row, preferences_class)
                return None
        except Exception as e:
            print(f"🔍 DEBUG: Error loading preferences: {e}")
            return None
    
    def _row_to_preferences(self, row, preferences_class):
        """Convert a database row to a BookingPreferences object."""
        try:
            return preferences_class(
                preferred_start_hour=row['preferred_start_hour'] or 9,
                preferred_end_hour=row['preferred_end_hour'] or 17,
                preferred_days=json.loads(row['preferred_days']) if row['preferred_days'] else ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                preferred_duration=row['preferred_duration'] or "30m",
                min_duration=row['min_duration'] or "15m",
                max_duration=row['max_duration'] or "2h",
                buffer_between_meetings=row['buffer_between_meetings'] or 15,
                max_meetings_per_day=row['max_meetings_per_day'] or 8,
                max_meetings_per_week=row['max_meetings_per_week'] or 25,
                auto_accept_preferred_times=bool(row['auto_accept_preferred_times']),
                require_confirmation=bool(row['require_confirmation']),
                preferred_partners=json.loads(row['preferred_partners']) if row['preferred_partners'] else [],
                blocked_partners=json.loads(row['blocked_partners']) if row['blocked_partners'] else [],
                min_trust_score=row['min_trust_score'] or 0.0,
                allow_new_partners=bool(row['allow_new_partners']) if row['allow_new_partners'] is not None else True,
                timezone=row['timezone'] or "UTC",
                allow_back_to_back=bool(row['allow_back_to_back']),
                instructions=row['instructions'] or ""
            )
        except Exception as e:
            print(f"🔍 DEBUG: Error converting row to preferences: {e}")
            return None
    
    def clear_all_events(self) -> bool:
        """Clear all events from the database.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM events")
                conn.commit()
                print(f"🔍 DEBUG: Cleared all events from database")
                return True
        except Exception as e:
            print(f"🔍 DEBUG: Error clearing events: {e}")
            return False
    
    def get_event_count(self) -> int:
        """Get the total number of events in the database.
        
        Returns:
            Number of events
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM events")
                return cursor.fetchone()[0]
        except Exception as e:
            print(f"🔍 DEBUG: Error getting event count: {e}")
            return 0

