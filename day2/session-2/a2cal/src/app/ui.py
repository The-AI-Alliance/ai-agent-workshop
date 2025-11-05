"""Streamlit UI for Calendar Agent."""
import streamlit as st
from datetime import datetime, timedelta
from streamlit_calendar import calendar as st_calendar
import sys
import os
import importlib.util
import io
import urllib.parse

# Use web-based QR code generation (no dependencies needed)
QRCODE_AVAILABLE = True

# Add src directory to path for imports
src_dir = os.path.dirname(os.path.dirname(__file__))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Import calendar module from services/calendar-service/calendar_api.py
calendar_api_path = os.path.join(src_dir, "services", "calendar-service", "calendar_api.py")
calendar_spec = importlib.util.spec_from_file_location("calendar_api", calendar_api_path)
calendar_module = importlib.util.module_from_spec(calendar_spec)
calendar_spec.loader.exec_module(calendar_module)

Calendar = calendar_module.Calendar
Event = calendar_module.Event
EventStatus = calendar_module.EventStatus
BookingPreferences = calendar_module.BookingPreferences

# Import database adapter from services/calendar-service/db_adapter.py
db_adapter_path = os.path.join(src_dir, "services", "calendar-service", "db_adapter.py")
db_spec = importlib.util.spec_from_file_location("db_adapter", db_adapter_path)
db_adapter_module = importlib.util.module_from_spec(db_spec)
db_spec.loader.exec_module(db_adapter_module)

CalendarDBAdapter = db_adapter_module.CalendarDBAdapter

# Page config
st.set_page_config(
    page_title="Calendar Agent",
    page_icon="📅",
    layout="wide"
)


def get_admin_credentials():
    """Get admin credentials from environment variables with defaults.
    
    Returns:
        tuple: (username, password) from env vars or defaults
    """
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin123")
    return username, password


def is_authenticated() -> bool:
    """Check if the current user is authenticated (logged in).
    
    Returns:
        True if user is logged in, False otherwise
    """
    return st.session_state.get('is_authenticated', False)


def login_page():
    """Display login form for admin access."""
    st.title("🔐 Admin Login")
    st.markdown("Please enter your credentials to access the admin dashboard.")
    
    username_default, password_default = get_admin_credentials()
    
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="Enter username")
        password = st.text_input("Password", type="password", placeholder="Enter password")
        
        submitted = st.form_submit_button("🔓 Login", type="primary", use_container_width=True)
        
        if submitted:
            admin_username, admin_password = get_admin_credentials()
            
            if username == admin_username and password == admin_password:
                st.session_state.is_authenticated = True
                st.success("✅ Login successful! Redirecting...")
                st.rerun()
            else:
                st.error("❌ Invalid username or password")
    
    st.markdown("---")
    st.info("💡 Default credentials: username=`admin`, password=`admin123`")
    st.info("💡 Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables to change defaults.")
    
    # Link to booking page for public access
    st.markdown("---")
    st.markdown("**Public Access:**")
    if st.button("📅 Book a Meeting (Public)", use_container_width=True):
        st.query_params["book"] = "1"
        st.rerun()

# Initialize database adapter
DB_PATH = "calendar_agent.db"
db_adapter = CalendarDBAdapter(db_path=DB_PATH)

