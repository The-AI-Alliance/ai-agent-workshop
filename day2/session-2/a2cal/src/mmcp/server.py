# type: ignore
import sys
from pathlib import Path

from common.utils import init_api_key, is_debug
from fastmcp import FastMCP
from fastmcp.utilities.logging import get_logger

# Add the services directory to the path to import calendar_api
sys.path.insert(0, str(Path(__file__).parent.parent / 'services' / 'calendar-service'))
from calendar_api import Calendar, Event, EventStatus
from db_adapter import CalendarDBAdapter
import pandas as pd
import os
import json
import google.generativeai as genai


# Import tools registration function
from mmcp.tools import register_tools

# Import shared calendar service
# Note: calendar-service directory has a hyphen, so we import from the __init__.py directly
try:
    # Add the services directory to sys.path if not already there
    services_calendar_path = Path(__file__).parent.parent / 'services' / 'calendar-service'
    if str(services_calendar_path) not in sys.path:
        sys.path.insert(0, str(services_calendar_path))
    
    # Import from the __init__.py in calendar-service directory
    # We need to import it as a module - the directory name has a hyphen
    import importlib.util
    init_file = services_calendar_path / '__init__.py'
    if init_file.exists():
        spec = importlib.util.spec_from_file_location("calendar_service", init_file)
        calendar_service_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(calendar_service_module)
        get_shared_calendar_service = calendar_service_module.get_shared_calendar_service
        SHARED_CALENDAR_DB = calendar_service_module.CALENDAR_DB
    else:
        raise ImportError("calendar-service __init__.py not found")
except Exception as e:
    # Final fallback - define locally
    # Note: logger not yet defined, so use print
    print(f"⚠️  Warning: Could not import shared calendar service: {e}. Using local instances.")
    SHARED_CALENDAR_DB = "calendar_agent.db"
    def get_shared_calendar_service(db_path=SHARED_CALENDAR_DB, owner_agent_id=None):
        """Fallback shared calendar service."""
        db_adapter = CalendarDBAdapter(db_path=db_path)
        calendar = Calendar(owner_agent_id=owner_agent_id)
        try:
            existing_events = db_adapter.load_all_events(Event, EventStatus)
            for event in existing_events:
                calendar.add_event(event)
        except Exception:
            pass
        return db_adapter, calendar


logger = get_logger(__name__)
DEBUG = is_debug()

if DEBUG:
    import logging
    logger.setLevel(logging.DEBUG)
    logging.getLogger().setLevel(logging.DEBUG)
    logger.debug("DEBUG mode enabled for MCP server")

# Agent cards directory - relative to src directory
AGENT_CARDS_DIR = Path(__file__).parent.parent / 'agent_cards'
CALENDAR_DB = 'calendar_agent.db'

def generate_embeddings(text):
    """Generates embeddings for the given text using Gemini API.

    Args:
        text: The input string for which to generate embeddings.

    Returns:
        A list of embeddings representing the input text.
    """
    return genai.embed_content(
        model='models/embedding-001',
        content=text,
        task_type='retrieval_document',
    )['embedding']


def load_agent_cards():
    """Loads agent card data from JSON files within a specified directory.

    Returns:
        tuple: A tuple containing two lists: card_uris (list of URI strings) and
        agent_cards (list of JSON-serializable dictionaries). Returns empty lists
        if the directory is empty, contains no '.json' files,
        or if all '.json' files encounter errors during processing.
    """
    card_uris = []
    agent_cards = []
    dir_path = Path(AGENT_CARDS_DIR)
    if not dir_path.is_dir():
        logger.error(
            f'Agent cards directory not found or is not a directory: {AGENT_CARDS_DIR}'
        )
        return card_uris, agent_cards  # Return tuple of empty lists

    logger.info(f'Loading agent cards from card repo: {AGENT_CARDS_DIR}')

    for filename in os.listdir(str(dir_path)):
        if filename.lower().endswith('.json'):
            file_path = Path(dir_path) / filename

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


