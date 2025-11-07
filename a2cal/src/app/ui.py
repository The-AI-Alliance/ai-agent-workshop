"""Streamlit UI for Calendar Agent."""
import json
import os
import sys
import traceback
import urllib.parse
from pathlib import Path
from datetime import datetime, timedelta

import streamlit as st
from streamlit_calendar import calendar as st_calendar
import importlib.util
import io

# Module-level debug print to confirm file is loaded
print("\n" + "="*80)
print("[UI.PY] ✅ MODULE LOADED - ui.py is being imported!")
print("="*80 + "\n")

# Try to import optional dependencies
try:
    from pyngrok import ngrok
    NGROK_AVAILABLE = True
except ImportError:
    NGROK_AVAILABLE = False
    ngrok = None

# Import common modules
from common.agentfacts import load_agentfacts, save_agentfacts
from common.base_agent import Agent
from common.server_state import get_server_state

# Import DID resolution
try:
    from common.did_peer_2 import resolve
    DID_RESOLVE_AVAILABLE = True
except ImportError:
    DID_RESOLVE_AVAILABLE = False
    resolve = None

# Import MCP client
try:
    from mmcp.client import init_session_from_url, send_message
    MCP_CLIENT_AVAILABLE = True
except ImportError:
    MCP_CLIENT_AVAILABLE = False
    init_session_from_url = None
    send_message = None

# Import A2A client
try:
    import sys
    import logging
    _ui_logger = logging.getLogger(__name__)
    _ui_logger.debug(f"Attempting to import A2A client from Python: {sys.executable}")
    _ui_logger.debug(f"Python path (first 3): {sys.path[:3]}")
    
    from a2a_client.client import send_message_to_a2a_agent, A2A_SDK_AVAILABLE
    A2A_CLIENT_AVAILABLE = A2A_SDK_AVAILABLE
    
    if A2A_CLIENT_AVAILABLE:
        _ui_logger.info("✅ A2A client imported successfully and SDK is available")
    else:
        _ui_logger.warning("⚠️ A2A client module imported but SDK is not available")
        from a2a_client.client import _import_error
        _ui_logger.warning(f"   Import error: {_import_error}")
except ImportError as e:
    A2A_CLIENT_AVAILABLE = False
    send_message_to_a2a_agent = None
    _ui_logger.error(f"❌ Failed to import A2A client module: {e}")
    _ui_logger.error(f"   Python executable: {sys.executable}")
    import traceback
    _ui_logger.debug(f"   Full traceback:\n{traceback.format_exc()}")
except Exception as e:
    A2A_CLIENT_AVAILABLE = False
    send_message_to_a2a_agent = None
    _ui_logger.error(f"❌ Unexpected error importing A2A client: {e}")
    import traceback
    _ui_logger.debug(f"   Full traceback:\n{traceback.format_exc()}")

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
    
    # Booking Links section
    st.markdown("---")
    st.subheader("🔗 Share Meeting Link")
    st.markdown("Share this link to allow others to book meetings with you.")
    
    # Display booking link with ngrok URL and QR code
    # Get Streamlit ngrok URL (default port 8501)
    if 'streamlit_ngrok_url' not in st.session_state:
        streamlit_port = 8501
        
        if NGROK_AVAILABLE and ngrok:
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
        else:
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
    
    # Copy and refresh buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋 Copy URL", key="copy_booking_url", use_container_width=True):
            st.success("💾 URL copied to clipboard!")
    with col2:
        if st.button("🔄 Refresh ngrok URL", key="refresh_ngrok", use_container_width=True):
            if 'streamlit_ngrok_url' in st.session_state:
                del st.session_state.streamlit_ngrok_url
            st.rerun()
    
    # QR Code section
    st.markdown("---")
    if QRCODE_AVAILABLE:
        if st.button("📱 Show QR Code", key="show_qr_code", use_container_width=True):
            st.session_state.show_booking_qr = True
            st.rerun()
        
        # Display QR code if button was clicked
        if st.session_state.get('show_booking_qr', False):
            try:
                # Use web-based QR code generator (no dependencies needed)
                # Using qr-server.com API
                encoded_url = urllib.parse.quote(booking_url)
                # TODO : fix dependencies
                qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded_url}"
                
                st.image(qr_code_url, caption="📱 Scan to book a meeting", use_container_width=True)
                if st.button("❌ Hide QR Code", key="hide_qr_code", use_container_width=True):
                    st.session_state.show_booking_qr = False
                    st.rerun()
            except Exception as e:
                st.warning(f"Could not generate QR code: {e}")
                st.error(f"Error details: {str(e)}")
    
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