# Initialize session state - ensure calendar persists across reloads
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
else:
    # Calendar exists - ensure it has all events from database (reload on each page load to sync)
    # This ensures any changes made via MCP/A2A are reflected in the UI
    saved_events = db_adapter.load_all_events(Event, EventStatus)
    if saved_events:
        # Update calendar with events from database (merge, don't replace)
        for event in saved_events:
            # Ensure status is properly set
            if isinstance(event.status, str) and hasattr(EventStatus, event.status.upper()):
                try:
                    event.status = EventStatus[event.status.upper()]
                except:
                    pass
            # Add or update event in calendar
            st.session_state.calendar.events[event.event_id] = event
        print(f"🔍 DEBUG: Synced {len(saved_events)} events from database to existing calendar")

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
    
    # Ensure calendar is properly initialized - load from database if needed
    if 'calendar' not in st.session_state or not isinstance(st.session_state.calendar, Calendar):
        # Load from database
        saved_events = db_adapter.load_all_events(Event, EventStatus)
        st.session_state.calendar = Calendar(owner_agent_id="agent-alpha")
        
        # Restore events from database
        if saved_events:
            for event in saved_events:
                if isinstance(event.status, str) and hasattr(EventStatus, event.status.upper()):
                    try:
                        event.status = EventStatus[event.status.upper()]
                    except:
                        pass
                st.session_state.calendar.events[event.event_id] = event
    
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
                    
                except ValueError as e:
                    st.error(f"❌ Error: {str(e)}")
    
    # Buttons must be outside the form context
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📅 View Calendar", use_container_width=True):
            st.query_params.clear()
            st.rerun()
    with col2:
        if st.button("← Back to Dashboard", use_container_width=True):
            st.query_params.clear()
            st.rerun()


