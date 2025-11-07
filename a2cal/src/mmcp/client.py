# type:ignore
import asyncio
import json
import os

from contextlib import asynccontextmanager

import click

from fastmcp.utilities.logging import get_logger
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, ReadResourceResult

# Try to import Streamable HTTP client
try:
    from mcp.client.streamable_http import streamablehttp_client
    STREAMABLE_HTTP_AVAILABLE = True
except ImportError:
    STREAMABLE_HTTP_AVAILABLE = False
    streamablehttp_client = None


logger = get_logger(__name__)

# Use GEMINI_API_TOKEN, fallback to GOOGLE_API_KEY or GEMINI_API_KEY for backward compatibility
gemini_token = os.getenv('GEMINI_API_TOKEN') or os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
env = {
    'GEMINI_API_TOKEN': gemini_token,
    'GEMINI_API_KEY': gemini_token,  # For LiteLLM compatibility
    'GOOGLE_API_KEY': gemini_token,  # Keep for backward compatibility
}


@asynccontextmanager
async def init_session(host, port, transport):
    """Initializes and manages an MCP ClientSession based on the specified transport.

    This asynchronous context manager establishes a connection to an MCP server
    using either Server-Sent Events (SSE), Streamable HTTP, or Standard I/O (STDIO) transport.
    It handles the setup and teardown of the connection and yields an active
    `ClientSession` object ready for communication.

    Args:
        host: The hostname or IP address of the MCP server (used for SSE/Streamable HTTP).
        port: The port number of the MCP server (used for SSE/Streamable HTTP).
        transport: The communication transport to use ('sse', 'streamable-http', or 'stdio').

    Yields:
        ClientSession: An initialized and ready-to-use MCP client session.

    Raises:
        ValueError: If an unsupported transport type is provided.
        Exception: Other potential exceptions during client initialization or
                   session setup.
    """
    if transport == 'sse':
        url = f'http://{host}:{port}/sse'
        async with sse_client(url) as (read_stream, write_stream):
            async with ClientSession(
                read_stream=read_stream, write_stream=write_stream
            ) as session:
                logger.debug('SSE ClientSession created, initializing...')
                await session.initialize()
                logger.info('SSE ClientSession initialized successfully.')
                yield session
    elif transport == 'streamable-http' or transport == 'streamable_http':
        if not STREAMABLE_HTTP_AVAILABLE:
            raise ValueError('Streamable HTTP client not available. Please install required dependencies.')
        url = f'http://{host}:{port}/mcp'
        async with streamablehttp_client(url=url) as (read_stream, write_stream, _get_session_id):
            async with ClientSession(
                read_stream=read_stream, write_stream=write_stream
            ) as session:
                logger.debug('Streamable HTTP ClientSession created, initializing...')
                await session.initialize()
                logger.info('Streamable HTTP ClientSession initialized successfully.')
                yield session
    elif transport == 'stdio':
        gemini_token = os.getenv('GEMINI_API_TOKEN') or os.getenv('GOOGLE_API_KEY')
        if not gemini_token:
            logger.error('GEMINI_API_TOKEN is not set')
            raise ValueError('GEMINI_API_TOKEN is not set. Please set GEMINI_API_TOKEN environment variable.')
        stdio_params = StdioServerParameters(
            command='uv',
            args=['run', 'a2a-mcp'],
            env=env,
        )
        async with stdio_client(stdio_params) as (read_stream, write_stream):
            async with ClientSession(
                read_stream=read_stream,
                write_stream=write_stream,
            ) as session:
                logger.debug('STDIO ClientSession created, initializing...')
                await session.initialize()
                logger.info('STDIO ClientSession initialized successfully.')
                yield session
    else:
        logger.error(f'Unsupported transport type: {transport}')
        raise ValueError(
            f"Unsupported transport type: {transport}. Must be 'sse', 'streamable-http', or 'stdio'."
        )


