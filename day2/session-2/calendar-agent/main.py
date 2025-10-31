import streamlit as st
from datetime import datetime, timedelta
from streamlit_calendar import calendar as st_calendar
import sys
import os
import importlib.util
import threading
from pathlib import Path

# Import local calendar module explicitly to avoid conflicts with built-in calendar
spec = importlib.util.spec_from_file_location("calendar_module", os.path.join(os.path.dirname(__file__), "calendar_module.py"))
calendar_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calendar_module)

Calendar = calendar_module.Calendar
Event = calendar_module.Event
EventStatus = calendar_module.EventStatus
BookingPreferences = calendar_module.BookingPreferences

# Import database adapter
db_spec = importlib.util.spec_from_file_location("db_adapter", os.path.join(os.path.dirname(__file__), "db_adapter.py"))
db_adapter_module = importlib.util.module_from_spec(db_spec)
db_spec.loader.exec_module(db_adapter_module)

CalendarDBAdapter = db_adapter_module.CalendarDBAdapter

# Import MCP server
server_spec = importlib.util.spec_from_file_location("server", os.path.join(os.path.dirname(__file__), "server.py"))
server_module = importlib.util.module_from_spec(server_spec)
server_spec.loader.exec_module(server_module)

# Page config
st.set_page_config(
    page_title="Calendar Agent",
    page_icon="📅",
    layout="wide"
)

# Initialize database adapter
DB_PATH = "calendar_agent.db"
db_adapter = CalendarDBAdapter(db_path=DB_PATH)

# Initialize session state
if 'calendar' not in st.session_state or not isinstance(st.session_state.calendar, Calendar):
    # Try to load from database
    saved_events = db_adapter.load_all_events(Event, EventStatus)
    st.session_state.calendar = Calendar(owner_agent_id="agent-alpha")
    
    # Restore events from database
    if saved_events:
        print(f"🔍 DEBUG: Loading {len(saved_events)} events from database")
        for event in saved_events:
            # Ensure status is properly set (convert string to enum if needed)
            if isinstance(event.status, str) and hasattr(EventStatus, event.status.upper()):
                try:
                    event.status = EventStatus[event.status.upper()]
                except:
                    pass
            st.session_state.calendar.events[event.event_id] = event
        print(f"🔍 DEBUG: Restored {len(st.session_state.calendar.events)} events to calendar")
    else:
        print("🔍 DEBUG: No saved events found in database")

if 'events_data' not in st.session_state:
    st.session_state.events_data = []

if 'preferences' not in st.session_state or not isinstance(st.session_state.preferences, BookingPreferences):
    # Try to load from database
    saved_preferences = db_adapter.load_preferences(BookingPreferences)
    if saved_preferences:
        st.session_state.preferences = saved_preferences
        print("🔍 DEBUG: Loaded preferences from database")
    else:
        st.session_state.preferences = BookingPreferences()
        # Save default preferences
        db_adapter.save_preferences(st.session_state.preferences)

if 'calendar_refresh_key' not in st.session_state:
    st.session_state.calendar_refresh_key = 0


def get_status_value(status):
    """Safely get status value, handling both enum and string types."""
    if hasattr(status, 'value'):
        return status.value
    return str(status) if status else "unknown"


def refresh_calendar():
    """Update events data and force calendar refresh - ensures UI is synced with calendar object."""
    # Always sync from calendar object to UI
    update_events_data()
    # Increment refresh key to force calendar component to re-render
    st.session_state.calendar_refresh_key = st.session_state.get('calendar_refresh_key', 0) + 1