def agentfacts_page():
    """Streamlit UI page for configuring AgentFacts."""
    from common.agentfacts import load_agentfacts, save_agentfacts
    
    st.title("📋 AgentFacts Configuration")
    st.markdown("Configure your agent's metadata and capabilities.")
    
    # Get current agent DID
    agent_did = st.session_state.get('agent_did')
    if not agent_did:
        try:
            # Try to import Agent class (from external package or local module)
            try:
                from agent import Agent
            except ImportError:
                # Try alternative import paths
                try:
                    sys.path.insert(0, os.path.dirname(src_dir))
                    from agent import Agent
                except ImportError:
                    st.error("⚠️ Agent class not found. Please ensure the agent module is available.")
                    return
            
            agent = Agent(name="Calendar Agent", host="localhost", a2a_port=8000, mcp_port=8000)
            agent_did = agent.get_did()
            st.session_state.agent_did = agent_did
        except Exception as e:
            st.error(f"Could not load agent DID: {e}")
            return
    
    # Load current agent facts
    facts = load_agentfacts()
    
    # Update agent_id with DID if not set or different
    if facts.get("core_identity", {}).get("agent_id") != agent_did:
        facts.setdefault("core_identity", {})["agent_id"] = agent_did
    
    # Core Identity Section
    st.header("🔐 Core Identity")
    with st.expander("Core Identity", expanded=True):
        facts["core_identity"]["agent_id"] = st.text_input(
            "Agent ID (DID)",
            value=facts.get("core_identity", {}).get("agent_id", agent_did),
            disabled=True,
            help="This is your agent's DID and cannot be changed"
        )
        facts["core_identity"]["name"] = st.text_input(
            "Agent Name",
            value=facts.get("core_identity", {}).get("name", "Calendar Agent")
        )
        facts["core_identity"]["version"] = st.text_input(
            "Version",
            value=facts.get("core_identity", {}).get("version", "1.0.0")
        )
        facts["core_identity"]["ttl"] = st.number_input(
            "TTL (seconds)",
            value=facts.get("core_identity", {}).get("ttl", 3600),
            min_value=60
        )
    
    # Baseline Model Section
    st.header("🤖 Baseline Model")
    with st.expander("Baseline Model", expanded=False):
        baseline = facts.setdefault("baseline_model", {})
        baseline["foundation_model"] = st.text_input(
            "Foundation Model",
            value=baseline.get("foundation_model", "GPT-4")
        )
        baseline["model_version"] = st.text_input(
            "Model Version",
            value=baseline.get("model_version", "gpt-4")
        )
        baseline["model_provider"] = st.text_input(
            "Model Provider",
            value=baseline.get("model_provider", "OpenAI")
        )
        
        training_sources = baseline.get("training_data_sources", [])
        if st.button("Add Training Data Source", key="add_training"):
            training_sources.append("")
        for i, source in enumerate(training_sources):
            training_sources[i] = st.text_input(
                f"Training Data Source {i+1}",
                value=source,
                key=f"training_{i}"
            )
        baseline["training_data_sources"] = [s for s in training_sources if s]
    
    # Classification Section
    st.header("📊 Classification")
    with st.expander("Classification", expanded=False):
        classification = facts.setdefault("classification", {})
        classification["agent_type"] = st.selectbox(
            "Agent Type",
            ["assistant", "autonomous", "tool", "workflow"],
            index=["assistant", "autonomous", "tool", "workflow"].index(classification.get("agent_type", "assistant"))
        )
        classification["operational_level"] = st.selectbox(
            "Operational Level",
            ["ambient", "supervised", "autonomous"],
            index=["ambient", "supervised", "autonomous"].index(classification.get("operational_level", "supervised"))
        )
        classification["stakeholder_context"] = st.selectbox(
            "Stakeholder Context",
            ["enterprise", "consumer", "government"],
            index=["enterprise", "consumer", "government"].index(classification.get("stakeholder_context", "consumer"))
        )
        classification["deployment_scope"] = st.selectbox(
            "Deployment Scope",
            ["internal", "external", "hybrid"],
            index=["internal", "external", "hybrid"].index(classification.get("deployment_scope", "external"))
        )
        classification["interaction_mode"] = st.selectbox(
            "Interaction Mode",
            ["synchronous", "asynchronous", "batch"],
            index=["synchronous", "asynchronous", "batch"].index(classification.get("interaction_mode", "synchronous"))
        )
    
    # Capabilities Section
    st.header("⚡ Capabilities")
    with st.expander("Capabilities", expanded=False):
        capabilities = facts.setdefault("capabilities", {})
        
        tool_calling = capabilities.get("tool_calling", ["MCP", "function_calls"])
        tool_calling_str = st.text_input(
            "Tool Calling (comma-separated)",
            value=", ".join(tool_calling)
        )
        capabilities["tool_calling"] = [t.strip() for t in tool_calling_str.split(",") if t.strip()]
        
        interface_types = capabilities.get("interface_types", ["REST API", "MCP"])
        interface_str = st.text_input(
            "Interface Types (comma-separated)",
            value=", ".join(interface_types)
        )
        capabilities["interface_types"] = [i.strip() for i in interface_str.split(",") if i.strip()]
        
        domain_expertise = capabilities.get("domain_expertise", ["calendar", "scheduling"])
        domain_str = st.text_input(
            "Domain Expertise (comma-separated)",
            value=", ".join(domain_expertise)
        )
        capabilities["domain_expertise"] = [d.strip() for d in domain_str.split(",") if d.strip()]
    
    # Save button
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("💾 Save AgentFacts", type="primary", use_container_width=True):
            if save_agentfacts(facts):
                st.success("✅ AgentFacts saved successfully!")
                st.rerun()
            else:
                st.error("❌ Failed to save AgentFacts")
    
    with col2:
        if st.button("🔙 Back to Dashboard", use_container_width=True):
            st.query_params.clear()
            st.rerun()
    
    # Preview section
    st.header("👁️ Preview")
    with st.expander("Preview AgentFacts JSON", expanded=False):
        st.json(facts)
    
    # Show endpoint info
    st.info(f"📡 AgentFacts will be available at: `http://localhost:8000/.well-known/agentfacts.json`")


