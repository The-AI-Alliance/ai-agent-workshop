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

# Load .env file at the beginning
try:
    from dotenv import load_dotenv
    # Load .env from the calendar-agent directory
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded .env file from {env_path}")
    else:
        # Try loading from parent directory
        parent_env = Path(__file__).parent.parent / '.env'
        if parent_env.exists():
            load_dotenv(parent_env)
            print(f"✅ Loaded .env file from {parent_env}")
        else:
            # Try loading from current working directory
            load_dotenv()
            print(f"ℹ️  No .env file found, using environment variables")
except ImportError:
    print("⚠️  python-dotenv not installed. Install with: pip install python-dotenv")
    print("   Environment variables must be set manually")

# Import A2A SDK
A2A_AVAILABLE = False
A2AServer = None
AgentCard = None
AgentSkill = None
AgentCapabilities = None
A2AStarletteApplication = None
DefaultRequestHandler = None
InMemoryTaskStore = None
AgentExecutor = None
RequestContext = None
EventQueue = None
uvicorn = None

try:
    from a2a.types import AgentCard as A2AAgentCard, AgentSkill as A2AAgentSkill, AgentCapabilities as A2AAgentCapabilities
    from a2a.server.apps import A2AStarletteApplication as A2AStarletteApp
    from a2a.server.request_handlers import DefaultRequestHandler as A2ADefaultRequestHandler
    from a2a.server.tasks import InMemoryTaskStore as A2AInMemoryTaskStore
    from a2a.server.agent_execution import AgentExecutor as A2AAgentExecutor, RequestContext as A2ARequestContext
    from a2a.server.events import EventQueue as A2AEventQueue
    
    try:
        import uvicorn
    except ImportError:
        uvicorn = None
    
    A2A_AVAILABLE = True
    AgentCard = A2AAgentCard
    AgentSkill = A2AAgentSkill
    AgentCapabilities = A2AAgentCapabilities
    A2AStarletteApplication = A2AStarletteApp
    DefaultRequestHandler = A2ADefaultRequestHandler
    InMemoryTaskStore = A2AInMemoryTaskStore
    AgentExecutor = A2AAgentExecutor
    RequestContext = A2ARequestContext
    EventQueue = A2AEventQueue
    
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
    
    # URL should point to /a2a/ (with trailing slash) to avoid redirect issues
    # This ensures the client POSTs directly to /a2a/ instead of /a2a (which redirects)
    url = os.getenv("A2A_ENDPOINT", f"http://{host}:{port}/a2a/")
    
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


