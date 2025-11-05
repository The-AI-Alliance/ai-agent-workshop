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

logger = logging.getLogger(__name__)


def get_agent(agent_card: AgentCard):
    """Get the agent, given an agent card."""
    try:
        if agent_card.name == 'Calendar Manager Agent':
            from .calendar_admin_agent import CalendarAdminAgent
            # Get instructions from agent card or use default
            instructions = getattr(agent_card, 'instructions', 'You are a helpful calendar management assistant that accepts and manages calendar requests.')
            return CalendarAdminAgent(
                agent_name=agent_card.name,
                description=agent_card.description or 'Calendar Manager Agent',
                instructions=instructions
            )
        if agent_card.name == 'Calendar Booking Agent':
            from .calendar_booking_agent import CalendarBookingAgent
            # Get instructions from agent card or use default
            instructions = getattr(agent_card, 'instructions', 'You are a helpful calendar booking assistant.')
            return CalendarBookingAgent(
                agent_name=agent_card.name,
                description=agent_card.description or 'Calendar Booking Agent',
                instructions=instructions
            )
    except Exception as e:
        raise e


def create_a2a_app(agent_card_path: str):
    """Create an A2A agent server application.
    
    Args:
        agent_card_path: Path to the agent card JSON file
        
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

        request_handler = DefaultRequestHandler(
            agent_executor=GenericAgentExecutor(agent=get_agent(agent_card)),
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