def update_events_data():
    """Update the events data for the calendar component from the calendar object."""
    # Ensure we have a valid calendar object
    if 'calendar' not in st.session_state:
        st.session_state.events_data = []
        print("🔍 DEBUG: update_events_data() - No calendar in session state")
        return
    
    if not isinstance(st.session_state.calendar, Calendar):
        st.session_state.events_data = []
        print(f"🔍 DEBUG: update_events_data() - Calendar is wrong type: {type(st.session_state.calendar)}")
        return
    
    calendar = st.session_state.calendar
    
    # Get all events from the calendar object
    events = []
    all_calendar_events = calendar.get_all_events()
    print(f"🔍 DEBUG: update_events_data() - Found {len(all_calendar_events)} events in calendar object")
    print(f"🔍 DEBUG: update_events_data() - Calendar.events dict has {len(calendar.events)} items")
    
    # Debug: Log how many events we're processing
    if len(all_calendar_events) > 0:
        st.session_state._debug_event_count = len(all_calendar_events)
    
    # Convert calendar events to UI format
    for event in all_calendar_events:
        # Parse duration to get end time
        duration_str = event.duration.lower().strip()
        if duration_str.endswith('m'):
            minutes = int(duration_str[:-1])
        elif duration_str.endswith('h'):
            minutes = int(duration_str[:-1]) * 60
        else:
            minutes = int(duration_str)
        
        end_time = event.time + timedelta(minutes=minutes)
        
        # Determine color based on status
        color_map = {
            "proposed": "#9E9E9E",  # Gray
            "accepted": "#2196F3",  # Blue
            "rejected": "#F44336",  # Red
            "confirmed": "#4CAF50",  # Green
            "booked": "#2E7D32",  # Dark Green
            "failed": "#D32F2F",  # Dark Red
            "no_show": "#FF5722",  # Deep Orange
        }
        
        status_value = get_status_value(event.status)
        status_key = status_value.lower() if status_value else "proposed"
        event_data = {
            "title": f"{event.partner_agent_id} ({status_value})",
            "start": event.time.isoformat(),
            "end": end_time.isoformat(),
            "color": color_map.get(status_key, "#757575"),
            "extendedProps": {
                "event_id": event.event_id,
                "partner": event.partner_agent_id,
                "status": status_value,
                "duration": event.duration
            }
        }
        events.append(event_data)
        print(f"🔍 DEBUG: Added event to UI data: {event.event_id} - {event.partner_agent_id} at {event.time.isoformat()}")
    
    # Update session state with synchronized events
    st.session_state.events_data = events
    print(f"🔍 DEBUG: update_events_data() - Total events prepared for UI: {len(events)}")
    print(f"🔍 DEBUG: Events data structure: {[e.get('title', 'No title') for e in events]}")
    
    # Verify sync: Check that counts match
    calendar_event_count = len(calendar.events)
    ui_event_count = len(events)
    
    # Debug: Store counts for debugging
    st.session_state._debug_calendar_events_count = calendar_event_count
    st.session_state._debug_ui_events_count = ui_event_count
    
    # Warn if there's a mismatch
    if calendar_event_count != ui_event_count:
        st.session_state._sync_warning = f"⚠️ Sync mismatch: Calendar has {calendar_event_count} events, UI has {ui_event_count}"
    else:
        st.session_state._sync_warning = None