def create_mcp_app(host=None, port=None, db_adapter=None, calendar=None):
    """Creates and initializes the Calendar Agent MCP Starlette application.

    Args:
        host: The hostname or IP address (ignored when mounting, used only for standalone mode)
        port: The port number (ignored when mounting, used only for standalone mode)
        db_adapter: Optional shared CalendarDBAdapter instance (uses shared service if None)
        calendar: Optional shared Calendar instance (uses shared service if None)

    Returns:
        Starlette: The Starlette application instance with MCP tools and resources
                   (can be mounted on FastAPI using app.mount())

    Raises:
        ValueError: If the 'GEMINI_API_TOKEN' environment variable is not set.
    """
    init_api_key()
    logger.info('Initializing Calendar Agent MCP Server')
    
    # Use shared calendar service if instances not provided
    if db_adapter is None or calendar is None:
        logger.info('Using shared calendar service')
        shared_db, shared_cal = get_shared_calendar_service(db_path=SHARED_CALENDAR_DB)
        if db_adapter is None:
            db_adapter = shared_db
        if calendar is None:
            calendar = shared_cal
    else:
        logger.info('Using provided calendar service instances')
    
    # FastMCP host/port are only used when running standalone (mcp.run())
    # When mounting with http_app(), these are ignored
    mcp_host = host or 'localhost'
    mcp_port = port or 10100
    if DEBUG:
        logger.debug(f"MCP Server config: host={mcp_host}, port={mcp_port} (only used in standalone mode)")
    
    # Create FastMCP with stateless_http=True for SSE support
    # This enables streamable-http transport which provides SSE endpoints
    mcp = FastMCP("Calendar Agent MCP Server", stateless_http=True)
    
    if DEBUG:
        logger.debug(f"FastMCP instance created: {type(mcp)}")
        logger.debug(f"FastMCP name: Calendar Agent MCP Server")
        logger.debug(f"FastMCP stateless_http: True")
        logger.debug(f"Using shared calendar service: {db_adapter is not None and calendar is not None}")

    df = build_agent_card_embeddings()
    
    # Register all tools and resources with the MCP instance
    register_tools(mcp, df, calendar, db_adapter)
    

    # Log initialization (host/port are only used for standalone mode, not when mounting)
    if host and port:
        logger.info(
            f'Calendar Agent MCP Server initialized at {host}:{port}'
        )
    else:
        logger.info(
            'Calendar Agent MCP Server initialized (mounted mode - host/port not used)'
        )
    
    # Get the HTTP app from FastMCP for mounting
    # FastMCP with stateless_http=True provides SSE via streamable-http transport
    # Following calendar-agent approach: use http_app() which returns the Starlette app
    # The SSE endpoint should be at /sse in the returned app
    # When mounted at /mcp prefix, it becomes accessible at /mcp/sse
    # Note: Unlike mcp.run(path="/mcp") which handles path internally,
    # http_app() returns the base app - mounting at /mcp should handle the prefix
    mcp_app = mcp.http_app(path='/mcp')
    logger.info("Got FastMCP http_app() (with stateless_http=True for SSE support)")
    logger.info("SSE endpoint will be at /mcp/sse after mounting at /mcp prefix")
    
    # Always log route structure (not just in DEBUG) to help diagnose mounting issues
    logger.info(f"MCP app type: {type(mcp_app)}")
    logger.info(f"MCP app has lifespan: {hasattr(mcp_app, 'lifespan')}")
    if hasattr(mcp_app, 'routes'):
        logger.info(f"MCP app has {len(mcp_app.routes)} routes:")
        for i, route in enumerate(mcp_app.routes):
            route_info = f"  Route {i}: {type(route).__name__}"
            if hasattr(route, 'path'):
                route_info += f" path={route.path}"
            if hasattr(route, 'methods'):
                route_info += f" methods={route.methods}"
            logger.info(route_info)
    else:
        logger.warning("MCP app does not have 'routes' attribute")
    
    # Return the Starlette app from FastMCP (which can be mounted on FastAPI)
    return mcp_app


def serve(host, port, transport):  # noqa: PLR0915
    """Initializes and runs the Calendar Agent MCP server.

    Args:
        host: The hostname or IP address to bind the server to.
        port: The port number to bind the server to.
        transport: The transport mechanism for the MCP server (e.g., 'stdio', 'sse').

    Raises:
        ValueError: If the 'GEMINI_API_TOKEN' environment variable is not set.
    """
    init_api_key()
    logger.info('Starting Calendar Agent MCP Server')
    
    # Use shared calendar service for consistency
    logger.info('Using shared calendar service')
    shared_db, shared_cal = get_shared_calendar_service(db_path=SHARED_CALENDAR_DB)
    db_adapter = shared_db
    calendar = shared_cal
    
    # FastMCP host/port are used when running standalone
    # Use stateless_http=True for SSE support via streamable-http transport
    mcp = FastMCP("Calendar Agent MCP Server", stateless_http=True)
    
    # Reuse the same initialization logic
    df = build_agent_card_embeddings()
    
    # Register all tools and resources with the MCP instance
    register_tools(mcp, df, calendar, db_adapter)

    # Convert transport to FastMCP format
    # "sse" -> "streamable-http" for SSE support
    if transport == "sse":
        mcp_transport = "streamable-http"
    else:
        mcp_transport = transport
    
    logger.info(
        f'Calendar Agent MCP Server at {host}:{port} and transport {mcp_transport}'
    )
    mcp.run(transport=mcp_transport, host=host, port=port, path="/mcp")