def agents_page():
    """Streamlit UI page for viewing all agents and their agent cards."""
    st.title("🤖 Agents")
    st.markdown("View all available agents and their capabilities.")
    
    # Get agent cards directory
    agent_cards_dir = Path(__file__).parent.parent / "agent_cards"
    
    if not agent_cards_dir.exists():
        st.error(f"❌ Agent cards directory not found: {agent_cards_dir}")
        return
    
    # Find all agent card JSON files
    agent_card_files = list(agent_cards_dir.glob("*.json"))
    
    if not agent_card_files:
        st.warning("⚠️ No agent cards found in the agent_cards directory.")
        return
    
    st.markdown(f"**Found {len(agent_card_files)} agent(s)**")
    st.markdown("---")
    
    # Display each agent
    for idx, agent_card_file in enumerate(agent_card_files, 1):
        try:
            with agent_card_file.open('r', encoding='utf-8') as f:
                agent_card = json.load(f)
            
            # Agent header
            agent_name = agent_card.get('name', 'Unknown Agent')
            agent_description = agent_card.get('description', 'No description available.')
            agent_version = agent_card.get('version', 'Unknown')
            agent_url = agent_card.get('url', 'N/A')
            
            # Try to get agent DID from server state
            agent_did = None
            try:
                server_state = get_server_state()
                agents = server_state.get('agents', {})
                # Find DID by matching agent name
                for did, agent_info in agents.items():
                    if agent_info.get('name') == agent_name:
                        agent_did = did
                        break
            except Exception:
                pass
            
            # Create columns for agent info
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.markdown(f"### {idx}. {agent_name}")
                st.markdown(f"**Description:** {agent_description}")
                if agent_did:
                    st.markdown(f"**DID:** `{agent_did}`")
            
            with col2:
                st.markdown(f"**Version:** `{agent_version}`")
                if agent_url and agent_url != 'N/A':
                    st.markdown(f"**URL:** `{agent_url}`")
            
            # Capabilities
            capabilities = agent_card.get('capabilities', {})
            if capabilities:
                st.markdown("**Capabilities:**")
                cap_cols = st.columns(len(capabilities))
                for cap_idx, (cap_key, cap_value) in enumerate(capabilities.items()):
                    with cap_cols[cap_idx]:
                        status = "✅" if cap_value else "❌"
                        st.markdown(f"{status} **{cap_key}:** {cap_value}")
            
            # Skills section
            skills = agent_card.get('skills', [])
            if skills:
                st.markdown("**Skills:**")
                for skill in skills:
                    skill_name = skill.get('name', 'Unknown Skill')
                    skill_desc = skill.get('description', 'No description')
                    skill_tags = skill.get('tags', [])
                    skill_examples = skill.get('examples', [])
                    
                    with st.expander(f"🔧 {skill_name}", expanded=False):
                        st.markdown(f"**Description:** {skill_desc}")
                        
                        if skill_tags:
                            st.markdown("**Tags:**")
                            tag_str = ", ".join([f"`{tag}`" for tag in skill_tags])
                            st.markdown(tag_str)
                        
                        if skill_examples:
                            st.markdown("**Examples:**")
                            for example in skill_examples:
                                st.markdown(f"- {example}")
            
            # Tools section
            tools = agent_card.get('tools', [])
            if tools:
                st.markdown("**Tools:**")
                tool_desc = {tool.get('name', 'Unknown'): tool.get('description', 'No description') 
                            for tool in tools}
                
                # Display tools in a compact format (show up to 9 tools)
                tools_to_show = tools[:9]
                tool_cols = st.columns(min(3, len(tools_to_show)))
                for tool_idx, tool in enumerate(tools_to_show):
                    tool_name = tool.get('name', 'Unknown')
                    with tool_cols[tool_idx % 3]:
                        with st.expander(f"🔨 {tool_name}", expanded=False):
                            st.markdown(tool_desc.get(tool_name, 'No description'))
                
                if len(tools) > 9:
                    st.info(f"💡 Showing {min(9, len(tools))} of {len(tools)} tools. See full agent card for complete list.")
            
            # Input/Output modes
            input_modes = agent_card.get('defaultInputModes', [])
            output_modes = agent_card.get('defaultOutputModes', [])
            
            if input_modes or output_modes:
                io_col1, io_col2 = st.columns(2)
                with io_col1:
                    if input_modes:
                        st.markdown("**Input Modes:**")
                        st.markdown(", ".join([f"`{mode}`" for mode in input_modes]))
                with io_col2:
                    if output_modes:
                        st.markdown("**Output Modes:**")
                        st.markdown(", ".join([f"`{mode}`" for mode in output_modes]))
            
            # Full Agent Card JSON (expandable)
            with st.expander("📄 View Full Agent Card JSON", expanded=False):
                st.json(agent_card)
            
            # Instructions (if available)
            instructions = agent_card.get('instructions', '')
            if instructions:
                with st.expander("📝 View Instructions", expanded=False):
                    st.markdown(instructions)
            
            st.markdown("---")
            
        except json.JSONDecodeError as e:
            st.error(f"❌ Error parsing agent card {agent_card_file.name}: {e}")
            st.markdown("---")
        except Exception as e:
            st.error(f"❌ Error loading agent card {agent_card_file.name}: {e}")
            import traceback
            st.code(traceback.format_exc())
            st.markdown("---")


