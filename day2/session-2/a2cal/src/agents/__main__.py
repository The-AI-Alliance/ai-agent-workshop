# type: ignore

import json
import logging
import sys

from pathlib import Path

import click
import httpx
import uvicorn

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    BasePushNotificationSender,
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
)
from a2a.types import AgentCard
from common.prompts import prompts
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


@click.command()
@click.option('--host', 'host', default='localhost')
@click.option('--port', 'port', default=10101)
@click.option('--agent-card', 'agent_card')
def main(host, port, agent_card):
    """Starts an Agent server."""
    try:
        if not agent_card:
            raise ValueError('Agent card is required')
        with Path.open(agent_card) as file:
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

        logger.info(f'Starting server on {host}:{port}')

        uvicorn.run(server.build(), host=host, port=port)
    except FileNotFoundError:
        logger.error(f"Error: File '{agent_card}' not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error(f"Error: File '{agent_card}' contains invalid JSON.")
        sys.exit(1)
    except Exception as e:
        logger.error(f'An error occurred during server startup: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()