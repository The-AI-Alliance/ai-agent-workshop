# type: ignore
import json
import os
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

import google.generativeai as genai
import numpy as np
import pandas as pd

from a2a_mcp.common.utils import init_api_key
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.logging import get_logger

# Add the services directory to the path to import calendar_api
sys.path.insert(0, str(Path(__file__).parent.parent / 'services' / 'calendar-service'))
from calendar_api import Calendar, Event, EventStatus
from db_adapter import CalendarDBAdapter


logger = get_logger(__name__)
AGENT_CARDS_DIR = 'agent_cards'
MODEL = 'models/embedding-001'
CALENDAR_DB = 'calendar_agent.db'

def generate_embeddings(text):
    """Generates embeddings for the given text using Google Generative AI.

    Args:
        text: The input string for which to generate embeddings.

    Returns:
        A list of embeddings representing the input text.
    """
    return genai.embed_content(
        model=MODEL,
        content=text,
        task_type='retrieval_document',
    )['embedding']


def load_agent_cards():
    """Loads agent card data from JSON files within a specified directory.

    Returns:
        A list containing JSON data from an agent card file found in the specified directory.
        Returns an empty list if the directory is empty, contains no '.json' files,
        or if all '.json' files encounter errors during processing.
    """
    card_uris = []
    agent_cards = []
    dir_path = Path(AGENT_CARDS_DIR)
    if not dir_path.is_dir():
        logger.error(
            f'Agent cards directory not found or is not a directory: {AGENT_CARDS_DIR}'
        )
        return agent_cards

    logger.info(f'Loading agent cards from card repo: {AGENT_CARDS_DIR}')

    for filename in os.listdir(AGENT_CARDS_DIR):
        if filename.lower().endswith('.json'):
            file_path = dir_path / filename

            if file_path.is_file():
                logger.info(f'Reading file: {filename}')
                try:
                    with file_path.open('r', encoding='utf-8') as f:
                        data = json.load(f)
                        card_uris.append(
                            f'resource://agent_cards/{Path(filename).stem}'
                        )
                        agent_cards.append(data)
                except json.JSONDecodeError as jde:
                    logger.error(f'JSON Decoder Error {jde}')
                except OSError as e:
                    logger.error(f'Error reading file {filename}: {e}.')
                except Exception as e:
                    logger.error(
                        f'An unexpected error occurred processing {filename}: {e}',
                        exc_info=True,
                    )
    logger.info(
        f'Finished loading agent cards. Found {len(agent_cards)} cards.'
    )
    return card_uris, agent_cards


def build_agent_card_embeddings() -> pd.DataFrame:
    """Loads agent cards, generates embeddings for them, and returns a DataFrame.

    Returns:
        Optional[pd.DataFrame]: A Pandas DataFrame containing the original
        'agent_card' data and their corresponding 'Embeddings'. Returns None
        if no agent cards were loaded initially or if an exception occurred
        during the embedding generation process.
    """
    card_uris, agent_cards = load_agent_cards()
    logger.info('Generating Embeddings for agent cards')
    try:
        if agent_cards:
            df = pd.DataFrame(
                {'card_uri': card_uris, 'agent_card': agent_cards}
            )
            df['card_embeddings'] = df.apply(
                lambda row: generate_embeddings(json.dumps(row['agent_card'])),
                axis=1,
            )
            return df
        logger.info('Done generating embeddings for agent cards')
    except Exception as e:
        logger.error(f'An unexpected error occurred : {e}.', exc_info=True)
        return None