def use_agent_to_book_page():
    """Streamlit UI page for using an agent (via A2A or MCP) to book an invite."""
    st.title("🤝 Use Agent To Book Invite")
    st.markdown("Connect to an agent using their DID and book a meeting via A2A or MCP.")
    
    st.markdown("---")
    
    # DID Input Section
    st.subheader("🔐 Agent DID")
    col1, col2 = st.columns([3, 1])
    with col1:
        agent_did = st.text_input(
            "Agent Decentralized Identifier (DID)",
            placeholder="did:peer:2...",
            help="Enter the DID of the agent you want to connect to",
            key="agent_did_input",
            label_visibility="collapsed"
        )
    with col2:
        connect_button = st.button("🔗 Connect", key="connect_did", type="primary", use_container_width=True)
    
    if not agent_did:
        st.info("💡 Enter an agent DID to begin booking")
        st.markdown("---")
        st.markdown("**Example DID format:** `did:peer:2.Vz6MksKa...`")
        return
    
    # Validate DID format (basic check)
    if not agent_did.startswith("did:"):
        st.warning("⚠️ DID should start with 'did:'")
        return
    
    # Resolve DID and extract service endpoints when Connect button is clicked
    a2a_endpoint = None
    mcp_endpoint = None
    
    # Resolve DID when Connect button is clicked
    if connect_button:
        if DID_RESOLVE_AVAILABLE and resolve:
            try:
                with st.spinner("🔍 Resolving DID and extracting service endpoints..."):
                    did_doc = resolve(agent_did)
                    st.session_state.resolved_did = agent_did
                    
                    # Extract service endpoints from DID document
                    services = did_doc.get("service", [])
                    for service in services:
                        service_type = service.get("type", "")
                        service_endpoint = service.get("serviceEndpoint", "")
                        
                        if service_type == "A2A":
                            # Strip /agent/ or /agent from the endpoint if present
                            a2a_endpoint = service_endpoint.rstrip('/')
                            # Remove trailing /agent or /agent/
                            if a2a_endpoint.endswith('/agent'):
                                a2a_endpoint = a2a_endpoint[:-6]  # Remove '/agent'
                            # Ensure we have a clean base URL
                            a2a_endpoint = a2a_endpoint.rstrip('/')
                            st.session_state.a2a_endpoint = a2a_endpoint
                        elif service_type == "MCP":
                            mcp_endpoint = service_endpoint
                            st.session_state.mcp_endpoint = mcp_endpoint
                    
                    if a2a_endpoint or mcp_endpoint:
                        st.success("✅ DID resolved successfully!")
                    else:
                        st.warning("⚠️ DID resolved but no A2A or MCP service endpoints found")
            except Exception as e:
                st.error(f"❌ Error resolving DID: {e}")
                st.session_state.resolved_did = None
                st.session_state.a2a_endpoint = None
                st.session_state.mcp_endpoint = None
        else:
            st.error("❌ DID resolution not available. Please install required dependencies.")
    else:
        # Use cached endpoints if available and DID matches
        if 'a2a_endpoint' in st.session_state and st.session_state.get('resolved_did') == agent_did:
            a2a_endpoint = st.session_state.a2a_endpoint
        if 'mcp_endpoint' in st.session_state and st.session_state.get('resolved_did') == agent_did:
            mcp_endpoint = st.session_state.mcp_endpoint
    
    st.success(f"✅ Agent DID: `{agent_did}`")
    if a2a_endpoint:
        st.info(f"📡 A2A Endpoint: `{a2a_endpoint}`")
    if mcp_endpoint:
        st.info(f"💬 MCP Endpoint: `{mcp_endpoint}`")
    st.markdown("---")
    
    # Automatic Booking Section
    if a2a_endpoint:
        st.subheader("🤖 Automated AI Booking")
        st.markdown("""
        Let your **Calendar Booking Agent** use AI to intelligently negotiate with the target agent.
        The agent will use your preferences from the sidebar to find the best meeting time.
        """)
        
        # Show current preferences summary
        with st.expander("📋 Current Preferences (from sidebar)", expanded=False):
            prefs = st.session_state.preferences
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Time Preferences:**")
                st.write(f"- Hours: {prefs.preferred_start_hour}:00 - {prefs.preferred_end_hour}:00")
                st.write(f"- Days: {', '.join(prefs.preferred_days)}")
                
            with col2:
                st.markdown("**Duration:**")
                st.write(f"- Preferred: {prefs.preferred_duration}")
                st.write(f"- Range: {prefs.min_duration} - {prefs.max_duration}")
            
            st.markdown("**Constraints:**")
            st.write(f"- Buffer between meetings: {prefs.buffer_between_meetings} minutes")
            st.write(f"- Max meetings per day: {prefs.max_meetings_per_day}")
            
            st.info("💡 Update preferences in the sidebar to change booking behavior")
        
        # Optional: Meeting title and description
        with st.expander("📝 Meeting Details (Optional)", expanded=False):
            meeting_title = st.text_input(
                "Meeting Title",
                placeholder="e.g., Project Review",
                key="auto_booking_title"
            )
            meeting_description = st.text_area(
                "Meeting Description",
                placeholder="Optional description for the meeting",
                key="auto_booking_description",
                height=80
            )
        
        # Book Meeting button
        col1, col2, col3 = st.columns([2, 1, 2])
        with col2:
            if st.button("🤖 Let AI Book Meeting", type="primary", use_container_width=True, key="auto_book_button"):
                print("\n" + "="*80)
                print("[UI] 🚀 AUTOMATED BOOKING BUTTON CLICKED!")
                print("="*80)
                
                # Show visible feedback in UI
                st.success("✅ Button clicked! Starting automated booking...")
                st.write("🔍 **Debug**: Button handler is executing")
                
                # Initialize booking automation
                from a2a_client.booking_automation import BookingAutomation, MeetingPreferences
                print("[UI] ✓ Imported BookingAutomation and MeetingPreferences")
                st.write("✓ Imported booking modules")
                
                # Convert sidebar preferences to MeetingPreferences
                # Use natural language for the AI to interpret
                prefs = st.session_state.preferences
                print(f"[UI] ✓ Retrieved preferences: {prefs}")
                date_pref = f"within the next week, preferably on {', '.join(prefs.preferred_days)}"
                time_pref = f"between {prefs.preferred_start_hour}:00 and {prefs.preferred_end_hour}:00"
                
                # Parse duration (e.g., "1h" -> 60 minutes)
                duration_map = {"15m": 15, "30m": 30, "45m": 45, "1h": 60, "1.5h": 90, "2h": 120, "3h": 180}
                duration_minutes = duration_map.get(prefs.preferred_duration, 60)
                
                preferences = MeetingPreferences(
                    date=date_pref,
                    time=time_pref,
                    duration=duration_minutes,
                    title=meeting_title if meeting_title else "Meeting",
                    description=meeting_description if meeting_description else None,
                    partner_agent_id=agent_did
                )
                print(f"[UI] ✓ Created MeetingPreferences: {preferences}")
                
                # Create status container
                status_container = st.container()
                progress_bar = st.progress(0)
                status_text = st.empty()
                print("[UI] ✓ Created Streamlit UI elements (progress bar, status text)")
                
                # Progress callback
                async def update_progress(turn: int, status: str, message: str):
                    progress = turn / 5  # Max 5 turns
                    progress_bar.progress(min(progress, 1.0))
                    status_text.markdown(f"**Turn {turn}/5:** {message}")
                
                # Get or create booking agent
                print("[UI] Checking for existing booking agent...")
                if 'booking_agent' not in st.session_state or st.session_state.booking_agent is None:
                    print("[UI] No booking agent found, creating new one...")
                    from agents.calendar_booking_agent import CalendarBookingAgent
                    
                    status_text.markdown("**Creating booking agent...**")
                    print("[UI] Importing CalendarBookingAgent...")
                    
                    try:
                        print("[UI] Creating CalendarBookingAgent instance...")
                        st.session_state.booking_agent = CalendarBookingAgent(
                            agent_name="Calendar Booking Agent",
                            description="Intelligent agent that negotiates meeting bookings on your behalf",
                            instructions="""You are an intelligent booking agent that helps schedule meetings.
Your goal is to negotiate with other agents to find optimal meeting times based on user preferences.

When communicating with other agents:
1. Be professional and clear
2. Share relevant preferences (time, date, duration)
3. Ask for their availability
4. Negotiate to find mutually agreeable times
5. Confirm bookings once agreed upon

Always prioritize the user's preferences while being flexible to find workable solutions."""
                        )
                        print("[UI] ✅ CalendarBookingAgent instance created successfully")
                        status_text.markdown("**✅ Booking agent created**")
                    except Exception as e:
                        print(f"[UI] ❌ Failed to create booking agent: {e}")
                        st.error(f"❌ Failed to create booking agent: {str(e)}")
                        import traceback
                        print(f"[UI] Traceback: {traceback.format_exc()}")
                        with st.expander("🐛 Error Details"):
                            st.code(traceback.format_exc())
                        st.stop()
                else:
                    print("[UI] ✓ Using existing booking agent from session state")
                
                # Run booking automation with AI agent
                print(f"[UI] Creating BookingAutomation instance (max_turns=5)...")
                automation = BookingAutomation(max_turns=5)
                print(f"[UI] ✓ BookingAutomation instance created")
                
                try:
                    print(f"[UI] Setting up asyncio...")
                    import asyncio
                    import nest_asyncio
                    nest_asyncio.apply()
                    print(f"[UI] ✓ nest_asyncio applied")
                    
                    loop = asyncio.get_event_loop()
                    print(f"[UI] ✓ Got event loop: {loop}")
                    print(f"[UI] 🚀 Calling automation.book_meeting()...")
                    print(f"[UI]    - target_agent_endpoint: {a2a_endpoint}")
                    print(f"[UI]    - target_agent_did: {agent_did}")
                    print(f"[UI]    - preferences: {preferences}")
                    print(f"[UI] ⏳ Running async function with loop.run_until_complete()...")
                    
                    result = loop.run_until_complete(
                        automation.book_meeting(
                            target_agent_endpoint=a2a_endpoint,
                            target_agent_did=agent_did,
                            preferences=preferences,
                            booking_agent=st.session_state.booking_agent,
                            progress_callback=update_progress
                        )
                    )
                    print(f"[UI] ✅ automation.book_meeting() completed!")
                    print(f"[UI] Result: {result}")
                    
                    # Display result
                    progress_bar.progress(1.0)
                    
                    if result['success']:
                        st.success(f"✅ {result['message']}")
                        
                        if result.get('booking_details'):
                            st.json(result['booking_details'])
                    else:
                        st.error(f"❌ {result['message']}")
                    
                    # Show conversation summary
                    with st.expander("📜 Conversation History", expanded=False):
                        st.markdown(automation.get_conversation_summary())
                        
                        for turn in result.get('conversation_history', []):
                            st.markdown(f"### Turn {turn.turn_number}")
                            st.markdown(f"**Sent:** {turn.message_sent}")
                            st.markdown(f"**Received:** {turn.response_received}")
                            st.markdown("---")
                
                except Exception as e:
                    progress_bar.progress(0.0)
                    status_text.markdown("**❌ Error occurred**")
                    st.error(f"❌ Error during automated booking: {str(e)}")
                    
                    # Check for common issues
                    error_str = str(e).lower()
                    if 'timeout' in error_str:
                        st.warning("⚠️ **Tip:** The MCP server connection timed out. Make sure your MCP server is running and accessible.")
                    elif 'connection' in error_str or 'connect' in error_str:
                        st.warning("⚠️ **Tip:** Cannot connect to MCP server. Check the server status in the sidebar.")
                    elif 'a2a' in error_str:
                        st.warning("⚠️ **Tip:** A2A communication issue. Verify the target agent's endpoint is correct.")
                    
                    import traceback
                    with st.expander("🐛 Full Error Details"):
                        st.code(traceback.format_exc())
                    
                    # Show conversation history if any was captured
                    if automation.conversation_history:
                        with st.expander("📜 Conversation Before Error"):
                            for turn in automation.conversation_history:
                                st.markdown(f"### Turn {turn.turn_number}")
                                st.markdown(f"**Sent:** {turn.message_sent}")
                                st.markdown(f"**Received:** {turn.response_received}")
                                st.markdown("---")
        
        st.markdown("---")
    
    # Create tabs for Manual A2A and MCP
    tab_a2a, tab_mcp = st.tabs(["📡 Manual A2A Chat", "💬 MCP Chat"])
    
    # A2A Tab
    with tab_a2a:
        st.subheader("📡 Manual A2A Chat")
        st.markdown("Manually chat with the agent using A2A protocol to book a meeting through conversation.")
        
        # Display A2A endpoint if available
        if a2a_endpoint:
            st.info(f"**A2A Service Endpoint:** `{a2a_endpoint}`")
        else:
            st.warning("⚠️ A2A endpoint not found. Please resolve the DID first.")
        
        st.markdown("---")
        
        # Initialize chat history in session state
        if 'a2a_chat_history' not in st.session_state:
            st.session_state.a2a_chat_history = []
        
        # Display chat history
        st.subheader("💬 Chat")
        
        # Chat container
        chat_container = st.container()
        
        with chat_container:
            # Display chat messages
            for idx, message in enumerate(st.session_state.a2a_chat_history):
                if message.get('role') == 'user':
                    with st.chat_message("user"):
                        st.write(message.get('content', ''))
                elif message.get('role') == 'assistant':
                    with st.chat_message("assistant"):
                        st.write(message.get('content', ''))
        
        st.markdown("---")
        
        # Chat input - only enable if A2A endpoint is available
        chat_enabled_a2a = a2a_endpoint is not None and A2A_CLIENT_AVAILABLE
        
        # Debug info expander
        with st.expander("🔧 Debug Info", expanded=False):
            import sys
            import json
            import os
            
            st.subheader("System Info")
            st.code(f"""
Python executable: {sys.executable}
A2A_CLIENT_AVAILABLE: {A2A_CLIENT_AVAILABLE}
A2A endpoint: {a2a_endpoint}
Chat enabled: {chat_enabled_a2a}
            """.strip())
            
            if not A2A_CLIENT_AVAILABLE:
                try:
                    from a2a_client.client import _import_error, A2A_SDK_AVAILABLE
                    st.warning(f"A2A SDK Available: {A2A_SDK_AVAILABLE}")
                    if _import_error:
                        st.error(f"Import error: {_import_error}")
                        st.code(str(_import_error))
                except:
                    st.error("Could not retrieve import error details")
            
            # Show A2A Client Debug Info from JSON file
            st.markdown("---")
            st.subheader("A2A Client Debug Info")
            debug_file_path = "/tmp/a2a_client_debug.json"
            
            if os.path.exists(debug_file_path):
                try:
                    with open(debug_file_path, 'r') as f:
                        debug_data = json.load(f)
                    
                    st.success(f"✅ Last request to: `{debug_data.get('endpoint', 'N/A')}`")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Chunks Received", debug_data.get('chunks_received', 0))
                    with col2:
                        st.metric("Text Extracted", "✅ Yes" if debug_data.get('text_extracted') else "❌ No")
                    with col3:
                        st.metric("Text Length", debug_data.get('text_length', 0))
                    
                    st.markdown("**Message sent:**")
                    st.code(debug_data.get('message', 'N/A'))
                    
                    st.markdown("**Streaming:**")
                    st.code(f"Supports streaming: {debug_data.get('supports_streaming', False)}")
                    
                    # Show chunk summary
                    st.markdown("**Chunks received:**")
                    raw_chunks = debug_data.get('raw_chunks', [])
                    for i, chunk_info in enumerate(raw_chunks):
                        with st.expander(f"Chunk {i+1}: {chunk_info.get('type', 'Unknown')}", expanded=False):
                            st.json(chunk_info.get('data', {}))
                    
                    # Button to view full debug file
                    if st.button("📄 View Full Debug JSON"):
                        st.json(debug_data)
                        
                except Exception as e:
                    st.error(f"Failed to read debug file: {e}")
            else:
                st.info("No debug info available yet. Send a message to generate debug data.")
        
        if not chat_enabled_a2a:
            if not a2a_endpoint:
                st.warning("⚠️ A2A endpoint not available. Please resolve the DID first.")
            elif not A2A_CLIENT_AVAILABLE:
                st.warning("⚠️ A2A client not available. Please install required dependencies.")
                st.info("💡 Check the Debug Info expander above for details about the import error.")
        
        user_input_a2a = st.chat_input(
            "Type your message to the agent..." if chat_enabled_a2a else "Connect to agent first...",
            disabled=not chat_enabled_a2a,
            key="a2a_chat_input"
        )
        
        if user_input_a2a and chat_enabled_a2a:
            # Add user message to chat history
            st.session_state.a2a_chat_history.append({
                'role': 'user',
                'content': user_input_a2a
            })
            
            # Display user message immediately
            with st.chat_message("user"):
                st.write(user_input_a2a)
            
            # Send message via A2A client
            with st.chat_message("assistant"):
                with st.spinner("Connecting to agent..."):
                    try:
                        import asyncio
                        import nest_asyncio
                        
                        # Allow nested event loops (needed for Streamlit)
                        nest_asyncio.apply()
                        
                        # Run async A2A client call
                        async def get_response():
                            return await send_message_to_a2a_agent(
                                endpoint_url=a2a_endpoint,
                                message_text=user_input_a2a
                            )
                        
                        # Run the async function
                        loop = asyncio.get_event_loop()
                        response = loop.run_until_complete(get_response())
                        st.write(response)
                        
                        # Add assistant response to chat history
                        st.session_state.a2a_chat_history.append({
                            'role': 'assistant',
                            'content': response
                        })
                    except ExceptionGroup as eg:
                        # Handle ExceptionGroup (TaskGroup errors)
                        error_details = []
                        for exc in eg.exceptions:
                            error_details.append(str(exc))
                        error_msg = f"Connection error: {'; '.join(error_details)}"
                        st.error(error_msg)
                        st.exception(eg)  # Show full traceback in expander
                        st.session_state.a2a_chat_history.append({
                            'role': 'assistant',
                            'content': error_msg
                        })
                    except Exception as e:
                        # Extract more details from the error
                        error_msg = f"Error communicating with agent: {str(e)}"
                        error_type = type(e).__name__
                        
                        # Provide more helpful error messages
                        if "ImportError" in error_type or "a2a-sdk" in str(e).lower():
                            # Show detailed debug info for import errors
                            import sys
                            debug_info = f"""
**A2A SDK Import Error**

Python executable: `{sys.executable}`
Error: {str(e)}

**Troubleshooting:**
1. Make sure you're using the correct Python environment
2. Install a2a-sdk: `pip install 'a2a-sdk[http-server]'`
3. Restart Streamlit after installing
4. Check that Streamlit is using the same Python as your terminal
                            """
                            error_msg = debug_info
                        elif "ConnectError" in error_type or "connection" in str(e).lower():
                            error_msg = f"❌ Cannot connect to A2A server at `{a2a_endpoint}`. Please check:\n- The server is running\n- The URL is correct\n- Network connectivity"
                        elif "TaskGroup" in str(e):
                            error_msg = f"❌ Connection failed: {str(e)}\n\nThis usually means the A2A server is not accessible. Please verify the endpoint URL."
                        
                        st.error(error_msg)
                        with st.expander("🔍 Error Details", expanded=True):
                            st.exception(e)
                            # Show additional debug info
                            import sys
                            st.code(f"""
Python executable: {sys.executable}
A2A_CLIENT_AVAILABLE: {A2A_CLIENT_AVAILABLE}
Error type: {error_type}
                            """.strip())
                        st.session_state.a2a_chat_history.append({
                            'role': 'assistant',
                            'content': error_msg
                        })
            
            st.rerun()
        
        # Clear chat button
        if st.button("🗑️ Clear Chat", key="clear_a2a_chat"):
            st.session_state.a2a_chat_history = []
            st.rerun()
        
        st.markdown("---")
        if chat_enabled_a2a:
            st.info("💡 You can ask the agent about available time slots, pending requests, calendar events, or request bookings.")
        else:
            st.info("💡 Connect to an agent by resolving their DID to start chatting.")
    
    # MCP Tab
    with tab_mcp:
        st.subheader("💬 MCP Chat")
        st.markdown("Manually chat with the agent using Model Context Protocol (MCP) to book a meeting through conversation.")
        
        # Display MCP endpoint if available
        if mcp_endpoint:
            st.info(f"**MCP Service Endpoint:** `{mcp_endpoint}`")
        else:
            st.warning("⚠️ MCP endpoint not found. Please resolve the DID first.")
        
        st.markdown("---")
        
        # Initialize chat history in session state
        if 'mcp_chat_history' not in st.session_state:
            st.session_state.mcp_chat_history = []
        
        # Display chat history
        st.subheader("💬 Chat")
        
        # Chat container
        chat_container = st.container()
        
        with chat_container:
            # Display chat messages
            for idx, message in enumerate(st.session_state.mcp_chat_history):
                if message.get('role') == 'user':
                    with st.chat_message("user"):
                        st.write(message.get('content', ''))
                elif message.get('role') == 'assistant':
                    with st.chat_message("assistant"):
                        st.write(message.get('content', ''))
        
        st.markdown("---")
        
        # Chat input - only enable if MCP endpoint is available
        chat_enabled = mcp_endpoint is not None and MCP_CLIENT_AVAILABLE
        
        if not chat_enabled:
            if not mcp_endpoint:
                st.warning("⚠️ MCP endpoint not available. Please resolve the DID first.")
            elif not MCP_CLIENT_AVAILABLE:
                st.warning("⚠️ MCP client not available. Please install required dependencies.")
        
        user_input = st.chat_input(
            "Type your message to the agent..." if chat_enabled else "Connect to agent first...",
            disabled=not chat_enabled
        )
        
        if user_input and chat_enabled:
            # Add user message to chat history
            st.session_state.mcp_chat_history.append({
                'role': 'user',
                'content': user_input
            })
            
            # Display user message immediately
            with st.chat_message("user"):
                st.write(user_input)
            
            # Send message via MCP client
            with st.chat_message("assistant"):
                with st.spinner("Connecting to agent..."):
                    try:
                        import asyncio
                        
                        # Run async MCP client call
                        async def get_response():
                            async with init_session_from_url(mcp_endpoint) as session:
                                return await send_message(session, user_input)
                        
                        # Run the async function
                        # Streamlit runs in a sync context, so asyncio.run() should work
                        response = asyncio.run(get_response())
                        st.write(response)
                        
                        # Add assistant response to chat history
                        st.session_state.mcp_chat_history.append({
                            'role': 'assistant',
                            'content': response
                        })
                    except ExceptionGroup as eg:
                        # Handle ExceptionGroup (TaskGroup errors)
                        error_details = []
                        for exc in eg.exceptions:
                            error_details.append(str(exc))
                        error_msg = f"Connection error: {'; '.join(error_details)}"
                        st.error(error_msg)
                        st.exception(eg)  # Show full traceback in expander
                        st.session_state.mcp_chat_history.append({
                            'role': 'assistant',
                            'content': error_msg
                        })
                    except Exception as e:
                        # Extract more details from the error
                        error_msg = f"Error communicating with agent: {str(e)}"
                        error_type = type(e).__name__
                        
                        # Provide more helpful error messages
                        if "ConnectError" in error_type or "connection" in str(e).lower():
                            error_msg = f"❌ Cannot connect to MCP server at `{mcp_endpoint}`. Please check:\n- The server is running\n- The URL is correct\n- Network connectivity"
                        elif "TaskGroup" in str(e):
                            error_msg = f"❌ Connection failed: {str(e)}\n\nThis usually means the MCP server is not accessible. Please verify the endpoint URL."
                        
                        st.error(error_msg)
                        with st.expander("🔍 Error Details", expanded=False):
                            st.exception(e)
                        st.session_state.mcp_chat_history.append({
                            'role': 'assistant',
                            'content': error_msg
                        })
            
            st.rerun()
        
        # Clear chat button
        if st.button("🗑️ Clear Chat", key="clear_mcp_chat"):
            st.session_state.mcp_chat_history = []
            st.rerun()
        
        st.markdown("---")
        if chat_enabled:
            st.info("💡 You can ask the agent about available time slots, pending requests, calendar events, or request bookings.")
        else:
            st.info("💡 Connect to an agent by resolving their DID to start chatting.")