@asynccontextmanager
async def init_session_from_url(url: str):
    """Initializes and manages an MCP ClientSession from a full URL (for Streamable HTTP).

    This is useful when you have a complete URL from a DID service endpoint.
    Automatically detects if the URL is Streamable HTTP or SSE based on the path.

    Args:
        url: The full URL of the MCP server endpoint (e.g., 'https://example.com/mcp' or 'http://localhost:8000/mcp').

    Yields:
        ClientSession: An initialized and ready-to-use MCP client session.

    Raises:
        ValueError: If Streamable HTTP client is not available or URL format is invalid.
        Exception: Other potential exceptions during client initialization.
    """
    if not STREAMABLE_HTTP_AVAILABLE:
        raise ValueError('Streamable HTTP client not available. Please install required dependencies.')
    
    logger.info(f'Connecting to MCP server at: {url}')
    
    try:
        # Ensure URL doesn't end with /sse (that would be SSE, not Streamable HTTP)
        if url.endswith('/sse'):
            # For SSE, use sse_client
            logger.debug('Using SSE client for URL ending with /sse')
            async with sse_client(url) as (read_stream, write_stream):
                async with ClientSession(
                    read_stream=read_stream, write_stream=write_stream
                ) as session:
                    logger.debug('SSE ClientSession created from URL, initializing...')
                    await session.initialize()
                    logger.info('SSE ClientSession initialized successfully.')
                    yield session
        else:
            # For Streamable HTTP, use streamablehttp_client
            logger.debug('Using Streamable HTTP client')
            try:
                async with streamablehttp_client(url=url) as (read_stream, write_stream, _get_session_id):
                    async with ClientSession(
                        read_stream=read_stream, write_stream=write_stream
                    ) as session:
                        logger.debug('Streamable HTTP ClientSession created from URL, initializing...')
                        await session.initialize()
                        logger.info('Streamable HTTP ClientSession initialized successfully.')
                        yield session
            except ExceptionGroup as eg:
                # Extract and log the actual errors from the ExceptionGroup
                logger.error(f'ExceptionGroup error connecting to {url}:')
                for exc in eg.exceptions:
                    logger.error(f'  - {type(exc).__name__}: {exc}')
                # Re-raise with more context
                raise ConnectionError(
                    f"Failed to connect to MCP server at {url}. "
                    f"Errors: {[str(e) for e in eg.exceptions]}"
                ) from eg
    except Exception as e:
        logger.error(f'Error in init_session_from_url for {url}: {e}', exc_info=True)
        raise


async def find_agent(session: ClientSession, query) -> CallToolResult:
    """Calls the 'find_agent' tool on the connected MCP server.

    Args:
        session: The active ClientSession.
        query: The natural language query to send to the 'find_agent' tool.

    Returns:
        The result of the tool call.
    """
    logger.info(f"Calling 'find_agent' tool with query: '{query[:50]}...'")
    return await session.call_tool(
        name='find_agent',
        arguments={
            'query': query,
        },
    )


async def find_resource(session: ClientSession, resource) -> ReadResourceResult:
    """Reads a resource from the connected MCP server.

    Args:
        session: The active ClientSession.
        resource: The URI of the resource to read (e.g., 'resource://agent_cards/list').

    Returns:
        The result of the resource read operation.
    """
    logger.info(f'Reading resource: {resource}')
    return await session.read_resource(resource)


async def request_available_slots(
    session: ClientSession, start_date: str, end_date: str, duration: str = "30m"
) -> CallToolResult:
    """Calls the 'requestAvailableSlots' tool on the connected MCP server.

    Args:
        session: The active ClientSession.
        start_date: Start date/time in ISO format (e.g., "2024-01-15T09:00:00")
        end_date: End date/time in ISO format (e.g., "2024-01-15T17:00:00")
        duration: Duration of the meeting (e.g., "30m", "1h", "45m")

    Returns:
        The result of the tool call.
    """
    logger.info(f"Calling 'requestAvailableSlots' tool: {start_date} to {end_date}, duration {duration}")
    return await session.call_tool(
        name='requestAvailableSlots',
        arguments={
            'start_date': start_date,
            'end_date': end_date,
            'duration': duration,
        },
    )


async def request_booking(
    session: ClientSession, time: str, duration: str, partner_agent_id: str
) -> CallToolResult:
    """Calls the 'requestBooking' tool on the connected MCP server.

    Args:
        session: The active ClientSession.
        time: Start time in ISO format (e.g., "2024-01-15T10:00:00")
        duration: Duration of the meeting (e.g., "30m", "1h", "45m")
        partner_agent_id: ID of the partner agent requesting the meeting

    Returns:
        The result of the tool call.
    """
    logger.info(f"Calling 'requestBooking' tool: {time}, duration {duration}, partner {partner_agent_id}")
    return await session.call_tool(
        name='requestBooking',
        arguments={
            'time': time,
            'duration': duration,
            'partner_agent_id': partner_agent_id,
        },
    )


async def accept_meeting(session: ClientSession, event_id: str) -> CallToolResult:
    """Calls the 'acceptMeeting' tool on the connected MCP server.

    Args:
        session: The active ClientSession.
        event_id: ID of the event to accept

    Returns:
        The result of the tool call.
    """
    logger.info(f"Calling 'acceptMeeting' tool for event {event_id}")
    return await session.call_tool(
        name='acceptMeeting',
        arguments={'event_id': event_id},
    )