def serve(host, port, transport):  # noqa: PLR0915
    """Initializes and runs the Calendar Agent MCP server.

    Args:
        host: The hostname or IP address to bind the server to.
        port: The port number to bind the server to.
        transport: The transport mechanism for the MCP server (e.g., 'stdio', 'sse').

    Raises:
        ValueError: If the 'GOOGLE_API_KEY' environment variable is not set.
    """
    init_api_key()
    logger.info('Starting Calendar Agent MCP Server')
    mcp = FastMCP('calendar-agent', host=host, port=port)

    df = build_agent_card_embeddings()
    
    # Initialize calendar and database adapter
    db_adapter = CalendarDBAdapter(db_path=CALENDAR_DB)
    calendar = Calendar()
    
    # Load existing events from database
    try:
        existing_events = db_adapter.load_all_events(Event, EventStatus)
        for event in existing_events:
            calendar.add_event(event)
        logger.info(f'Loaded {len(existing_events)} events from database')
    except Exception as e:
        logger.error(f'Error loading events from database: {e}')
        logger.error(traceback.format_exc())

    @mcp.tool(
        name='find_agent',
        description='Finds the most relevant agent card based on a natural language query string.',
    )
    def find_agent(query: str) -> str:
        """Finds the most relevant agent card based on a query string.

        This function takes a user query, typically a natural language question or a task generated by an agent,
        generates its embedding, and compares it against the
        pre-computed embeddings of the loaded agent cards. It uses the dot
        product to measure similarity and identifies the agent card with the
        highest similarity score.

        Args:
            query: The natural language query string used to search for a
                   relevant agent.

        Returns:
            The json representing the agent card deemed most relevant
            to the input query based on embedding similarity.
        """
        query_embedding = genai.embed_content(
            model=MODEL, content=query, task_type='retrieval_query'
        )
        dot_products = np.dot(
            np.stack(df['card_embeddings']), query_embedding['embedding']
        )
        best_match_index = np.argmax(dot_products)
        logger.debug(
            f'Found best match at index {best_match_index} with score {dot_products[best_match_index]}'
        )
        return df.iloc[best_match_index]['agent_card']

    @mcp.tool()
    def requestAvailableSlots(start_date: str, end_date: str, duration: str = "30m") -> dict:
        """Request available time slots for booking between start_date and end_date.
        
        Args:
            start_date: Start date/time in ISO format (e.g., "2024-01-15T09:00:00")
            end_date: End date/time in ISO format (e.g., "2024-01-15T17:00:00")
            duration: Duration of the meeting (e.g., "30m", "1h", "45m")
            
        Returns:
            Dictionary with available time slots
        """
        try:
            logger.info(f'Requesting available slots from {start_date} to {end_date}, duration {duration}')
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)
            
            # Parse duration to minutes
            duration_str = duration.lower().strip()
            if duration_str.endswith('m'):
                duration_minutes = int(duration_str[:-1])
            elif duration_str.endswith('h'):
                duration_minutes = int(duration_str[:-1]) * 60
            else:
                duration_minutes = int(duration_str)
            
            available_slots = []
            current_time = start_dt
            
            # Get all booked/confirmed/accepted events
            confirmed_events = calendar.get_confirmed_events()
            pending_events = calendar.get_pending_events()
            all_busy = confirmed_events + pending_events
            
            while current_time + timedelta(minutes=duration_minutes) <= end_dt:
                slot_end = current_time + timedelta(minutes=duration_minutes)
                
                # Create a temporary event to check for conflicts
                temp_event = Event(
                    time=current_time,
                    duration=duration,
                    partner_agent_id="temp",
                    status=EventStatus.PROPOSED
                )
                
                # Check if this slot conflicts with any existing events
                has_conflict = False
                for busy_event in all_busy:
                    if temp_event.overlaps_with(busy_event):
                        has_conflict = True
                        break
                
                if not has_conflict:
                    available_slots.append({
                        'start': current_time.isoformat(),
                        'end': slot_end.isoformat(),
                        'duration': duration
                    })
                
                # Move to next slot (15 minute intervals)
                current_time += timedelta(minutes=15)
            
            return {
                'available_slots': available_slots,
                'count': len(available_slots)
            }
        except Exception as e:
            logger.error(f'Error requesting available slots: {e}')
            logger.error(traceback.format_exc())
            return {'error': str(e), 'available_slots': []}

    @mcp.tool()
    def requestBooking(time: str, duration: str, partner_agent_id: str) -> dict:
        """Request a calendar booking/meeting.
        
        Args:
            time: Start time in ISO format (e.g., "2024-01-15T10:00:00")
            duration: Duration of the meeting (e.g., "30m", "1h", "45m")
            partner_agent_id: ID of the partner agent requesting the meeting
            
        Returns:
            Dictionary with booking result and event details
        """
        try:
            logger.info(f'Requesting booking at {time} for {duration} with partner {partner_agent_id}')
            event_time = datetime.fromisoformat(time)
            
            event = calendar.propose_event(
                time=event_time,
                duration=duration,
                partner_agent_id=partner_agent_id
            )
            
            # Save to database
            db_adapter.save_event(event)
            
            return {
                'success': True,
                'event': event.to_dict(),
                'status': event.status.value if hasattr(event.status, 'value') else str(event.status)
            }
        except ValueError as e:
            logger.error(f'Error requesting booking: {e}')
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f'Unexpected error requesting booking: {e}')
            logger.error(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    @mcp.tool()
    def proposeMeeting(time: str, duration: str, partner_agent_id: str) -> dict:
        """Propose a meeting time (same as requestBooking, alias for clarity).
        
        Args:
            time: Start time in ISO format (e.g., "2024-01-15T10:00:00")
            duration: Duration of the meeting (e.g., "30m", "1h", "45m")
            partner_agent_id: ID of the partner agent proposing the meeting
            
        Returns:
            Dictionary with proposal result and event details
        """
        return requestBooking(time, duration, partner_agent_id)

    @mcp.tool()
    def acceptMeeting(event_id: str) -> dict:
        """Accept a proposed meeting.
        
        Args:
            event_id: ID of the event to accept
            
        Returns:
            Dictionary with acceptance result and event details
        """
        try:
            logger.info(f'Accepting meeting {event_id}')
            event = calendar.accept_event(event_id)
            
            if event:
                # Save to database
                db_adapter.save_event(event)
                return {
                    'success': True,
                    'event': event.to_dict(),
                    'status': event.status.value if hasattr(event.status, 'value') else str(event.status)
                }
            else:
                return {
                    'success': False,
                    'error': f'Event {event_id} not found or not in proposed status'
                }
        except Exception as e:
            logger.error(f'Error accepting meeting: {e}')
            logger.error(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    @mcp.tool()
    def rejectMeeting(event_id: str) -> dict:
        """Reject a proposed meeting.
        
        Args:
            event_id: ID of the event to reject
            
        Returns:
            Dictionary with rejection result and event details
        """
        try:
            logger.info(f'Rejecting meeting {event_id}')
            event = calendar.reject_event(event_id)
            
            if event:
                # Save to database
                db_adapter.save_event(event)
                return {
                    'success': True,
                    'event': event.to_dict(),
                    'status': event.status.value if hasattr(event.status, 'value') else str(event.status)
                }
            else:
                return {
                    'success': False,
                    'error': f'Event {event_id} not found or not in proposed status'
                }
        except Exception as e:
            logger.error(f'Error rejecting meeting: {e}')
            logger.error(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    @mcp.tool()
    def confirmMeeting(event_id: str) -> dict:
        """Confirm an accepted meeting (mark as booked).
        
        Args:
            event_id: ID of the event to confirm
            
        Returns:
            Dictionary with confirmation result and event details
        """
        try:
            logger.info(f'Confirming meeting {event_id}')
            event = calendar.confirm_event(event_id)
            
            if event:
                # Also mark as booked
                calendar.mark_booked(event_id)
                event = calendar.get_event(event_id)
                
                # Save to database
                db_adapter.save_event(event)
                return {
                    'success': True,
                    'event': event.to_dict(),
                    'status': event.status.value if hasattr(event.status, 'value') else str(event.status)
                }
            else:
                return {
                    'success': False,
                    'error': f'Event {event_id} not found or cannot be confirmed'
                }
        except Exception as e:
            logger.error(f'Error confirming meeting: {e}')
            logger.error(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    @mcp.tool()
    def getCalendarEvents(status: Optional[str] = None) -> dict:
        """Get all calendar events, optionally filtered by status.
        
        Args:
            status: Optional status filter (e.g., "proposed", "accepted", "confirmed", "booked")
            
        Returns:
            Dictionary with list of events
        """
        try:
            logger.info(f'Getting calendar events, status filter: {status}')
            
            if status:
                # Convert status string to EventStatus enum
                status_upper = status.upper()
                try:
                    event_status = EventStatus[status_upper]
                    events = calendar.get_events_by_status(event_status)
                except KeyError:
                    return {'error': f'Invalid status: {status}', 'events': []}
            else:
                events = calendar.get_all_events()
            
            return {
                'events': [event.to_dict() for event in events],
                'count': len(events)
            }
        except Exception as e:
            logger.error(f'Error getting calendar events: {e}')
            logger.error(traceback.format_exc())
            return {'error': str(e), 'events': []}

    @mcp.tool()
    def getUpcomingEvents(limit: Optional[int] = 10) -> dict:
        """Get upcoming confirmed/booked events.
        
        Args:
            limit: Maximum number of events to return (default: 10)
            
        Returns:
            Dictionary with list of upcoming events
        """
        try:
            logger.info(f'Getting upcoming events, limit: {limit}')
            events = calendar.get_upcoming_events(limit=limit)
            
            return {
                'events': [event.to_dict() for event in events],
                'count': len(events)
            }
        except Exception as e:
            logger.error(f'Error getting upcoming events: {e}')
            logger.error(traceback.format_exc())
            return {'error': str(e), 'events': []}

    @mcp.tool()
    def cancelEvent(event_id: str) -> dict:
        """Cancel an event (remove it from the calendar).
        
        Args:
            event_id: ID of the event to cancel
            
        Returns:
            Dictionary with cancellation result
        """
        try:
            logger.info(f'Canceling event {event_id}')
            event = calendar.get_event(event_id)
            
            if event:
                removed = calendar.remove_event(event_id)
                if removed:
                    # Delete from database
                    db_adapter.delete_event(event_id)
                    return {
                        'success': True,
                        'message': f'Event {event_id} cancelled successfully',
                        'event': event.to_dict()
                    }
                else:
                    return {'success': False, 'error': f'Failed to remove event {event_id}'}
            else:
                return {'success': False, 'error': f'Event {event_id} not found'}
        except Exception as e:
            logger.error(f'Error canceling event: {e}')
            logger.error(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    @mcp.tool()
    def getPendingRequests() -> dict:
        """Get all pending meeting requests (proposed or accepted but not confirmed).
        
        Returns:
            Dictionary with list of pending events
        """
        try:
            logger.info('Getting pending meeting requests')
            events = calendar.get_pending_events()
            
            return {
                'events': [event.to_dict() for event in events],
                'count': len(events)
            }
        except Exception as e:
            logger.error(f'Error getting pending requests: {e}')
            logger.error(traceback.format_exc())
            return {'error': str(e), 'events': []}

    @mcp.resource('resource://agent_cards/list', mime_type='application/json')
    def get_agent_cards() -> dict:
        """Retrieves all loaded agent cards as a json / dictionary for the MCP resource endpoint.

        This function serves as the handler for the MCP resource identified by
        the URI 'resource://agent_cards/list'.

        Returns:
            A json / dictionary structured as {'agent_cards': [...]}, where the value is a
            list containing all the loaded agent card dictionaries. Returns
            {'agent_cards': []} if the data cannot be retrieved.
        """
        resources = {}
        logger.info('Starting read resources')
        resources['agent_cards'] = df['card_uri'].to_list()
        return resources

    @mcp.resource(
        'resource://agent_cards/{card_name}', mime_type='application/json'
    )
    def get_agent_card(card_name: str) -> dict:
        """Retrieves an agent card as a json / dictionary for the MCP resource endpoint.

        This function serves as the handler for the MCP resource identified by
        the URI 'resource://agent_cards/{card_name}'.

        Returns:
            A json / dictionary
        """
        resources = {}
        logger.info(
            f'Starting read resource resource://agent_cards/{card_name}'
        )
        resources['agent_card'] = (
            df.loc[
                df['card_uri'] == f'resource://agent_cards/{card_name}',
                'agent_card',
            ]
        ).to_list()

        return resources

    logger.info(
        f'Calendar Agent MCP Server at {host}:{port} and transport {transport}'
    )
    mcp.run(transport=transport)