def proposed_events_logs_page():
    """Streamlit UI page for reviewing logs of proposed events."""
    st.title("📋 Proposed Events Logs")
    st.markdown("Review all proposed meeting requests and their details.")
    
    st.markdown("---")
    
    # Ensure calendar is properly initialized
    if 'calendar' not in st.session_state or not isinstance(st.session_state.calendar, Calendar):
        st.error("❌ Calendar not initialized. Please go back to the dashboard first.")
        if st.button("← Back to Dashboard", use_container_width=True):
            st.query_params.clear()
            st.rerun()
        return
    
    # Get all proposed events
    all_events = st.session_state.calendar.get_all_events()
    proposed_events = [
        event for event in all_events 
        if get_status_value(event.status).lower() == "proposed"
    ]
    
    # Sort by creation time (newest first)
    proposed_events.sort(key=lambda x: x.created_at, reverse=True)
    
    # Display statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Proposed Events", len(proposed_events))
    with col2:
        total_events = len(all_events)
        st.metric("Total Events", total_events)
    with col3:
        if total_events > 0:
            percentage = (len(proposed_events) / total_events) * 100
            st.metric("Proposed %", f"{percentage:.1f}%")
    
    st.markdown("---")
    
    if not proposed_events:
        st.info("📭 No proposed events found. All meeting requests have been processed.")
        st.markdown("---")
        if st.button("← Back to Dashboard", use_container_width=True, type="primary"):
            st.query_params.clear()
            st.rerun()
        return
    
    # Display proposed events in a table/expander format
    st.subheader(f"📋 Proposed Events ({len(proposed_events)})")
    
    # Filter and sort options
    col1, col2 = st.columns(2)
    with col1:
        sort_option = st.selectbox(
            "Sort by",
            options=["Newest First", "Oldest First", "Time (Upcoming)", "Time (Past)", "Partner Name"],
            index=0
        )
    with col2:
        search_partner = st.text_input(
            "Filter by Partner Agent ID",
            placeholder="Enter agent ID to filter...",
            key="filter_partner_proposed"
        )
    
    # Apply filters
    filtered_events = proposed_events
    if search_partner:
        filtered_events = [
            event for event in filtered_events
            if search_partner.lower() in event.partner_agent_id.lower()
        ]
    
    # Apply sorting
    if sort_option == "Newest First":
        filtered_events.sort(key=lambda x: x.created_at, reverse=True)
    elif sort_option == "Oldest First":
        filtered_events.sort(key=lambda x: x.created_at)
    elif sort_option == "Time (Upcoming)":
        filtered_events.sort(key=lambda x: x.time)
    elif sort_option == "Time (Past)":
        filtered_events.sort(key=lambda x: x.time, reverse=True)
    elif sort_option == "Partner Name":
        filtered_events.sort(key=lambda x: x.partner_agent_id)
    
    if not filtered_events:
        st.warning(f"⚠️ No proposed events found matching the filter criteria.")
        st.markdown("---")
        if st.button("← Back to Dashboard", use_container_width=True, type="primary"):
            st.query_params.clear()
            st.rerun()
        return
    
    # Display each proposed event
    for idx, event in enumerate(filtered_events, 1):
        with st.expander(
            f"#{idx} - {event.partner_agent_id} | {event.time.strftime('%Y-%m-%d %H:%M')} | Duration: {event.duration}",
            expanded=False
        ):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**Event Details**")
                st.write(f"**Event ID:** `{event.event_id}`")
                st.write(f"**Partner Agent:** {event.partner_agent_id}")
                st.write(f"**Status:** {get_status_value(event.status)}")
            
            with col2:
                st.markdown("**Time Information**")
                st.write(f"**Date & Time:** {event.time.strftime('%Y-%m-%d %H:%M')}")
                st.write(f"**Duration:** {event.duration}")
                # Calculate end time
                duration_str = event.duration.lower().strip()
                if duration_str.endswith('m'):
                    minutes = int(duration_str[:-1])
                elif duration_str.endswith('h'):
                    minutes = int(duration_str[:-1]) * 60
                else:
                    minutes = int(duration_str)
                end_time = event.time + timedelta(minutes=minutes)
                st.write(f"**End Time:** {end_time.strftime('%Y-%m-%d %H:%M')}")
            
            with col3:
                st.markdown("**Timestamps**")
                st.write(f"**Created:** {event.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                if hasattr(event, 'updated_at') and event.updated_at:
                    st.write(f"**Updated:** {event.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
            
            st.markdown("---")
            
            # Quick actions
            st.markdown("**Quick Actions**")
            action_col1, action_col2, action_col3, action_col4 = st.columns(4)
            
            with action_col1:
                if st.button("✅ Accept", key=f"accept_proposed_{event.event_id}", type="primary", use_container_width=True):
                    updated_event = st.session_state.calendar.accept_event(event.event_id)
                    if updated_event:
                        db_adapter.save_event(updated_event)
                        st.success("✅ Event accepted!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to accept event")
            
            with action_col2:
                if st.button("❌ Reject", key=f"reject_proposed_{event.event_id}", type="secondary", use_container_width=True):
                    updated_event = st.session_state.calendar.reject_event(event.event_id)
                    if updated_event:
                        db_adapter.save_event(updated_event)
                        st.success("❌ Event rejected!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to reject event")
            
            with action_col3:
                if st.button("📋 View Logs", key=f"logs_proposed_{event.event_id}", use_container_width=True):
                    # Show logs in an expander
                    with st.expander("📋 Event Logs", expanded=True):
                        st.code(f"""
Event ID: {event.event_id}
Partner Agent: {event.partner_agent_id}
Status: {get_status_value(event.status)}
Created: {event.created_at.strftime('%Y-%m-%d %H:%M:%S')}
Updated: {event.updated_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(event, 'updated_at') and event.updated_at else 'N/A'}

Time: {event.time.strftime('%Y-%m-%d %H:%M')}
Duration: {event.duration}

Full Event Data:
{json.dumps(event.to_dict() if hasattr(event, 'to_dict') else event.__dict__, indent=2, default=str)}
                        """, language="text")
                        
                        # Add download button for logs
                        log_content = f"""Event ID: {event.event_id}
Partner Agent: {event.partner_agent_id}
Status: {get_status_value(event.status)}
Created: {event.created_at.strftime('%Y-%m-%d %H:%M:%S')}
Updated: {event.updated_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(event, 'updated_at') and event.updated_at else 'N/A'}

Time: {event.time.strftime('%Y-%m-%d %H:%M')}
Duration: {event.duration}

Full Event Data:
{json.dumps(event.to_dict() if hasattr(event, 'to_dict') else event.__dict__, indent=2, default=str)}
"""
                        st.download_button(
                            label="💾 Download Logs",
                            data=log_content,
                            file_name=f"event_{event.event_id}_logs.txt",
                            mime="text/plain",
                            key=f"download_log_{event.event_id}"
                        )
            
            with action_col4:
                if st.button("🗑️ Delete", key=f"delete_proposed_{event.event_id}", use_container_width=True):
                    if st.session_state.calendar.remove_event(event.event_id):
                        db_adapter.delete_event(event.event_id)
                        st.success("🗑️ Event deleted!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to delete event")
        
        st.markdown("---")
    
    # Back to dashboard button at the bottom
    st.markdown("---")
    if st.button("← Back to Dashboard", use_container_width=True, type="primary"):
        st.query_params.clear()
        st.rerun()


def agentfacts_page():
    """Streamlit UI page for viewing and configuring AgentFacts."""
    st.title("📋 AgentFacts")
    st.markdown("View and configure your agent's metadata and capabilities.")
    
    # Create tabs for View and Configure
    tab1, tab2 = st.tabs(["👁️ View AgentFacts", "⚙️ Configure AgentFacts"])
    
    # View Tab
    with tab1:
        st.subheader("📋 AgentFacts JSON")
        st.markdown("View your agent's current AgentFacts configuration.")
        
        try:
            facts = load_agentfacts()
            
            # Display JSON
            st.json(facts)
            
            # Show endpoint URL
            base_url = st.session_state.get('base_server_url', 'http://localhost:8000')
            agentfacts_url = f"{base_url}/.well-known/agentfacts.json"
            
            st.markdown("---")
            st.markdown("**AgentFacts Endpoint:**")
            st.code(agentfacts_url, language="text")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📋 Copy Endpoint URL", key="copy_endpoint_url", use_container_width=True):
                    st.write("💾 URL copied to clipboard!")
            with col2:
                if st.button("🔗 Open in New Tab", key="open_agentfacts_endpoint", use_container_width=True):
                    st.markdown(f'<meta http-equiv="refresh" content="0; url={agentfacts_url}">', unsafe_allow_html=True)
                    st.info(f"Opening: {agentfacts_url}")
        except Exception as e:
            st.error(f"Could not load AgentFacts: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    # Configure Tab
    with tab2:
        st.subheader("⚙️ Configure AgentFacts")
        st.markdown("Configure your agent's metadata and capabilities.")
        
        # Get current agent DID
        agent_did = st.session_state.get('agent_did')
        if not agent_did:
            try:
                agent = Agent(name="Calendar Agent", host="localhost", a2a_port=8000, mcp_port=8000)
                agent_did = agent.get_did()
                st.session_state.agent_did = agent_did
                st.session_state.agent = agent  # Store agent instance
            except Exception as e:
                st.error(f"Could not load agent DID: {e}")
                traceback.print_exc()
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
    # Load server state from file (updated by main.py when servers start)
    try:
        server_state = get_server_state()
        
        # Update session state with server status
        if 'mcp_server_started' in server_state:
            st.session_state.mcp_server_started = server_state.get('mcp_server_started', False)
            st.session_state.mcp_server_url = server_state.get('mcp_server_url', 'Unknown')
        
        if 'a2a_server_started' in server_state:
            st.session_state.a2a_server_started = server_state.get('a2a_server_started', False)
            st.session_state.a2a_server_url = server_state.get('a2a_server_url', 'Unknown')
        
        if 'base_server_url' in server_state:
            st.session_state.base_server_url = server_state.get('base_server_url', 'http://localhost:8000')
        
        # Load Calendar Admin Agent DID from server state
        if 'calendar_admin_agent_did' in server_state:
            st.session_state.calendar_admin_agent_did = server_state.get('calendar_admin_agent_did')
    except Exception as e:
        # If server state can't be loaded, use defaults
        if 'mcp_server_started' not in st.session_state:
            st.session_state.mcp_server_started = False
        if 'a2a_server_started' not in st.session_state:
            st.session_state.a2a_server_started = False
    
    # Display Calendar Admin Agent DID from server state
    # The DID is already loaded from server_state above if available
    # Fallback: try to create a generic agent if not in server state
    if 'calendar_admin_agent_did' not in st.session_state or not st.session_state.get('calendar_admin_agent_did'):
        try:
            # Initialize agent if not already done (fallback)
            agent = Agent(name="Calendar Manager Agent", host="localhost", a2a_port=8000, mcp_port=8000)
            st.session_state.calendar_admin_agent_did = agent.get_did()
            st.session_state.agent = agent  # Store agent instance for later use
        except Exception as e:
            print(f"⚠️ Error loading agent DID: {e}")
            import traceback
            traceback.print_exc()
            st.session_state.calendar_admin_agent_did = None
            st.session_state.agent = None
    
    # Display Calendar Admin Agent DID prominently in sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔐 Calendar Admin Agent Identity")
    
    if st.session_state.get('calendar_admin_agent_did'):
        with st.sidebar.expander("📋 DID Peer", expanded=True):
            st.write("**Decentralized Identifier:**")
            st.code(st.session_state.calendar_admin_agent_did, language=None)
            
            # Copy button with better feedback
            if st.button("📋 Copy DID", key="copy_did", use_container_width=True):
                st.success("💾 DID copied to clipboard!")
            
            # Show agent name
            st.markdown("---")
            st.write("**Agent Name:**")
            st.info("Calendar Manager Agent")
            
            # Show agent description if available
            agent = st.session_state.get('agent')
            if agent and agent.description:
                st.write("**Description:**")
                st.caption(agent.description)
    else:
        # Show warning if DID is not available
        st.sidebar.warning("⚠️ Calendar Admin Agent DID not available")
    
    # Add navigation links (always show)
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📋 Navigation")
    
    # Share Meeting Link button - prominent placement
    if st.sidebar.button("🔗 Share Meeting Link", key="sidebar_share_meeting_link", use_container_width=True, type="primary"):
        st.query_params["book"] = "1"
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # Other navigation items
    if st.sidebar.button("📋 AgentFacts", key="view_agentfacts", use_container_width=True):
        st.query_params["page"] = "agentfacts"
        st.rerun()
    if st.sidebar.button("🤖 View Agents", key="view_agents", use_container_width=True):
        st.query_params["page"] = "agents"
        st.rerun()
    if st.sidebar.button("🤝 Use Agent To Book Invite", key="use_agent_to_book", use_container_width=True):
        st.query_params["page"] = "use_agent_to_book"
        st.rerun()
    if st.sidebar.button("📋 Proposed Events Logs", key="view_proposed_events", use_container_width=True):
        st.query_params["page"] = "proposed_events_logs"
        st.rerun()
    
    # Show AgentFacts endpoint (use base server URL from state if available)
    base_url = st.session_state.get('base_server_url', 'http://localhost:8000')
    agentfacts_url = f"{base_url}/.well-known/agentfacts.json"
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
    
    # Handle /agents route (admin only - requires authentication)
    if query_params.get('page') == 'agents':
        agents_page()
        return
    
    # Handle /use-agent-to-book route (admin only - requires authentication)
    if query_params.get('page') == 'use_agent_to_book':
        use_agent_to_book_page()
        return
    
    # Handle /proposed-events-logs route (admin only - requires authentication)
    if query_params.get('page') == 'proposed_events_logs':
        proposed_events_logs_page()
        return
    
    # Home/Dashboard page - Admin only (requires authentication)
    # User is authenticated, show dashboard
    
    st.title("📅 Calendar Agent Dashboard")
    
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
        if st.button("🔗 Share Meeting Link", use_container_width=True, type="primary"):
            st.query_params["book"] = "1"
            st.rerun()
    with col3:
        if st.button("🤝 Book Meeting With Agent", use_container_width=True, type="primary"):
            st.query_params["page"] = "use_agent_to_book"
            st.rerun()
    
    st.markdown("---")
    
    # Sidebar for adding/removing events
    with st.sidebar:
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


if __name__ == "__main__":
    main()