async def reject_meeting(session: ClientSession, event_id: str) -> CallToolResult:
    """Calls the 'rejectMeeting' tool on the connected MCP server.

    Args:
        session: The active ClientSession.
        event_id: ID of the event to reject

    Returns:
        The result of the tool call.
    """
    logger.info(f"Calling 'rejectMeeting' tool for event {event_id}")
    return await session.call_tool(
        name='rejectMeeting',
        arguments={'event_id': event_id},
    )


async def confirm_meeting(session: ClientSession, event_id: str) -> CallToolResult:
    """Calls the 'confirmMeeting' tool on the connected MCP server.

    Args:
        session: The active ClientSession.
        event_id: ID of the event to confirm

    Returns:
        The result of the tool call.
    """
    logger.info(f"Calling 'confirmMeeting' tool for event {event_id}")
    return await session.call_tool(
        name='confirmMeeting',
        arguments={'event_id': event_id},
    )


async def get_calendar_events(
    session: ClientSession, status: str = None
) -> CallToolResult:
    """Calls the 'getCalendarEvents' tool on the connected MCP server.

    Args:
        session: The active ClientSession.
        status: Optional status filter (e.g., "proposed", "accepted", "confirmed", "booked")

    Returns:
        The result of the tool call.
    """
    logger.info(f"Calling 'getCalendarEvents' tool, status filter: {status}")
    arguments = {}
    if status:
        arguments['status'] = status
    return await session.call_tool(
        name='getCalendarEvents',
        arguments=arguments,
    )


async def get_upcoming_events(
    session: ClientSession, limit: int = 10
) -> CallToolResult:
    """Calls the 'getUpcomingEvents' tool on the connected MCP server.

    Args:
        session: The active ClientSession.
        limit: Maximum number of events to return (default: 10)

    Returns:
        The result of the tool call.
    """
    logger.info(f"Calling 'getUpcomingEvents' tool, limit: {limit}")
    return await session.call_tool(
        name='getUpcomingEvents',
        arguments={'limit': limit},
    )


async def get_pending_requests(session: ClientSession) -> CallToolResult:
    """Calls the 'getPendingRequests' tool on the connected MCP server.

    Args:
        session: The active ClientSession.

    Returns:
        The result of the tool call.
    """
    logger.info("Calling 'getPendingRequests' tool")
    return await session.call_tool(
        name='getPendingRequests',
        arguments={},
    )


async def cancel_event(session: ClientSession, event_id: str) -> CallToolResult:
    """Calls the 'cancelEvent' tool on the connected MCP server.

    Args:
        session: The active ClientSession.
        event_id: ID of the event to cancel

    Returns:
        The result of the tool call.
    """
    logger.info(f"Calling 'cancelEvent' tool for event {event_id}")
    return await session.call_tool(
        name='cancelEvent',
        arguments={'event_id': event_id},
    )


