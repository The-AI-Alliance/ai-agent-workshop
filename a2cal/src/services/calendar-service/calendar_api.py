from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict
from uuid import uuid4
import pydantic

class EventStatus(str, Enum):
    """Status of a calendar event in the negotiation process."""
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CONFIRMED = "confirmed"
    BOOKED = "booked"
    FAILED = "failed"
    NO_SHOW = "no_show"

class Event(pydantic.BaseModel):
    """Represents a calendar event/meeting."""
    
    event_id: str = pydantic.Field(default_factory=lambda: f"evt-{uuid4().hex[:8]}")
    time: datetime
    duration: str  # e.g., "30m", "1h", "45m"
    status: EventStatus = EventStatus.PROPOSED
    partner_agent_id: str
    title: Optional[str] = None  # Optional meeting title
    created_at: datetime = pydantic.Field(default_factory=datetime.utcnow)
    updated_at: datetime = pydantic.Field(default_factory=datetime.utcnow)
    
    model_config = pydantic.ConfigDict(
        use_enum_values=True,
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )
    
    def get_end_time(self) -> datetime:
        """Calculate the end time of the event based on duration."""
        duration_minutes = self._parse_duration(self.duration)
        return self.time + timedelta(minutes=duration_minutes)
    
    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string (e.g., '30m', '1h', '45m') to minutes."""
        duration_str = duration_str.lower().strip()
        if duration_str.endswith('m'):
            return int(duration_str[:-1])
        elif duration_str.endswith('h'):
            return int(duration_str[:-1]) * 60
        else:
            # Assume minutes if no unit specified
            return int(duration_str)
    
    def overlaps_with(self, other: "Event") -> bool:
        """Check if this event overlaps with another event."""
        self_end = self.get_end_time()
        other_end = other.get_end_time()
        
        # Check if events overlap
        return (self.time < other_end and self_end > other.time)
    
    def update_status(self, new_status: EventStatus):
        """Update the event status and timestamp."""
        self.status = new_status
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Convert event to dictionary for JSON serialization."""
        # Handle both enum and string status values
        status_str = self.status.value if hasattr(self.status, 'value') else str(self.status)
        
        return {
            "event_id": self.event_id,
            "time": self.time.isoformat(),
            "duration": self.duration,
            "status": status_str,
            "partner_agent_id": self.partner_agent_id,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class Calendar:
    """Manages calendar events and negotiations."""
    
    def __init__(self, owner_agent_id: Optional[str] = None):
        self.owner_agent_id = owner_agent_id
        self.events: Dict[str, Event] = {}
    
    def add_event(self, event: Event) -> Event:
        """Add an event to the calendar. Returns the event if added, raises ValueError if conflict."""
        # Check for conflicts
        if self.has_conflict(event):
            raise ValueError(f"Event conflicts with existing events")
        
        # Ensure event has an ID
        if not event.event_id:
            # This shouldn't happen as Event auto-generates IDs, but just in case
            from uuid import uuid4
            event.event_id = f"evt-{uuid4().hex[:8]}"
        
        # Add event to calendar
        self.events[event.event_id] = event
        return event
    
    def remove_event(self, event_id: str) -> bool:
        """Remove an event from the calendar."""
        if event_id in self.events:
            del self.events[event_id]
            return True
        return False
    
    def get_event(self, event_id: str) -> Optional[Event]:
        """Get an event by ID."""
        return self.events.get(event_id)
    
    def has_conflict(self, new_event: Event) -> bool:
        """Check if a new event would conflict with existing events."""
        # Status values that should be checked for conflicts
        conflict_statuses = ["booked", "confirmed", "accepted"]
        
        for existing_event in self.events.values():
            # Get status as string for comparison
            existing_status = getattr(existing_event.status, 'value', None) if hasattr(existing_event.status, 'value') else str(existing_event.status)
            existing_status = existing_status.lower() if existing_status else ""
            
            # Only check conflicts with booked/confirmed/accepted events
            if existing_status in conflict_statuses:
                if new_event.overlaps_with(existing_event):
                    return True
        return False
    
    def get_events_by_status(self, status: EventStatus) -> List[Event]:
        """Get all events with a specific status."""
        return [event for event in self.events.values() if event.status == status]
    
    def get_events_by_partner(self, partner_agent_id: str) -> List[Event]:
        """Get all events with a specific partner agent."""
        return [event for event in self.events.values() if event.partner_agent_id == partner_agent_id]
    
    def get_pending_events(self) -> List[Event]:
        """Get all events that are pending (proposed or accepted but not confirmed)."""
        return [
            event for event in self.events.values()
            if event.status in [EventStatus.PROPOSED, EventStatus.ACCEPTED]
        ]
    
    def get_confirmed_events(self) -> List[Event]:
        """Get all confirmed or booked events."""
        return [
            event for event in self.events.values()
            if event.status in [EventStatus.CONFIRMED, EventStatus.BOOKED]
        ]
    
    def propose_event(self, time: datetime, duration: str, partner_agent_id: str, title: Optional[str] = None) -> Event:
        """Propose a new meeting event."""
        event = Event(
            time=time,
            duration=duration,
            partner_agent_id=partner_agent_id,
            status=EventStatus.PROPOSED,
            title=title
        )
        return self.add_event(event)
    
    def accept_event(self, event_id: str) -> Optional[Event]:
        """Accept a proposed event."""
        event = self.get_event(event_id)
        if event and event.status == EventStatus.PROPOSED:
            event.update_status(EventStatus.ACCEPTED)
            return event
        return None
    
    def reject_event(self, event_id: str) -> Optional[Event]:
        """Reject a proposed event."""
        event = self.get_event(event_id)
        if event and event.status == EventStatus.PROPOSED:
            event.update_status(EventStatus.REJECTED)
            return event
        return None
    
    def confirm_event(self, event_id: str) -> Optional[Event]:
        """Confirm an accepted event (mark as booked)."""
        event = self.get_event(event_id)
        if event and event.status in [EventStatus.ACCEPTED, EventStatus.PROPOSED]:
            event.update_status(EventStatus.CONFIRMED)
            return event
        return None
    
    def mark_booked(self, event_id: str) -> Optional[Event]:
        """Mark an event as booked (final status)."""
        event = self.get_event(event_id)
        if event:
            event.update_status(EventStatus.BOOKED)
            return event
        return None
    
    def mark_failed(self, event_id: str) -> Optional[Event]:
        """Mark an event as failed (e.g., no-show)."""
        event = self.get_event(event_id)
        if event:
            event.update_status(EventStatus.FAILED)
            return event
        return None
    
    def get_all_events(self) -> List[Event]:
        """Get all events in the calendar."""
        return list(self.events.values())
    
    def get_upcoming_events(self, limit: Optional[int] = None) -> List[Event]:
        """Get upcoming events sorted by time."""
        now = datetime.utcnow()
        upcoming = [
            event for event in self.events.values()
            if event.time > now and event.status in [EventStatus.ACCEPTED, EventStatus.CONFIRMED, EventStatus.BOOKED]
        ]
        upcoming.sort(key=lambda e: e.time)
        if limit:
            return upcoming[:limit]
        return upcoming
    
    def count_by_status(self) -> Dict[str, int]:
        """Count events by status."""
        counts = {}
        for event in self.events.values():
            # Handle both enum and string status values
            if hasattr(event.status, 'value'):
                status = event.status.value
            else:
                status = str(event.status)
            counts[status] = counts.get(status, 0) + 1
        return counts
    
    def clear(self):
        """Clear all events from the calendar."""
        self.events.clear()
    
    def get_available_slots(self, start_date: datetime, end_date: datetime, duration: str = "30m", buffer_minutes: int = 15) -> List[Dict]:
        """Get available time slots between start_date and end_date.
        
        Args:
            start_date: Start datetime for the search window
            end_date: End datetime for the search window
            duration: Duration of the meeting (e.g., "30m", "1h", "45m")
            buffer_minutes: Buffer time between meetings in minutes (default: 15)
            
        Returns:
            List of dictionaries with available time slots, each containing:
            - start: ISO format datetime string
            - end: ISO format datetime string
            - duration: duration string
        """
        # Parse duration to minutes
        duration_str = duration.lower().strip()
        if duration_str.endswith('m'):
            duration_minutes = int(duration_str[:-1])
        elif duration_str.endswith('h'):
            duration_minutes = int(duration_str[:-1]) * 60
        else:
            duration_minutes = int(duration_str)
        
        # Get all booked/confirmed/accepted events in the time range
        booked_events = []
        for event in self.events.values():
            status_str = event.status.value if hasattr(event.status, 'value') else str(event.status)
            status_str = status_str.lower()
            # Only consider events that block time
            if status_str in ['booked', 'confirmed', 'accepted']:
                if start_date <= event.time <= end_date or start_date <= event.get_end_time() <= end_date:
                    booked_events.append(event)
        
        # Sort by start time
        booked_events.sort(key=lambda e: e.time)
        
        # Find available slots
        available_slots = []
        current_time = start_date
        
        for event in booked_events:
            # If there's a gap before this event, add it as a slot
            gap_start = current_time
            gap_end = event.time
            
            # Add buffer time requirement
            effective_gap = (gap_end - gap_start).total_seconds() / 60
            
            if effective_gap >= (duration_minutes + buffer_minutes):
                # Add slots in this gap
                slot_start = gap_start
                while slot_start + timedelta(minutes=duration_minutes + buffer_minutes) <= gap_end:
                    slot_end = slot_start + timedelta(minutes=duration_minutes)
                    if slot_end <= end_date:
                        available_slots.append({
                            "start": slot_start.isoformat(),
                            "end": slot_end.isoformat(),
                            "duration": duration
                        })
                    # Move to next slot (with buffer)
                    slot_start += timedelta(minutes=duration_minutes + buffer_minutes)
            
            # Update current_time to after this event (with buffer)
            current_time = max(current_time, event.get_end_time() + timedelta(minutes=buffer_minutes))
        
        # Check for available slots after the last event
        if current_time < end_date:
            slot_start = current_time
            while slot_start + timedelta(minutes=duration_minutes) <= end_date:
                slot_end = slot_start + timedelta(minutes=duration_minutes)
                available_slots.append({
                    "start": slot_start.isoformat(),
                    "end": slot_end.isoformat(),
                    "duration": duration
                })
                slot_start += timedelta(minutes=duration_minutes + buffer_minutes)
        
        return available_slots


class BookingPreferences(pydantic.BaseModel):
    """Preferences for how the calendar agent should book meetings."""
    
    # Time preferences
    preferred_start_hour: int = 9  # 24-hour format
    preferred_end_hour: int = 17  # 24-hour format
    preferred_days: List[str] = pydantic.Field(default_factory=lambda: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])
    
    # Duration preferences
    preferred_duration: str = "30m"  # Default preferred duration
    min_duration: str = "15m"  # Minimum acceptable duration
    max_duration: str = "2h"  # Maximum acceptable duration
    
    # Scheduling constraints
    buffer_between_meetings: int = 15  # Minutes of buffer time required
    max_meetings_per_day: int = 8  # Maximum number of meetings per day
    max_meetings_per_week: int = 25  # Maximum number of meetings per week
    
    # Auto-acceptance preferences
    auto_accept_preferred_times: bool = False
    require_confirmation: bool = True
    
    # Partner preferences
    preferred_partners: List[str] = pydantic.Field(default_factory=list)  # Agent IDs to prioritize
    blocked_partners: List[str] = pydantic.Field(default_factory=list)  # Agent IDs to avoid
    
    # Trust/reputation preferences
    min_trust_score: float = 0.0  # Minimum trust score to accept (0.0 to 1.0)
    allow_new_partners: bool = True  # Whether to accept meetings from unknown partners
    
    # Other preferences
    timezone: str = "UTC"
    allow_back_to_back: bool = False  # Allow meetings with no buffer
    automation_level: int = 3  # Automation level (1-5): 1=manual, 5=fully automated
    
    # Natural language instructions
    instructions: str = ""  # Human-readable instructions for how the agent should behave
    
    model_config = pydantic.ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )
    
    def is_preferred_time(self, event_time: datetime) -> bool:
        """Check if a time matches preferred scheduling preferences."""
        hour = event_time.hour
        day_name = event_time.strftime("%A")
        
        # Check if hour is within preferred range (inclusive start, exclusive end)
        time_ok = self.preferred_start_hour <= hour < self.preferred_end_hour
        # Check if day is in preferred days list
        day_ok = day_name in self.preferred_days if self.preferred_days else True
        
        return time_ok and day_ok
    
    def can_accept_meeting(self, event: Event, existing_events: List[Event]) -> bool:
        """Check if a meeting can be accepted based on preferences."""
        # Check preferred time
        if not self.is_preferred_time(event.time):
            return False
        
        # Check buffer time
        if not self.allow_back_to_back:
            for existing in existing_events:
                if existing.status in [EventStatus.BOOKED, EventStatus.CONFIRMED, EventStatus.ACCEPTED]:
                    time_diff = abs((event.time - existing.get_end_time()).total_seconds() / 60)
                    if time_diff < self.buffer_between_meetings:
                        return False
        
        # Check max meetings per day
        same_day_events = [e for e in existing_events if e.time.date() == event.time.date()]
        if len(same_day_events) >= self.max_meetings_per_day:
            return False
        
        # Check blocked partners
        if event.partner_agent_id in self.blocked_partners:
            return False
        
        return True
    
    def to_dict(self) -> Dict:
        """Convert preferences to dictionary for JSON serialization."""
        return {
            "preferred_start_hour": self.preferred_start_hour,
            "preferred_end_hour": self.preferred_end_hour,
            "preferred_days": self.preferred_days,
            "preferred_duration": self.preferred_duration,
            "min_duration": self.min_duration,
            "max_duration": self.max_duration,
            "buffer_between_meetings": self.buffer_between_meetings,
            "max_meetings_per_day": self.max_meetings_per_day,
            "max_meetings_per_week": self.max_meetings_per_week,
            "auto_accept_preferred_times": self.auto_accept_preferred_times,
            "require_confirmation": self.require_confirmation,
            "preferred_partners": self.preferred_partners,
            "blocked_partners": self.blocked_partners,
            "min_trust_score": self.min_trust_score,
            "allow_new_partners": self.allow_new_partners,
            "timezone": self.timezone,
            "allow_back_to_back": self.allow_back_to_back,
            "instructions": self.instructions
        }