def main():
    # Display Agent DID
    if 'agent_did' not in st.session_state:
        try:
            # Try to import Agent class (from external package or local module)
            try:
                from agent import Agent
            except ImportError:
                # Try alternative import paths
                try:
                    sys.path.insert(0, os.path.dirname(src_dir))
                    from agent import Agent
                except ImportError:
                    print("⚠️ Agent class not found. Please ensure the agent module is available.")
                    Agent = None
            
            if Agent:
                # Initialize agent if not already done
                agent = Agent(name="Calendar Agent", host="localhost", a2a_port=8000, mcp_port=8000)
                st.session_state.agent_did = agent.get_did()
            else:
                st.session_state.agent_did = None
        except Exception as e:
            st.session_state.agent_did = None
    
    if st.session_state.get('agent_did'):
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🔐 Agent Identity")
        with st.sidebar.expander("📋 DID Peer", expanded=True):
            st.write("**Decentralized Identifier:**")
            st.code(st.session_state.agent_did, language=None)
            if st.button("📋 Copy DID", key="copy_did"):
                st.write("💾 DID copied to clipboard!")
        
        # Add AgentFacts link
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 📋 AgentFacts")
        if st.sidebar.button("📋 Configure AgentFacts", key="configure_agentfacts", use_container_width=True):
            st.query_params["page"] = "agentfacts"
            st.rerun()
        
        # Show AgentFacts endpoint
        agentfacts_url = f"http://localhost:8000/.well-known/agentfacts.json"
        with st.sidebar.expander("🔗 AgentFacts Endpoint", expanded=False):
            st.write("**Endpoint URL:**")
            st.code(agentfacts_url, language=None)
            if st.button("📋 Copy URL", key="copy_agentfacts_url"):
                st.write("💾 URL copied to clipboard!")
            if st.button("🔗 Open AgentFacts", key="open_agentfacts"):
                st.markdown(f"[View AgentFacts]({agentfacts_url})")
    
    # Display MCP server status and URL
    if st.session_state.get('mcp_server_started', False):
        # Get MCP URL from session state (already set with ngrok URL from main.py)
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
    
    # Display A2A server status and URL
    if st.session_state.get('a2a_server_started', False):
        # Get A2A URL from session state (already set with ngrok URL from main.py)
        a2a_url = st.session_state.get('a2a_server_url', 'Unknown')
        st.sidebar.success("🟢 A2A Server Running", icon="🤝")
        
        # Show A2A server URL in an expander
        with st.sidebar.expander("🤝 A2A Server Info", expanded=False):
            st.write("**Base URL:**")
            st.code(a2a_url, language=None)
            st.write("**Protocol:** Agent2Agent (A2A)")
            st.write("**Tools:** requestAvailableSlots, requestBooking, deleteBooking")
            st.write("**A2A Endpoint:**")
            # A2A endpoint is at /a2a/ (with trailing slash)
            a2a_endpoint = f"{a2a_url}/a2a/" if not a2a_url.endswith("/a2a/") else a2a_url
            st.code(a2a_endpoint, language=None)
            if st.button("📋 Copy URL", key="copy_a2a_url"):
                st.write("💾 URL copied to clipboard!")
    else:
        st.sidebar.info("⚪ A2A Server Not Started", icon="🤝")
    
    # Add logout button in sidebar for authenticated users
    if is_authenticated():
        st.sidebar.markdown("---")
        st.sidebar.success("✅ Logged in as Admin", icon="👤")
        if st.sidebar.button("🚪 Logout", use_container_width=True):
            st.query_params["page"] = "logout"
            st.rerun()
    
    # Check if this is a booking page request (public access)
    query_params = st.query_params
    
    # Handle /book route (public access - no authentication required)
    if 'book' in query_params or query_params.get('page') == 'book':
        booking_page()
        return
    
    # Handle logout
    if query_params.get('page') == 'logout':
        st.session_state.is_authenticated = False
        st.session_state.pop('is_admin', None)
        st.success("👋 Logged out successfully")
        st.query_params.clear()
        st.rerun()
    
    # Check authentication for admin pages
    if not is_authenticated():
        login_page()
        return
    
    # Handle /agentfacts route (admin only - requires authentication)
    if query_params.get('page') == 'agentfacts':
        agentfacts_page()
        return
    
    # Home/Dashboard page - Admin only (requires authentication)
    # User is authenticated, show dashboard
    
    st.title("📅 Calendar Agent Dashboard")
    
    # Add AgentFacts quick access button at the top
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown("")  # Spacing
    with col2:
        if st.button("📋 Configure AgentFacts", key="top_configure_agentfacts", use_container_width=True):
            st.query_params["page"] = "agentfacts"
            st.rerun()
    with col3:
        agentfacts_url = f"http://localhost:8000/.well-known/agentfacts.json"
        if st.button("🔗 View AgentFacts JSON", key="view_agentfacts_json", use_container_width=True):
            st.query_params["view_agentfacts"] = "true"
            st.rerun()
    
    # Show AgentFacts JSON if requested
    if st.query_params.get("view_agentfacts") == "true":
        try:
            from common.agentfacts import load_agentfacts
            facts = load_agentfacts()
            with st.expander("📋 AgentFacts JSON", expanded=True):
                st.json(facts)
                if st.button("❌ Close", key="close_agentfacts"):
                    st.query_params.clear()
                    st.rerun()
        except Exception as e:
            st.error(f"Could not load AgentFacts: {e}")
    
    # Ensure calendar is properly initialized and synced with database
    # The calendar should already be initialized at the top level, but ensure it's synced
    if 'calendar' not in st.session_state or not isinstance(st.session_state.calendar, Calendar):
        # Calendar was somehow lost - reload from database
        saved_events = db_adapter.load_all_events(Event, EventStatus)
        st.session_state.calendar = Calendar(owner_agent_id="agent-alpha")
        
        # Restore events from database
        if saved_events:
            for event in saved_events:
                if isinstance(event.status, str) and hasattr(EventStatus, event.status.upper()):
                    try:
                        event.status = EventStatus[event.status.upper()]
                    except:
                        pass
                st.session_state.calendar.events[event.event_id] = event
            print(f"🔍 DEBUG: Dashboard - Reloaded {len(saved_events)} events from database")
    else:
        # Calendar exists - sync with database to ensure we have latest events
        # This ensures any changes made via MCP/A2A are reflected
        saved_events = db_adapter.load_all_events(Event, EventStatus)
        if saved_events:
            # Merge database events into calendar (don't replace, merge)
            for event in saved_events:
                if isinstance(event.status, str) and hasattr(EventStatus, event.status.upper()):
                    try:
                        event.status = EventStatus[event.status.upper()]
                    except:
                        pass
                # Add or update event (preserves any in-memory changes)
                st.session_state.calendar.events[event.event_id] = event
    
    # Sync UI with calendar object
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
        # Display booking link with ngrok URL and QR code
        with st.expander("🔗 Share Booking Link", expanded=True):
            # Get Streamlit ngrok URL (default port 8501)
            if 'streamlit_ngrok_url' not in st.session_state:
                try:
                    from pyngrok import ngrok
                    # Get Streamlit's default port (8501)
                    streamlit_port = 8501
                    
                    # Check if ngrok is available and configured
                    try:
                        # Try to get existing tunnels first
                        tunnels = ngrok.get_tunnels()
                        existing_tunnel = None
                        for tunnel in tunnels:
                            # Tunnel config addr can be in various formats
                            tunnel_addr = str(tunnel.config.get('addr', '')).strip()
                            port_str = str(streamlit_port)
                            if (tunnel_addr == f'localhost:{streamlit_port}' or 
                                tunnel_addr == f'127.0.0.1:{streamlit_port}' or 
                                tunnel_addr == port_str or 
                                tunnel_addr.endswith(f':{streamlit_port}') or
                                tunnel_addr == f':{streamlit_port}'):
                                existing_tunnel = tunnel
                                print(f"🔍 Found existing tunnel for Streamlit port {streamlit_port}: {tunnel.public_url}")
                                break
                        
                        if existing_tunnel:
                            streamlit_ngrok_url = existing_tunnel.public_url.rstrip('/')
                        else:
                            # Create new ngrok tunnel for Streamlit
                            tunnel = ngrok.connect(streamlit_port, "http")
                            streamlit_ngrok_url = tunnel.public_url.rstrip('/')
                        
                        st.session_state.streamlit_ngrok_url = streamlit_ngrok_url
                        print(f"✅ Created/Found ngrok tunnel for Streamlit: {streamlit_ngrok_url}")
                    except Exception as ngrok_error:
                        print(f"⚠️  ngrok error: {ngrok_error}")
                        # Fallback to localhost if ngrok not available
                        streamlit_ngrok_url = f"http://localhost:8501"
                        st.session_state.streamlit_ngrok_url = streamlit_ngrok_url
                        st.warning("⚠️ ngrok not available - using localhost URL")
                except ImportError:
                    # Fallback to localhost if pyngrok not installed
                    streamlit_ngrok_url = f"http://localhost:8501"
                    st.session_state.streamlit_ngrok_url = streamlit_ngrok_url
                    st.warning("⚠️ pyngrok not installed - install with: pip install pyngrok")
            else:
                streamlit_ngrok_url = st.session_state.streamlit_ngrok_url
            
            # Create full booking URL
            booking_url = f"{streamlit_ngrok_url}/?book=1"
            
            # Display the URL
            st.markdown("**Booking URL:**")
            st.code(booking_url, language="text")
            
            # Button to show/hide QR code
            if QRCODE_AVAILABLE:
                if st.button("📱 Show QR Code", key="show_qr_code", use_container_width=True):
                    st.session_state.show_booking_qr = True
                    st.rerun()
            
            # Display QR code if button was clicked
            if st.session_state.get('show_booking_qr', False) and QRCODE_AVAILABLE:
                try:
                    # Use web-based QR code generator (no dependencies needed)
                    # Using qr-server.com API
                    encoded_url = urllib.parse.quote(booking_url)
                    qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded_url}"
                    
                    st.image(qr_code_url, caption="📱 Scan to book a meeting", use_container_width=True)
                    if st.button("❌ Hide QR Code", key="hide_qr_code", use_container_width=True):
                        st.session_state.show_booking_qr = False
                        st.rerun()
                except Exception as e:
                    st.warning(f"Could not generate QR code: {e}")
                    st.error(f"Error details: {str(e)}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📋 Copy URL", key="copy_booking_url", use_container_width=True):
                    st.write("💾 URL copied to clipboard!")
            with col2:
                if st.button("🔄 Refresh ngrok URL", key="refresh_ngrok", use_container_width=True):
                    if 'streamlit_ngrok_url' in st.session_state:
                        del st.session_state.streamlit_ngrok_url
                    st.rerun()
            
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
                    current_status = get_status_value(event.status)
                    
                    # Show different buttons based on current status
                    if current_status.lower() == "proposed":
                        # For proposed events, show Accept and Reject prominently
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if st.button("✅ Accept", key=f"accept_{event_id}", type="primary", use_container_width=True):
                                updated_event = st.session_state.calendar.accept_event(event_id)
                                if updated_event:
                                    db_adapter.save_event(updated_event)
                                    st.success("✅ Event accepted")
                                    refresh_calendar()
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to accept event. Make sure the event is in PROPOSED status.")
                        
                        with col2:
                            if st.button("❌ Reject", key=f"reject_{event_id}", type="secondary", use_container_width=True):
                                updated_event = st.session_state.calendar.reject_event(event_id)
                                if updated_event:
                                    db_adapter.save_event(updated_event)
                                    st.success("❌ Event rejected")
                                    refresh_calendar()
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to reject event. Make sure the event is in PROPOSED status.")
                        
                        # Also show other actions in a separate row
                        st.caption("Other actions:")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            if st.button("Confirm", key=f"confirm_{event_id}"):
                                updated_event = st.session_state.calendar.confirm_event(event_id)
                                if updated_event:
                                    db_adapter.save_event(updated_event)
                                    st.success("Event confirmed")
                                    refresh_calendar()
                                    st.rerun()
                        
                        with col2:
                            if st.button("Mark Booked", key=f"booked_{event_id}"):
                                updated_event = st.session_state.calendar.mark_booked(event_id)
                                if updated_event:
                                    db_adapter.save_event(updated_event)
                                    st.success("Event marked as booked")
                                    refresh_calendar()
                                    st.rerun()
                        
                        with col3:
                            if st.button("Mark Failed", key=f"failed_{event_id}"):
                                updated_event = st.session_state.calendar.mark_failed(event_id)
                                if updated_event:
                                    db_adapter.save_event(updated_event)
                                    st.success("Event marked as failed")
                                    refresh_calendar()
                                    st.rerun()
                    
                    elif current_status.lower() == "accepted":
                        # For accepted events, show Confirm prominently, and allow Accept again or Reject
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            if st.button("✅ Confirm", key=f"confirm_{event_id}", type="primary", use_container_width=True):
                                updated_event = st.session_state.calendar.confirm_event(event_id)
                                if updated_event:
                                    db_adapter.save_event(updated_event)
                                    st.success("✅ Event confirmed")
                                    refresh_calendar()
                                    st.rerun()
                        
                        with col2:
                            if st.button("Accept", key=f"accept_{event_id}"):
                                updated_event = st.session_state.calendar.accept_event(event_id)
                                if updated_event:
                                    db_adapter.save_event(updated_event)
                                    st.success("Event accepted")
                                    refresh_calendar()
                                    st.rerun()
                        
                        with col3:
                            if st.button("❌ Reject", key=f"reject_{event_id}", type="secondary"):
                                # For accepted events, we can't reject directly, but we could mark as failed
                                st.info("Cannot reject an accepted event. Use 'Mark Failed' instead.")
                    
                    else:
                        # For other statuses, show all available actions
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
            event_status = get_status_value(event.status)
            with st.expander(
                f"{event.time.strftime('%Y-%m-%d %H:%M')} - {event.partner_agent_id} ({event_status})"
            ):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**Event ID:** `{event.event_id}`")
                    st.write(f"**Partner:** {event.partner_agent_id}")
                    st.write(f"**Status:** {event_status}")
                    st.write(f"**Duration:** {event.duration}")
                    st.write(f"**Created:** {event.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    # Status update buttons - especially useful for proposed events
                    if event_status.lower() == "proposed":
                        st.write("**Quick Actions:**")
                        col_accept, col_reject = st.columns(2)
                        with col_accept:
                            if st.button("✅ Accept", key=f"list_accept_{event.event_id}", type="primary", use_container_width=True):
                                updated_event = st.session_state.calendar.accept_event(event.event_id)
                                if updated_event:
                                    db_adapter.save_event(updated_event)
                                    st.success("✅ Event accepted")
                                    refresh_calendar()
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to accept event")
                        with col_reject:
                            if st.button("❌ Reject", key=f"list_reject_{event.event_id}", type="secondary", use_container_width=True):
                                updated_event = st.session_state.calendar.reject_event(event.event_id)
                                if updated_event:
                                    db_adapter.save_event(updated_event)
                                    st.success("❌ Event rejected")
                                    refresh_calendar()
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to reject event")
                
                with col2:
                    if st.button("🗑️ Remove", key=f"remove_{event.event_id}", use_container_width=True):
                        if st.session_state.calendar.remove_event(event.event_id):
                            db_adapter.delete_event(event.event_id)
                            st.success("Event removed")
                            refresh_calendar()
                            st.rerun()
    else:
        st.info("No events found. Add an event using the sidebar form.")