async def send_message(session: ClientSession, message: str, partner_agent_id: str = None) -> str:
    """Send a natural language message to the MCP server and get a response.
    
    Uses an LLM to interpret the message and call appropriate MCP tools.
    
    Args:
        session: The active ClientSession.
        message: The natural language message to send.
        partner_agent_id: Optional partner agent ID for booking requests.
        
    Returns:
        A response string from the agent.
    """
    import json
    from datetime import datetime, timedelta
    from common.utils import init_api_key
    
    # Initialize API key for LLM
    try:
        init_api_key()
    except ValueError as e:
        logger.error(f"Failed to initialize API key: {e}")
        return f"Error: {e}. Please set GEMINI_API_TOKEN environment variable."
    
    # Get available tools from MCP session
    try:
        tools_result = await session.list_tools()
        available_tools = tools_result.tools if hasattr(tools_result, 'tools') else []
        logger.info(f"Available MCP tools: {[tool.name for tool in available_tools]}")
    except Exception as e:
        logger.error(f"Failed to list tools: {e}")
        available_tools = []
    
    # Build tool descriptions for LLM
    tools_description = []
    for tool in available_tools:
        tool_desc = {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": {}
        }
        # inputSchema is a dict (JSON Schema), not an object
        if hasattr(tool, 'inputSchema') and tool.inputSchema:
            input_schema = tool.inputSchema
            # Handle both dict and object types
            if isinstance(input_schema, dict):
                properties = input_schema.get('properties', {})
                tool_desc["parameters"] = {
                    prop: {
                        "type": properties[prop].get('type', 'string'),
                        "description": properties[prop].get('description', '')
                    }
                    for prop in properties
                }
            elif hasattr(input_schema, 'properties'):
                # Handle object with properties attribute
                tool_desc["parameters"] = {
                    prop: {
                        "type": getattr(input_schema.properties[prop], 'type', 'string'),
                        "description": getattr(input_schema.properties[prop], 'description', '')
                    }
                    for prop in input_schema.properties
                }
        tools_description.append(tool_desc)
    
    # Use LLM to interpret the message and determine which tool to call
    try:
        try:
            import litellm
            from litellm import acompletion
        except ImportError:
            logger.error("litellm is not installed. Please install it with: pip install litellm")
            return "Error: litellm is not installed. Please install it to use LLM-based message interpretation."
        
        # Build prompt for LLM
        tools_json = json.dumps(tools_description, indent=2)
        current_date = datetime.now().strftime('%Y-%m-%d')
        tomorrow_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        system_prompt = f"""You are a helpful assistant that interprets user messages and calls the appropriate MCP tools.

Available tools:
{tools_json}

Current date: {current_date}
Tomorrow: {tomorrow_date}

When the user wants to book a meeting, use the partner_agent_id: {partner_agent_id or 'agent-beta-42'}

Your task:
1. Analyze the user's message
2. Determine which tool to call
3. Extract the required parameters from the message
4. Return a JSON object with:
   - "tool": tool name
   - "arguments": object with tool parameters

For date/time parsing:
- "tomorrow" means {tomorrow_date}
- Parse times like "2pm" to 24-hour format (14:00)
- Convert durations like "30 min" to "30m", "1 hour" to "1h"
- Use ISO format for dates: YYYY-MM-DDTHH:MM:SS

Example response:
{{
  "tool": "requestBooking",
  "arguments": {{
    "time": "2024-01-16T14:00:00",
    "duration": "30m",
    "partner_agent_id": "{partner_agent_id or 'agent-beta-42'}"
  }}
}}"""

        user_prompt = f"User message: {message}"

        # Call LLM
        model = os.getenv('LITELLM_MODEL', 'gemini/gemini-2.0-flash')
        logger.info(f"Calling LLM ({model}) to interpret message: {message[:100]}...")
        
        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Try with response_format first (for OpenAI-compatible models)
        # Add timeout to prevent hanging
        try:
            response = await asyncio.wait_for(
                acompletion(
                    model=model,
                    messages=messages,
                    temperature=0.0,
                    response_format={"type": "json_object"}
                ),
                timeout=30.0  # 30 second timeout for LLM call
            )
        except asyncio.TimeoutError:
            logger.error("LLM call timed out after 30 seconds")
            return "Error: The request took too long to process. Please try again with a simpler request."
        except Exception as e:
            # Fallback: try without response_format (for models that don't support it)
            logger.warning(f"Failed with response_format, trying without: {e}")
            # Add instruction to return JSON in the prompt instead
            user_prompt_with_json = f"{user_prompt}\n\nIMPORTANT: You must respond with ONLY a valid JSON object, no other text. Format: {{\"tool\": \"tool_name\", \"arguments\": {{...}}}}"
            try:
                response = await asyncio.wait_for(
                    acompletion(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt_with_json}
                        ],
                        temperature=0.0
                    ),
                    timeout=30.0  # 30 second timeout for fallback LLM call
                )
            except asyncio.TimeoutError:
                logger.error("LLM call (fallback) timed out after 30 seconds")
                return "Error: The request took too long to process. Please try again with a simpler request."
        
        # Extract tool call from LLM response
        llm_response = response.choices[0].message.content
        logger.info(f"LLM response: {llm_response}")
        
        # Clean up response - remove markdown code blocks if present
        cleaned_response = llm_response.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]  # Remove ```json
        elif cleaned_response.startswith("```"):
            cleaned_response = cleaned_response[3:]  # Remove ```
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]  # Remove closing ```
        cleaned_response = cleaned_response.strip()
        
        # Parse JSON response
        try:
            tool_call = json.loads(cleaned_response)
            tool_name = tool_call.get("tool")
            tool_args = tool_call.get("arguments", {})
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Cleaned response: {cleaned_response}")
            return f"I understood your message, but had trouble processing it. Please try rephrasing. Error: {str(e)}"
        
        if not tool_name:
            return "I couldn't determine which action to take. Please be more specific about what you'd like to do."
        
        # Call the appropriate tool with timeout
        logger.info(f"Calling tool: {tool_name} with arguments: {tool_args}")
        
        try:
            result = await asyncio.wait_for(
                session.call_tool(tool_name, tool_args),
                timeout=30.0  # 30 second timeout for tool call
            )
        except asyncio.TimeoutError:
            logger.error(f"Tool call '{tool_name}' timed out after 30 seconds")
            return f"Error: The tool '{tool_name}' took too long to execute. Please try again."
        
        # Extract and return response
        if result.content and len(result.content) > 0:
            return result.content[0].text
        elif hasattr(result, 'text'):
            return result.text
        else:
            return f"Tool '{tool_name}' executed successfully, but no response text was returned."
            
    except Exception as e:
        logger.error(f"Error in LLM-based message interpretation: {e}", exc_info=True)
        return f"Error processing your message: {str(e)}. Please try rephrasing your request."