class CalendarAgentExecutor(AgentExecutor if AgentExecutor else object):
    """Agent executor for calendar operations using OpenAI to process messages and call tools."""
    
    def __init__(self):
        if AgentExecutor:
            super().__init__()
        
        # Initialize OpenAI client
        import os
        from openai import AsyncOpenAI
        
        api_key = os.getenv('OPENAI_KEY')
        if not api_key:
            raise ValueError('OPENAI_KEY environment variable not set')
        
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = 'gpt-4o'  # or 'gpt-4', 'gpt-3.5-turbo', etc.
        
        # Define tools in OpenAI format
        self.tools = [
            {
                'type': 'function',
                'function': {
                    'name': 'requestAvailableSlots',
                    'description': 'Get available time slots for booking within a date range',
                    'parameters': {
                        'type': 'object',
                        'required': ['start_date', 'end_date'],
                        'properties': {
                            'start_date': {
                                'type': 'string',
                                'format': 'date',
                                'description': 'Start date for availability check (YYYY-MM-DD)'
                            },
                            'end_date': {
                                'type': 'string',
                                'format': 'date',
                                'description': 'End date for availability check (YYYY-MM-DD)'
                            },
                            'duration': {
                                'type': 'string',
                                'default': '30m',
                                'description': "Desired meeting duration (e.g., '30m', '1h', '45m')"
                            },
                            'partner_agent_id': {
                                'type': 'string',
                                'description': 'Optional partner agent ID to filter availability'
                            },
                            'timezone': {
                                'type': 'string',
                                'default': 'UTC',
                                'description': 'Timezone for the availability check'
                            }
                        }
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'requestBooking',
                    'description': 'Request a booking for a meeting at a specific time',
                    'parameters': {
                        'type': 'object',
                        'required': ['start_time', 'duration', 'partner_agent_id'],
                        'properties': {
                            'start_time': {
                                'type': 'string',
                                'format': 'date-time',
                                'description': 'Start time in ISO format (e.g., 2025-01-15T10:00:00Z)'
                            },
                            'duration': {
                                'type': 'string',
                                'description': "Meeting duration (e.g., '30m', '1h', '45m')"
                            },
                            'partner_agent_id': {
                                'type': 'string',
                                'description': 'Agent ID of the partner requesting the meeting'
                            },
                            'initial_status': {
                                'type': 'string',
                                'enum': ['proposed', 'accepted', 'confirmed'],
                                'default': 'proposed',
                                'description': 'Initial status of the booking'
                            }
                        }
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'deleteBooking',
                    'description': 'Delete or cancel a booking by event ID',
                    'parameters': {
                        'type': 'object',
                        'required': ['event_id'],
                        'properties': {
                            'event_id': {
                                'type': 'string',
                                'description': 'The event ID to delete'
                            }
                        }
                    }
                }
            }
        ]
        
        self.system_prompt = """You are a calendar management agent that helps users find available time slots, book meetings, and manage calendar events.

You have access to three tools:
1. requestAvailableSlots - Find available time slots within a date range
2. requestBooking - Book a meeting at a specific time
3. deleteBooking - Cancel or delete a booking

When users ask about availability or want to book meetings, use the appropriate tools to help them.
Always provide helpful and clear responses based on the tool results."""
    
    async def execute(
        self,
        context: RequestContext if RequestContext else Any,
        event_queue: EventQueue if EventQueue else Any,
    ) -> None:
        """Execute calendar agent logic using OpenAI to process messages and call tools.
        
        This follows the pattern from github-agent example:
        https://github.com/a2aproject/a2a-samples/blob/main/samples/python/agents/github-agent/openai_agent_executor.py
        """
        if not A2A_AVAILABLE:
            if event_queue:
                await event_queue.enqueue_event({
                    "type": "text",
                    "content": "Calendar agent: A2A SDK not available"
                })
            return
        
        from a2a.utils import new_agent_text_message
        from a2a.types import TextPart
        import json
        
        # Extract message text from context.message.parts (following github-agent pattern)
        message_text = ''
        if hasattr(context, 'message') and context.message:
            if hasattr(context.message, 'parts'):
                # Extract text from all TextPart objects (like github-agent does)
                for part in context.message.parts:
                    if hasattr(part, 'root') and isinstance(part.root, TextPart):
                        message_text += part.root.text
                    elif isinstance(part, TextPart):
                        message_text += part.text
                    elif hasattr(part, 'text'):
                        message_text += part.text
            elif hasattr(context.message, 'content'):
                message_text = str(context.message.content)
            elif isinstance(context.message, dict):
                message_text = str(context.message.get('content', ''))
        
        if not message_text:
            if event_queue:
                await event_queue.enqueue_event(new_agent_text_message(
                    "Calendar agent ready. I can help you find available slots, book meetings, and manage calendar events."
                ))
            return
        
        # Process request with OpenAI (following github-agent pattern)
        messages = [
            {'role': 'system', 'content': self.system_prompt},
            {'role': 'user', 'content': message_text},
        ]
        
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            try:
                # Make API call to OpenAI
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=self.tools,
                    tool_choice='auto',
                    temperature=0.1,
                    max_tokens=4000,
                )
                
                message = response.choices[0].message
                
                # Add assistant's response to messages
                messages.append({
                    'role': 'assistant',
                    'content': message.content,
                    'tool_calls': message.tool_calls,
                })
                
                # Check if there are tool calls to execute
                if message.tool_calls:
                    # Execute tool calls
                    for tool_call in message.tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)
                        
                        # Execute the function
                        result = None
                        if function_name == "requestAvailableSlots":
                            result = handle_request_available_slots(function_args)
                        elif function_name == "requestBooking":
                            result = handle_request_booking(function_args)
                        elif function_name == "deleteBooking":
                            result = handle_delete_booking(function_args)
                        else:
                            result = {'error': f'Function {function_name} not found'}
                        
                        # Serialize result properly
                        if hasattr(result, 'model_dump'):
                            # It's a Pydantic model
                            result_json = json.dumps(result.model_dump())
                        elif isinstance(result, dict):
                            result_json = json.dumps(result)
                        else:
                            result_json = str(result)
                        
                        # Add tool result to messages
                        messages.append({
                            'role': 'tool',
                            'tool_call_id': tool_call.id,
                            'content': result_json,
                        })
                    
                    # Continue the loop to get the final response
                    continue
                
                # No more tool calls, this is the final response
                if message.content:
                    if event_queue:
                        await event_queue.enqueue_event(new_agent_text_message(message.content))
                break
                
            except Exception as e:
                error_message = f'Sorry, an error occurred while processing the request: {str(e)}'
                if event_queue:
                    await event_queue.enqueue_event(new_agent_text_message(error_message))
                break
        
        if iteration >= max_iterations:
            error_message = 'Sorry, the request has exceeded the maximum number of iterations.'
            if event_queue:
                await event_queue.enqueue_event(new_agent_text_message(error_message))
    
    async def cancel(
        self, 
        context: RequestContext if RequestContext else Any, 
        event_queue: EventQueue if EventQueue else Any
    ) -> None:
        """Cancel the current execution."""
        if not A2A_AVAILABLE or not event_queue:
            return
        
        from a2a.utils import new_agent_text_message
        await event_queue.enqueue_event(new_agent_text_message("Calendar agent operation cancelled."))