def booking_page():
    """Booking page accessible via /book route."""
    st.title("📅 Book a Meeting")
    
    # Ensure calendar is properly initialized
    if 'calendar' not in st.session_state or not isinstance(st.session_state.calendar, Calendar):
        st.session_state.calendar = Calendar(owner_agent_id="agent-alpha")
    
    if 'preferences' not in st.session_state or not isinstance(st.session_state.preferences, BookingPreferences):
        st.session_state.preferences = BookingPreferences()
    
    st.markdown("---")
    
    # Booking form
    with st.form("booking_form"):
        st.subheader("Meeting Details")
        
        partner_id = st.text_input(
            "Your Agent ID *",
            placeholder="agent-beta-42",
            help="Your unique agent identifier"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            event_date = st.date_input(
                "Preferred Date *",
                value=datetime.now().date(),
                min_value=datetime.now().date()
            )
        with col2:
            event_time = st.time_input(
                "Preferred Time *",
                value=datetime.now().time()
            )
        
        duration = st.selectbox(
            "Meeting Duration *",
            options=["15m", "30m", "45m", "1h", "1.5h", "2h"],
            index=1,
            help="Select the duration for the meeting"
        )
        
        message = st.text_area(
            "Optional Message",
            placeholder="Any additional information about the meeting...",
            help="Optional message to include with the booking request"
        )
        
        submitted = st.form_submit_button("📅 Request Meeting", type="primary", use_container_width=True)
        
        if submitted:
            if not partner_id:
                st.error("❌ Please enter your Agent ID")
            else:
                try:
                    event_datetime = datetime.combine(event_date, event_time)
                    
                    # Check preferences before proposing
                    prefs = st.session_state.preferences
                    matches_prefs = prefs.is_preferred_time(event_datetime)
                    
                    # Create the event
                    event = st.session_state.calendar.propose_event(
                        time=event_datetime,
                        duration=duration,
                        partner_agent_id=partner_id
                    )
                    
                    st.success("✅ Meeting request submitted!")
                    
                    # Refresh calendar to show new event
                    refresh_calendar()
                    
                    # Save to database
                    db_adapter.save_event(event)
                    print(f"🔍 DEBUG: Saved event {event.event_id} from booking page to database")
                    
                    # Display event details
                    st.info(f"""
                    **Event ID:** `{event.event_id}`  
                    **Time:** {event_datetime.strftime('%Y-%m-%d %H:%M')}  
                    **Duration:** {duration}  
                    **Status:** {get_status_value(event.status)}
                    
                    Your meeting request has been sent. You'll receive a confirmation once it's accepted.
                    """)
                    
                    if not matches_prefs:
                        st.warning(f"⚠️ Note: This time may not match the agent's preferred schedule ({prefs.preferred_start_hour}:00-{prefs.preferred_end_hour}:00 on {', '.join(prefs.preferred_days)})")
                    
                    # Link to view calendar
                    st.markdown("---")
                    if st.button("📅 View Calendar", use_container_width=True):
                        st.query_params.clear()
                        st.rerun()
                    
                except ValueError as e:
                    st.error(f"❌ Error: {str(e)}")
    
    st.markdown("---")
    if st.button("← Back to Dashboard", use_container_width=True):
        st.query_params.clear()
        st.rerun()


def main():
    # Display MCP server status and URL
    if st.session_state.get('mcp_server_started', False):
        mcp_url = st.session_state.get('mcp_server_url', 'Unknown')
        st.sidebar.success("🟢 MCP Server Running", icon="📡")
        
        # Show MCP server URL in an expander
        with st.sidebar.expander("📡 MCP Server Info", expanded=False):
            st.write("**Server URL:**")
            st.code(mcp_url, language=None)
            if st.button("📋 Copy URL", key="copy_mcp_url"):
                st.write("💾 URL copied to clipboard!")
    else:
        st.sidebar.info("⚪ MCP Server Not Started", icon="📡")
    
    # Check if this is a booking page request
    query_params = st.query_params
    
    # Handle /book route
    if 'book' in query_params or query_params.get('page') == 'book':
        booking_page()
        return
    
    st.title("📅 Calendar Agent Dashboard")
    
    # Ensure calendar is properly initialized (in case session state was reset)
    # IMPORTANT: Only create new calendar if it doesn't exist, preserve existing one
    calendar_initialized = False
    if 'calendar' not in st.session_state:
        st.session_state.calendar = Calendar(owner_agent_id="agent-alpha")
        calendar_initialized = True
    elif not isinstance(st.session_state.calendar, Calendar):
        # Calendar exists but wrong type - try to preserve events
        existing_events = {}
        try:
            if hasattr(st.session_state.calendar, 'events'):
                existing_events = dict(st.session_state.calendar.events)  # Make a copy
        except:
            pass
        
        # Create new calendar
        st.session_state.calendar = Calendar(owner_agent_id="agent-alpha")
        
        # Restore events if any were preserved
        if existing_events:
            for event_id, event in existing_events.items():
                try:
                    st.session_state.calendar.events[event_id] = event
                except:
                    pass
        calendar_initialized = True
    
    # Sync UI with calendar object after initialization check
    if calendar_initialized or not hasattr(st.session_state, 'events_data') or len(st.session_state.get('events_data', [])) != len(st.session_state.calendar.get_all_events()):
        update_events_data()
    
    if 'preferences' not in st.session_state or not isinstance(st.session_state.preferences, BookingPreferences):
        st.session_state.preferences = BookingPreferences()
    
    # Add prominent booking banner at top
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.info("📅 Need to schedule a meeting? Use the booking page or sidebar button!")
    with col2:
        if st.button("📅 Book Meeting", use_container_width=True, type="primary"):
            st.query_params["book"] = "1"
            st.rerun()
    with col3:
        # Display booking link
        with st.expander("🔗 Share Booking Link"):
            booking_url = "/?book=1"
            st.code(booking_url, language="text")
            st.caption("Share this link to allow others to book meetings with you")
    
    st.markdown("---")
    
    # Sidebar for adding/removing events
    with st.sidebar:
        # Booking link button
        if st.button("📅 Book a Meeting", use_container_width=True, type="primary"):
            st.query_params["book"] = "1"
            st.rerun()
        
        st.markdown("---")
        st.header("⚙️ Booking Preferences")
        
        # Preferences Form
        with st.expander("📋 Set Preferences", expanded=False):
            with st.form("preferences_form"):
                st.subheader("Time Preferences")
                
                col1, col2 = st.columns(2)
                with col1:
                    start_hour = st.number_input(
                        "Preferred Start Hour",
                        min_value=0,
                        max_value=23,
                        value=st.session_state.preferences.preferred_start_hour,
                        help="24-hour format (0-23)"
                    )
                with col2:
                    end_hour = st.number_input(
                        "Preferred End Hour",
                        min_value=0,
                        max_value=23,
                        value=st.session_state.preferences.preferred_end_hour,
                        help="24-hour format (0-23)"
                    )
                
                preferred_days = st.multiselect(
                    "Preferred Days",
                    options=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                    default=st.session_state.preferences.preferred_days
                )
                
                st.subheader("Duration Preferences")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    preferred_duration = st.selectbox(
                        "Preferred Duration",
                        options=["15m", "30m", "45m", "1h", "1.5h", "2h"],
                        index=["15m", "30m", "45m", "1h", "1.5h", "2h"].index(
                            st.session_state.preferences.preferred_duration
                        ) if st.session_state.preferences.preferred_duration in ["15m", "30m", "45m", "1h", "1.5h", "2h"] else 1
                    )
                with col2:
                    min_duration = st.selectbox(
                        "Min Duration",
                        options=["15m", "30m", "45m", "1h"],
                        index=["15m", "30m", "45m", "1h"].index(
                            st.session_state.preferences.min_duration
                        ) if st.session_state.preferences.min_duration in ["15m", "30m", "45m", "1h"] else 0
                    )
                with col3:
                    max_duration = st.selectbox(
                        "Max Duration",
                        options=["30m", "45m", "1h", "1.5h", "2h", "3h"],
                        index=["30m", "45m", "1h", "1.5h", "2h", "3h"].index(
                            st.session_state.preferences.max_duration
                        ) if st.session_state.preferences.max_duration in ["30m", "45m", "1h", "1.5h", "2h", "3h"] else 4
                    )
                
                st.subheader("Scheduling Constraints")
                
                buffer_time = st.number_input(
                    "Buffer Between Meetings (minutes)",
                    min_value=0,
                    max_value=60,
                    value=st.session_state.preferences.buffer_between_meetings,
                    step=5
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    max_per_day = st.number_input(
                        "Max Meetings/Day",
                        min_value=1,
                        max_value=20,
                        value=st.session_state.preferences.max_meetings_per_day
                    )
                with col2:
                    max_per_week = st.number_input(
                        "Max Meetings/Week",
                        min_value=1,
                        max_value=50,
                        value=st.session_state.preferences.max_meetings_per_week
                    )
                
                allow_back_to_back = st.checkbox(
                    "Allow Back-to-Back Meetings",
                    value=st.session_state.preferences.allow_back_to_back
                )
                
                st.subheader("Auto-Acceptance")
                
                auto_accept = st.checkbox(
                    "Auto-Accept Preferred Times",
                    value=st.session_state.preferences.auto_accept_preferred_times,
                    help="Automatically accept meetings that match your preferred times"
                )
                
                require_confirm = st.checkbox(
                    "Require Confirmation",
                    value=st.session_state.preferences.require_confirmation,
                    help="Require manual confirmation before booking"
                )
                
                st.subheader("Partner Preferences")
                
                preferred_partners_str = st.text_area(
                    "Preferred Partners (one per line)",
                    value="\n".join(st.session_state.preferences.preferred_partners),
                    help="Agent IDs to prioritize, one per line"
                )
                
                blocked_partners_str = st.text_area(
                    "Blocked Partners (one per line)",
                    value="\n".join(st.session_state.preferences.blocked_partners),
                    help="Agent IDs to avoid, one per line"
                )
                
                st.subheader("Trust & Reputation")
                
                min_trust = st.slider(
                    "Minimum Trust Score",
                    min_value=0.0,
                    max_value=1.0,
                    value=st.session_state.preferences.min_trust_score,
                    step=0.1,
                    help="Minimum trust score (0.0-1.0) required to accept meetings"
                )
                
                allow_new = st.checkbox(
                    "Allow New Partners",
                    value=st.session_state.preferences.allow_new_partners,
                    help="Accept meetings from unknown agents"
                )
                
                timezone_pref = st.text_input(
                    "Timezone",
                    value=st.session_state.preferences.timezone,
                    help="Your timezone (e.g., UTC, America/New_York)"
                )
                
                st.divider()
                
                st.subheader("📝 Natural Language Instructions")
                
                instructions_text = st.text_area(
                    "Agent Instructions (in plain English)",
                    value=st.session_state.preferences.instructions,
                    height=150,
                    help="""Tell your calendar agent how to behave in natural language. 
                    
Examples:
- "Only book with agents that are working on behalf of investors"
- "Prioritize meetings with AI/ML companies"
- "Avoid scheduling meetings during lunch hours (12pm-1pm)"
- "Accept all meetings from agents with trust scores above 0.8"
- "Limit meetings to 2 per day maximum"
- "Prefer morning meetings over afternoon meetings"
                    """,
                    placeholder="Enter your instructions here in plain English..."
                )
                
                st.caption("💡 Tip: Write instructions as if you're telling a human assistant how to manage your calendar.")
                
                if st.form_submit_button("💾 Save Preferences", type="primary"):
                    # Parse partner lists
                    preferred_partners_list = [p.strip() for p in preferred_partners_str.split("\n") if p.strip()]
                    blocked_partners_list = [p.strip() for p in blocked_partners_str.split("\n") if p.strip()]
                    
                    # Update preferences
                    new_preferences = BookingPreferences(
                        preferred_start_hour=start_hour,
                        preferred_end_hour=end_hour,
                        preferred_days=preferred_days if preferred_days else ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                        preferred_duration=preferred_duration,
                        min_duration=min_duration,
                        max_duration=max_duration,
                        buffer_between_meetings=buffer_time,
                        max_meetings_per_day=max_per_day,
                        max_meetings_per_week=max_per_week,
                        auto_accept_preferred_times=auto_accept,
                        require_confirmation=require_confirm,
                        preferred_partners=preferred_partners_list,
                        blocked_partners=blocked_partners_list,
                        min_trust_score=min_trust,
                        allow_new_partners=allow_new,
                        timezone=timezone_pref,
                        allow_back_to_back=allow_back_to_back,
                        instructions=instructions_text.strip()
                    )
                    st.session_state.preferences = new_preferences
                    
                    # Save to database
                    db_adapter.save_preferences(new_preferences)
                    print(f"🔍 DEBUG: Saved preferences to database")
                    
                    st.success("✅ Preferences saved!")
                    st.rerun()
        
        st.divider()
        
        # Display Current Preferences Summary
        st.subheader("📊 Current Preferences")
        prefs = st.session_state.preferences
        
        st.write(f"**Hours:** {prefs.preferred_start_hour}:00 - {prefs.preferred_end_hour}:00")
        st.write(f"**Days:** {', '.join(prefs.preferred_days)}")
        st.write(f"**Duration:** {prefs.preferred_duration} (min: {prefs.min_duration}, max: {prefs.max_duration})")
        st.write(f"**Buffer:** {prefs.buffer_between_meetings} min")
        st.write(f"**Limits:** {prefs.max_meetings_per_day}/day, {prefs.max_meetings_per_week}/week")
        
        if prefs.preferred_partners:
            st.write(f"**Preferred Partners:** {len(prefs.preferred_partners)}")
        if prefs.blocked_partners:
            st.write(f"**Blocked Partners:** {len(prefs.blocked_partners)}")
        
        st.write(f"**Min Trust Score:** {prefs.min_trust_score:.1f}")
        st.write(f"**Auto-Accept:** {'✅' if prefs.auto_accept_preferred_times else '❌'}")
        st.write(f"**Allow New Partners:** {'✅' if prefs.allow_new_partners else '❌'}")
        
        if prefs.instructions:
            st.markdown("---")
            st.subheader("📝 Instructions")
            st.info(prefs.instructions)
        else:
            st.caption("💡 No instructions set. Add natural language instructions in the preferences form.")
        
        st.divider()
        
        st.header("Manage Events")
        
        # Debug: Show event count and calendar state - always sync first
        update_events_data()  # Ensure UI is synced with calendar object
        total_events = len(st.session_state.calendar.get_all_events())
        calendar_events_dict_size = len(st.session_state.calendar.events) if hasattr(st.session_state.calendar, 'events') else 0
        ui_events_count = len(st.session_state.events_data) if 'events_data' in st.session_state else 0
        sync_indicator = "✅" if total_events == ui_events_count else "⚠️"
        st.caption(f"{sync_indicator} Calendar: {total_events} events (dict: {calendar_events_dict_size}) | UI: {ui_events_count} events")
        
        # Debug: Show if calendar is proper type
        is_calendar = isinstance(st.session_state.calendar, Calendar)
        if not is_calendar:
            st.error(f"⚠️ Calendar type issue: {type(st.session_state.calendar)}")
        
        # Show calendar ID for tracking
        if hasattr(st.session_state.calendar, 'owner_agent_id'):
            st.caption(f"📋 Calendar Owner: {st.session_state.calendar.owner_agent_id}")
        
        # Add Event Form
        st.subheader("➕ Add New Event")
        with st.form("add_event_form"):
            partner_id = st.text_input("Partner Agent ID", placeholder="agent-beta-42")
            
            col1, col2 = st.columns(2)
            with col1:
                event_date = st.date_input("Date", value=datetime.now().date())
            with col2:
                event_time = st.time_input("Time", value=datetime.now().time())
            
            duration = st.selectbox(
                "Duration",
                options=["15m", "30m", "45m", "1h", "1.5h", "2h"],
                index=1
            )
            
            initial_status = st.selectbox(
                "Initial Status",
                options=["proposed", "accepted", "confirmed"],
                index=0
            )
            
            submitted = st.form_submit_button("Add Event", type="primary")
            
            if submitted:
                if partner_id:
                    try:
                        event_datetime = datetime.combine(event_date, event_time)
                        
                        # Check preferences before adding
                        temp_event = Event(
                            time=event_datetime,
                            duration=duration,
                            partner_agent_id=partner_id,
                            status=EventStatus.PROPOSED
                        )
                        
                        # Validate against preferences
                        prefs = st.session_state.preferences
                        matches_prefs = prefs.is_preferred_time(event_datetime)
                        
                        if not matches_prefs:
                            st.warning(f"⚠️ This time may not match your preferences ({prefs.preferred_start_hour}:00-{prefs.preferred_end_hour}:00 on {', '.join(prefs.preferred_days)})")
                        
                        if partner_id in prefs.blocked_partners:
                            st.error("❌ This partner is in your blocked list!")
                            st.stop()
                        
                        # Ensure we're working with the actual calendar instance
                        calendar = st.session_state.calendar
                        if not isinstance(calendar, Calendar):
                            st.error(f"❌ Calendar is not correct type: {type(calendar)}")
                            st.stop()
                        
                        # Create event based on initial status
                        if initial_status == "proposed":
                            event = calendar.propose_event(
                                time=event_datetime,
                                duration=duration,
                                partner_agent_id=partner_id
                            )
                        else:
                            event = Event(
                                time=event_datetime,
                                duration=duration,
                                partner_agent_id=partner_id,
                                status=EventStatus[initial_status.upper()]
                            )
                            calendar.add_event(event)
                        
                        # Immediately verify the event is stored in the calendar's events dict
                        if event and event.event_id:
                            # Verify event is in calendar BEFORE storing back to session state
                            events_before = len(calendar.events)
                            event_stored = event.event_id in calendar.events
                            
                            if not event_stored:
                                # Force add to dict if add_event didn't work
                                calendar.events[event.event_id] = event
                                event_stored = True
                                st.warning("⚠️ Event was manually added to calendar dict")
                            
                            if event_stored:
                                # CRITICAL: Store calendar back to session state and verify
                                # Make sure we're modifying the actual session state calendar
                                st.session_state.calendar = calendar
                                
                                # Verify it persisted
                                verify_calendar = st.session_state.calendar
                                if not isinstance(verify_calendar, Calendar):
                                    st.error(f"❌ Calendar type changed after storage: {type(verify_calendar)}")
                                    st.stop()
                                
                                if event.event_id not in verify_calendar.events:
                                    st.error(f"❌ Calendar not persisting! Event {event.event_id} missing after storage.")
                                    st.error(f"   Calendar has {len(verify_calendar.events)} events")
                                    st.error(f"   Event IDs in calendar: {list(verify_calendar.events.keys())[:5]}")
                                    st.stop()
                                
                                # Success - show message
                                all_events_count = len(verify_calendar.get_all_events())
                                success_msg = f"✅ Event added: {event.event_id} (Total events: {all_events_count})"
                                if matches_prefs:
                                    success_msg += " (matches preferences)"
                                st.success(success_msg)
                                
                                # DEBUG: Print calendar state before refresh
                                print(f"\n🔍 DEBUG: BEFORE refresh_calendar() - Event {event.event_id} added")
                                print(f"🔍 DEBUG: Calendar.events keys: {list(verify_calendar.events.keys())}")
                                print(f"🔍 DEBUG: Calendar.get_all_events() count: {all_events_count}")
                                
                                # Force calendar refresh
                                refresh_calendar()
                                
                                # Save to database
                                db_adapter.save_event(event)
                                print(f"🔍 DEBUG: Saved event {event.event_id} to database")
                                
                                # DEBUG: Print calendar state after refresh
                                print(f"🔍 DEBUG: AFTER refresh_calendar() - UI events_data count: {len(st.session_state.events_data)}")
                                print(f"🔍 DEBUG: UI events_data: {[e.get('title', 'No title') for e in st.session_state.events_data]}")
                                print(f"🔍 DEBUG: Calendar being rendered with {len(st.session_state.events_data)} events\n")
                                
                                # Rerun to show updated calendar
                                st.rerun()
                            else:
                                st.error(f"❌ Event {event.event_id} could not be stored! Dict had {events_before} events. Calendar type: {type(calendar)}")
                        else:
                            st.error("❌ Failed to add event - event object is invalid")
                    except ValueError as e:
                        st.error(f"❌ Error: {str(e)}")
                else:
                    st.warning("⚠️ Please enter a Partner Agent ID")
        
        st.divider()
        
        # Remove Event Section
        st.subheader("🗑️ Remove Event")
        
        # Get all events for selection
        all_events = st.session_state.calendar.get_all_events()
        if all_events:
            event_options = {
                f"{e.event_id} - {e.partner_agent_id} ({get_status_value(e.status)})": e.event_id
                for e in sorted(all_events, key=lambda x: x.time, reverse=True)
            }
            
            selected_event_key = st.selectbox(
                "Select Event to Remove",
                options=list(event_options.keys()),
                index=0
            )
            
            if st.button("Remove Event", type="secondary"):
                event_id = event_options[selected_event_key]
                if st.session_state.calendar.remove_event(event_id):
                    # Save to database
                    db_adapter.delete_event(event_id)
                    print(f"🔍 DEBUG: Deleted event {event_id} from database")
                    st.success(f"✅ Event {event_id} removed")
                    refresh_calendar()
                    st.rerun()
                else:
                    st.error("❌ Failed to remove event")
        else:
            st.info("No events to remove")
        
        st.divider()
        
        # Statistics
        st.subheader("📊 Statistics")
        counts = st.session_state.calendar.count_by_status()
        for status, count in counts.items():
            st.metric(label=status.replace("_", " ").title(), value=count)
        
        total = sum(counts.values())
        st.metric(label="Total Events", value=total)
    
    # Main calendar view
    st.subheader("Calendar View")
    
    # Calendar configuration
    calendar_options = {
        "editable": True,
        "selectable": True,
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay,listWeek"
        },
        "initialView": "dayGridMonth",
        "height": "600px",
    }
    
    # CRITICAL: Always sync calendar UI with calendar object before displaying
    # This ensures the UI reflects the current state of the calendar
    update_events_data()
    
    # Show sync status
    calendar_event_count = st.session_state._debug_calendar_events_count if '_debug_calendar_events_count' in st.session_state else 0
    ui_event_count = st.session_state._debug_ui_events_count if '_debug_ui_events_count' in st.session_state else 0
    
    if st.session_state.get('_sync_warning'):
        st.warning(st.session_state._sync_warning)
    
    # Use refresh key to force calendar update
    calendar_key = f"calendar_{st.session_state.get('calendar_refresh_key', 0)}"
    
    # Show sync status (only if there's a mismatch or events exist)
    events_count = len(st.session_state.events_data)
    if calendar_event_count > 0 or ui_event_count > 0:
        sync_status = "✅" if calendar_event_count == ui_event_count else "⚠️"
        if calendar_event_count != ui_event_count:
            # Only show warning if there's a mismatch
            st.warning(f"{sync_status} Sync mismatch detected: Calendar has {calendar_event_count} events, UI has {ui_event_count} events")
        elif events_count > 0:
            # Only show status if events exist and are synced
            st.caption(f"{sync_status} {events_count} event(s) loaded and synced")
        
        # Debug expander (collapsed by default) for troubleshooting
        with st.expander("🔍 Debug: View Events & Sync Status", expanded=False):
            st.write("**Calendar Object Status:**")
            st.write(f"- Calendar events dict size: {len(st.session_state.calendar.events)}")
            st.write(f"- Calendar get_all_events() count: {calendar_event_count}")
            st.write(f"- UI events_data count: {ui_event_count}")
            st.write(f"- Rendering: {events_count} events")
            st.write(f"- Sync status: {'✅ Synced' if calendar_event_count == ui_event_count else '⚠️ Mismatch'}")
            st.write("\n**Events JSON:**")
            if st.session_state.events_data:
                st.json(st.session_state.events_data)
            else:
                st.info("No events data available")
    
    # DEBUG: Print what we're about to render
    print(f"\n🔍 DEBUG: Rendering calendar with {len(st.session_state.events_data)} events")
    print(f"🔍 DEBUG: Calendar key: {calendar_key}")
    print(f"🔍 DEBUG: Events being rendered:")
    for idx, event_data in enumerate(st.session_state.events_data):
        print(f"  [{idx+1}] {event_data.get('title', 'No title')} - Start: {event_data.get('start', 'N/A')}, End: {event_data.get('end', 'N/A')}")
    
    # Display calendar
    calendar_result = st_calendar(
        events=st.session_state.events_data,
        options=calendar_options,
        custom_css="""
        .fc-event-past {
            opacity: 0.8;
        }
        .fc-event-time {
            font-style: italic;
        }
        .fc-event-title {
            font-weight: 700;
        }
        .fc-toolbar-title {
            font-size: 2rem;
        }
        """,
        key=calendar_key
    )
    
    print(f"🔍 DEBUG: Calendar component rendered, result type: {type(calendar_result)}")
    
    # calendar_result is a dict containing interaction data when events are clicked
    # This is normal behavior - no action needed unless there's an error
    
    # Display event details when clicked
    if calendar_result and isinstance(calendar_result, dict):
        st.divider()
        st.subheader("Event Details")
        
        if 'eventClick' in calendar_result and isinstance(calendar_result.get('eventClick'), dict):
            event_info = calendar_result['eventClick'].get('event', {})
            event_id = event_info.get('extendedProps', {}).get('event_id')
            
            if event_id:
                event = st.session_state.calendar.get_event(event_id)
                if event:
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write("**Event ID:**")
                        st.code(event.event_id)
                    
                    with col2:
                        st.write("**Partner:**")
                        st.write(event.partner_agent_id)
                    
                    with col3:
                        st.write("**Status:**")
                        st.write(get_status_value(event.status))
                    
                    st.write("**Time:**", event.time.strftime("%Y-%m-%d %H:%M"))
                    st.write("**Duration:**", event.duration)
                    st.write("**Created:**", event.created_at.strftime("%Y-%m-%d %H:%M:%S"))
                    
                    # Status update buttons
                    st.write("**Update Status:**")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        if st.button("Accept", key=f"accept_{event_id}"):
                            updated_event = st.session_state.calendar.accept_event(event_id)
                            if updated_event:
                                db_adapter.save_event(updated_event)
                                st.success("Event accepted")
                                refresh_calendar()
                                st.rerun()
                    
                    with col2:
                        if st.button("Confirm", key=f"confirm_{event_id}"):
                            updated_event = st.session_state.calendar.confirm_event(event_id)
                            if updated_event:
                                db_adapter.save_event(updated_event)
                                st.success("Event confirmed")
                                refresh_calendar()
                                st.rerun()
                    
                    with col3:
                        if st.button("Mark Booked", key=f"booked_{event_id}"):
                            updated_event = st.session_state.calendar.mark_booked(event_id)
                            if updated_event:
                                db_adapter.save_event(updated_event)
                                st.success("Event marked as booked")
                                refresh_calendar()
                                st.rerun()
                    
                    with col4:
                        if st.button("Mark Failed", key=f"failed_{event_id}"):
                            updated_event = st.session_state.calendar.mark_failed(event_id)
                            if updated_event:
                                db_adapter.save_event(updated_event)
                                st.success("Event marked as failed")
                                refresh_calendar()
                                st.rerun()
    
    # Events list view
    st.divider()
    st.subheader("Events List")
    
    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        filter_status = st.selectbox(
            "Filter by Status",
            options=["All"] + [status.value for status in EventStatus],
            index=0
        )
    
    with col2:
        sort_by = st.selectbox(
            "Sort by",
            options=["Time (Newest)", "Time (Oldest)", "Status", "Partner"],
            index=0
        )
    
    # Get filtered events
    if filter_status == "All":
        display_events = st.session_state.calendar.get_all_events()
    else:
        display_events = st.session_state.calendar.get_events_by_status(
            EventStatus[filter_status.upper()]
        )
    
    # Sort events
    if sort_by == "Time (Newest)":
        display_events.sort(key=lambda x: x.time, reverse=True)
    elif sort_by == "Time (Oldest)":
        display_events.sort(key=lambda x: x.time)
    elif sort_by == "Status":
        display_events.sort(key=lambda x: get_status_value(x.status))
    elif sort_by == "Partner":
        display_events.sort(key=lambda x: x.partner_agent_id)
    
    # Display events table
    if display_events:
        for event in display_events:
            with st.expander(
                f"{event.time.strftime('%Y-%m-%d %H:%M')} - {event.partner_agent_id} ({get_status_value(event.status)})"
            ):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**Event ID:** `{event.event_id}`")
                    st.write(f"**Partner:** {event.partner_agent_id}")
                    st.write(f"**Duration:** {event.duration}")
                    st.write(f"**Created:** {event.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                with col2:
                    if st.button("Remove", key=f"remove_{event.event_id}"):
                        if st.session_state.calendar.remove_event(event.event_id):
                            db_adapter.delete_event(event.event_id)
                            st.success("Event removed")
                            refresh_calendar()
                            st.rerun()
    else:
        st.info("No events found. Add an event using the sidebar form.")


# Initialize MCP server in background thread (only once per Streamlit session)
if 'mcp_server_started' not in st.session_state:
    try:
        # Default MCP server configuration
        MCP_HOST = "localhost"
        MCP_PORT = 8000
        MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}/sse"
        
        def run_server():
            try:
                server_module.run_mcp_server(host=MCP_HOST, port=MCP_PORT)
            except Exception as e:
                print(f"⚠️ MCP Server error: {e}")
        
        mcp_thread = threading.Thread(target=run_server, daemon=True)
        mcp_thread.start()
        st.session_state.mcp_server_started = True
        st.session_state.mcp_server_url = MCP_URL
        print(f"🚀 MCP Server started in background thread at {MCP_URL}")
    except Exception as e:
        print(f"⚠️ Failed to start MCP server: {e}")
        st.session_state.mcp_server_started = False
        st.session_state.mcp_server_url = None

if __name__ == "__main__":
    main()