# Test util
async def main(host, port, transport, query, resource, tool, tool_args):
    """Main asynchronous function to connect to the MCP server and execute commands.

    Used for local testing.

    Args:
        host: Server hostname.
        port: Server port.
        transport: Connection transport ('sse' or 'stdio').
        query: Optional query string for the 'find_agent' tool.
        resource: Optional resource URI to read.
        tool: Optional tool name to execute.
        tool_args: Optional dictionary of arguments for the tool.
    """
    logger.info('Starting Client to connect to Calendar Agent MCP Server')
    async with init_session(host, port, transport) as session:
        if query:
            result = await find_agent(session, query)
            data = json.loads(result.content[0].text)
            logger.info(json.dumps(data, indent=2))
        if resource:
            result = await find_resource(session, resource)
            logger.info(result)
            data = json.loads(result.contents[0].text)
            logger.info(json.dumps(data, indent=2))
        if tool:
            result = None
            if tool == 'requestAvailableSlots':
                result = await request_available_slots(
                    session,
                    tool_args.get('start_date', '2024-01-15T09:00:00'),
                    tool_args.get('end_date', '2024-01-15T17:00:00'),
                    tool_args.get('duration', '30m'),
                )
            elif tool == 'requestBooking':
                result = await request_booking(
                    session,
                    tool_args.get('time', '2024-01-15T10:00:00'),
                    tool_args.get('duration', '30m'),
                    tool_args.get('partner_agent_id', 'test-agent-1'),
                )
            elif tool == 'acceptMeeting':
                result = await accept_meeting(session, tool_args.get('event_id', ''))
            elif tool == 'rejectMeeting':
                result = await reject_meeting(session, tool_args.get('event_id', ''))
            elif tool == 'confirmMeeting':
                result = await confirm_meeting(session, tool_args.get('event_id', ''))
            elif tool == 'getCalendarEvents':
                result = await get_calendar_events(session, tool_args.get('status'))
            elif tool == 'getUpcomingEvents':
                result = await get_upcoming_events(session, tool_args.get('limit', 10))
            elif tool == 'getPendingRequests':
                result = await get_pending_requests(session)
            elif tool == 'cancelEvent':
                result = await cancel_event(session, tool_args.get('event_id', ''))
            
            if result:
                logger.info(result)
                if result.content and len(result.content) > 0:
                    try:
                        data = json.loads(result.content[0].text)
                        logger.info(json.dumps(data, indent=2))
                    except (json.JSONDecodeError, AttributeError):
                        logger.info(result.content[0].text if hasattr(result.content[0], 'text') else str(result))


# Command line tester
@click.command()
@click.option('--host', default='localhost', help='SSE Host')
@click.option('--port', default='10100', help='SSE Port')
@click.option('--transport', default='stdio', help='MCP Transport')
@click.option('--find_agent', help='Query to find an agent')
@click.option('--resource', help='URI of the resource to locate')
@click.option(
    '--tool_name',
    type=click.Choice([
        'requestAvailableSlots',
        'requestBooking',
        'acceptMeeting',
        'rejectMeeting',
        'confirmMeeting',
        'getCalendarEvents',
        'getUpcomingEvents',
        'getPendingRequests',
        'cancelEvent',
    ]),
    help='Calendar tool to execute',
)
@click.option('--tool_args', help='JSON string of tool arguments (e.g., \'{"event_id": "evt-123"}\')')
def cli(host, port, transport, find_agent, resource, tool_name, tool_args):
    """A command-line client to interact with the Calendar Agent MCP server."""
    tool_args_dict = {}
    if tool_args:
        try:
            tool_args_dict = json.loads(tool_args)
        except json.JSONDecodeError:
            logger.error(f'Invalid JSON in tool_args: {tool_args}')
            tool_args_dict = {}
    
    asyncio.run(main(host, port, transport, find_agent, resource, tool_name, tool_args_dict))


if __name__ == '__main__':
    cli()