def create_a2a_server(host: str = "localhost", port: int = 8000) -> Optional[Any]:
    """Create and configure the A2A server using the actual SDK.
    
    This follows the pattern from the official A2A samples:
    https://github.com/a2aproject/a2a-samples/blob/main/samples/python/agents/helloworld/__main__.py
    
    Args:
        host: Host to bind the server to
        port: Port to bind the server to
        
    Returns:
        Starlette app instance configured with A2A, or None if SDK not available
    """
    if not A2A_AVAILABLE or not A2AStarletteApplication or not AgentCard or not DefaultRequestHandler:
        print("❌ A2A SDK not available. Cannot create A2A server.")
        print("   Install with: uv add 'a2a-sdk[http-server]'")
        print("   Or: pip install 'a2a-sdk[http-server]'")
        return None
    
    try:
        # Create agent card from dict
        agent_card_dict = create_agent_card(host=host, port=port)
        # URL should include /a2a path since we mount at /a2a
        # Use the URL from agent_card_dict which should have trailing slash
        url = agent_card_dict.get('url', f"http://{host}:{port}/a2a/")
        
        # Create AgentSkill for calendar booking
        calendar_skill = None
        if AgentSkill:
            calendar_skill = AgentSkill(
                id='calendar_booking',
                name='Calendar Booking',
                description='Tools for calendar booking and scheduling',
                tags=['calendar', 'scheduling', 'booking', 'meetings', 'availability'],
                examples=['find available slots', 'book a meeting', 'schedule a call']
            )
        
        # Create AgentCard object
        try:
            # Build AgentCard from dict
            # Use URL from dict - keep trailing slash to avoid redirect issues
            # The A2A SDK/AgentCard should accept URLs with trailing slashes
            agent_card_url = url.rstrip('/')  # Remove trailing slash for AgentCard object
            agent_card = AgentCard(
                name=agent_card_dict.get('name', 'Calendar Agent'),
                description=agent_card_dict.get('description', 'Calendar management agent'),
                url=agent_card_url,
                version=agent_card_dict.get('version', '0.1.0'),
                default_input_modes=agent_card_dict.get('defaultInputModes', ['text']),
                default_output_modes=agent_card_dict.get('defaultOutputModes', ['text']),
                capabilities=AgentCapabilities(
                    streaming=agent_card_dict.get('capabilities', {}).get('streaming', False),
                    push_notifications=agent_card_dict.get('capabilities', {}).get('pushNotifications', False),
                    state_transition_history=agent_card_dict.get('capabilities', {}).get('stateTransitionHistory', False)
                ),
                skills=[calendar_skill] if calendar_skill else []
            )
        except Exception as e:
            print(f"⚠️  Could not create AgentCard object: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        # Create agent executor
        try:
            agent_executor = CalendarAgentExecutor()
        except ValueError as e:
            print(f"⚠️  Could not create CalendarAgentExecutor: {e}")
            print("   Make sure OPENAI_KEY environment variable is set")
            import traceback
            traceback.print_exc()
            return None
        except Exception as e:
            print(f"⚠️  Error creating CalendarAgentExecutor: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        # Create request handler with executor and task store
        request_handler = DefaultRequestHandler(
            agent_executor=agent_executor,
            task_store=InMemoryTaskStore() if InMemoryTaskStore else None
        )
        
        # Create A2A Starlette application (following the example pattern)
        a2a_server = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler
        )
        
        # Build the Starlette app - this automatically adds .well-known/agent-card.json route!
        starlette_app = a2a_server.build()
        
        # Add root endpoint handler for GET requests only
        # POST requests should go to SDK routes like /messages/send
        # The SDK will handle routing for POST requests
        # Note: We only handle GET here to avoid interfering with SDK POST routes
        @starlette_app.route("/", methods=["GET"])
        async def root_endpoint(request):
            """Root endpoint for A2A server - handles GET requests to /a2a/."""
            from starlette.responses import JSONResponse
            # Use the agent card URL (without trailing slash) for endpoint references
            base_url = agent_card.url if hasattr(agent_card, 'url') else url.rstrip('/')
            return JSONResponse({
                "service": "Calendar Agent A2A Server",
                "version": agent_card.version,
                "protocol": "A2A",
                "url": base_url,
                "endpoints": {
                    "agent_card": f"{base_url}/.well-known/agent-card.json",
                    "messages": f"{base_url}/messages",
                    "tasks": f"{base_url}/tasks"
                }
            })
        
        # Add health check endpoint
        @starlette_app.route("/health", methods=["GET"])
        async def health_check(request):
            """Health check endpoint for the A2A server."""
            from starlette.responses import JSONResponse
            return JSONResponse({
                "status": "healthy",
                "service": "Calendar Agent A2A Server",
                "agent_card": {
                    "name": agent_card.name,
                    "version": agent_card.version,
                    "url": agent_card.url
                },
                "endpoints": {
                    "health": f"{url}/health",
                    "agent_card": f"{url}/.well-known/agent-card.json"
                }
            })
        
        print(f"✅ A2A Starlette app created (following official example pattern)")
        print(f"📍 Agent card will be served at: {url}/.well-known/agent-card.json")
        print(f"💚 Health check available at: {url}/health")
        print(f"🔗 A2A endpoints available at: {url}/a2a")
        
        # Store app and config for later
        starlette_app._a2a_host = host
        starlette_app._a2a_port = port
        starlette_app._a2a_agent_card = agent_card
        
        return starlette_app
        
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

