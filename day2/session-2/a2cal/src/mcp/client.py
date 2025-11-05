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


logger = get_logger(__name__)

env = {
    'GOOGLE_API_KEY': os.getenv('GOOGLE_API_KEY'),
}


@asynccontextmanager
async def init_session(host, port, transport):
    """Initializes and manages an MCP ClientSession based on the specified transport.

    This asynchronous context manager establishes a connection to an MCP server
    using either Server-Sent Events (SSE) or Standard I/O (STDIO) transport.
    It handles the setup and teardown of the connection and yields an active
    `ClientSession` object ready for communication.

    Args:
        host: The hostname or IP address of the MCP server (used for SSE).
        port: The port number of the MCP server (used for SSE).
        transport: The communication transport to use ('sse' or 'stdio').

    Yields:
        ClientSession: An initialized and ready-to-use MCP client session.

    Raises:
        ValueError: If an unsupported transport type is provided (implicitly,
                    as it won't match 'sse' or 'stdio').
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
    elif transport == 'stdio':
        if not os.getenv('GOOGLE_API_KEY'):
            logger.error('GOOGLE_API_KEY is not set')
            raise ValueError('GOOGLE_API_KEY is not set')
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
            f"Unsupported transport type: {transport}. Must be 'sse' or 'stdio'."
        )


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
