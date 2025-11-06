"""A2A Agent server functions for integration."""
import json
import logging
from pathlib import Path

import httpx

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    BasePushNotificationSender,
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
)
from a2a.types import AgentCard
from common.agent_executor import GenericAgentExecutor
from common import prompts
from .calendar_admin_agent import CalendarAdminAgent
from .calendar_booking_agent import CalendarBookingAgent

logger = logging.getLogger(__name__)

def get_agent(agent_card: AgentCard, host: str = "localhost", a2a_port: int = 8000, mcp_port: int = 8000):
    """Get the agent, given an agent card.
    
    Args:
        agent_card: The agent card defining the agent
        host: Host for service endpoints (for DID generation)
        a2a_port: Port for A2A service endpoint (for DID generation)
        mcp_port: Port for MCP service endpoint (for DID generation)
    """
    try:
        if agent_card.name == 'Calendar Manager Agent':
            # Get instructions from agent card or use default
            instructions = getattr(agent_card, 'instructions', 'You are a helpful calendar management assistant that accepts and manages calendar requests.')
            return CalendarAdminAgent(
                agent_name=agent_card.name,
                description=agent_card.description or 'Calendar Manager Agent',
                instructions=prompts.CALENDAR_ADMIN_INSTRUCTIONS,
                host=host,
                a2a_port=a2a_port,
                mcp_port=mcp_port
            )
        if agent_card.name == 'Calendar Booking Agent':
            from .calendar_booking_agent import CalendarBookingAgent
            # Get instructions from agent card or use default
            instructions = getattr(agent_card, 'instructions', 'You are a helpful calendar booking assistant.')
            return CalendarBookingAgent(
                agent_name=agent_card.name,
                description=agent_card.description or 'Calendar Booking Agent',
                instructions=prompts.CALENDAR_BOOKING_INSTRUCTIONS,
                host=host,
                a2a_port=a2a_port,
                mcp_port=mcp_port
            )
    except Exception as e:
        raise e


def create_a2a_app(agent_card_path: str, host: str = "localhost", a2a_port: int = 8000, mcp_port: int = 8000):
    """Create an A2A agent server application.
    
    Args:
        agent_card_path: Path to the agent card JSON file
        host: Host for service endpoints (for DID generation)
        a2a_port: Port for A2A service endpoint (for DID generation)
        mcp_port: Port for MCP service endpoint (for DID generation)
        
    Returns:
        Starlette application instance
    """
    try:
        logger.info(f'Loading agent card from {agent_card_path}')
        agent_card_file = Path(agent_card_path)
        if not agent_card_file.exists():
            raise FileNotFoundError(f"Agent card file not found: {agent_card_path}")
        
        with agent_card_file.open() as file:
            data = json.load(file)
        agent_card = AgentCard(**data)

        client = httpx.AsyncClient()
        push_notification_config_store = InMemoryPushNotificationConfigStore()
        push_notification_sender = BasePushNotificationSender(
            client, config_store=push_notification_config_store
        )

        agent = get_agent(agent_card, host=host, a2a_port=a2a_port, mcp_port=mcp_port)
        
        # Store agent instance and DID for UI access
        # Only store if it's a CalendarAdminAgent (has get_did method)
        if hasattr(agent, 'get_did'):
            try:
                agent_did = agent.get_did()
                logger.info(f'🔐 Agent {agent_card.name} DID: {agent_did}')
                print(f'🔐 Agent {agent_card.name} DID: {agent_did}')
                # Store in server state for UI access (specifically for Calendar Admin Agent)
                if agent_card.name == 'Calendar Manager Agent':
                    from common.server_state import set_calendar_admin_agent_did
                    set_calendar_admin_agent_did(agent_did)
                    logger.info(f'✅ Calendar Admin Agent DID stored in server state: {agent_did}')
                    print(f'✅ Calendar Admin Agent DID stored in server state: {agent_did}')
            except Exception as e:
                logger.error(f'❌ Could not get agent DID for {agent_card.name}: {e}')
                print(f'❌ Could not get agent DID for {agent_card.name}: {e}')
                import traceback
                logger.error(traceback.format_exc())
        
        request_handler = DefaultRequestHandler(
            agent_executor=GenericAgentExecutor(agent=agent),
            task_store=InMemoryTaskStore(),
            push_config_store=push_notification_config_store,
            push_sender=push_notification_sender,
        )

        server = A2AStarletteApplication(
            agent_card=agent_card, http_handler=request_handler
        )

        logger.info(f'A2A agent server created for {agent_card.name}')
        return server.build()
        
    except FileNotFoundError as e:
        logger.error(f"Error: File '{agent_card_path}' not found.")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Error: File '{agent_card_path}' contains invalid JSON.")
        raise
    except Exception as e:
        logger.error(f'An error occurred during A2A server creation: {e}')
        raise

