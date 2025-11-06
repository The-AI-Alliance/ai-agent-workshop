# type: ignore

import json
import logging
import os
import re

from collections.abc import AsyncIterable
from typing import Any

from common.agent_runner import AgentRunner
from common.base_agent import BaseAgent
from common.utils import get_mcp_server_config, init_api_key
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import SseServerParams
from google.genai import types as genai_types
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPServerParams

logger = logging.getLogger(__name__)


class CalendarAdminAgent(BaseAgent):
    """Calendar Admin Agent backed by ADK for managing calendar requests."""

    def __init__(self, agent_name: str, description: str, instructions: str,
                 host: str = "localhost", a2a_port: int = 8000, mcp_port: int = 8000):
        init_api_key()

        super().__init__(
            agent_name=agent_name,
            description=description,
            content_types=['text', 'text/plain'],
            host=host,
            a2a_port=a2a_port,
            mcp_port=mcp_port
        )

        logger.info(f'✅ Calendar Admin Agent initialized: {self.agent_name}')
        logger.info(f'   DID: {self.get_did()}')
        logger.info(f'   A2A endpoint: {self.get_a2a_endpoint()}')
        logger.info(f'   MCP endpoint: {self.get_mcp_endpoint()}')

        self.instructions = instructions
        self.agent = None

    async def init_agent(self):
        logger.info(f'Initializing {self.agent_name} metadata')
        config = get_mcp_server_config()
        logger.info(f'MCP Server url={config.url} (transport: {config.transport})')
        # Use MCPToolset constructor with SseServerParams
        # For Streamable HTTP, use the base /mcp endpoint (not /sse)
        # SseServerParams works for both SSE and Streamable HTTP transports
        mcp_toolset = MCPToolset(
            connection_params=StreamableHTTPServerParams(url=config.url)
        )
        tools = await mcp_toolset.get_tools()

        for tool in tools:
            logger.info(f'Loaded tools {tool.name}')
        generate_content_config = genai_types.GenerateContentConfig(
            temperature=0.0
        )
        LITELLM_MODEL = os.getenv('LITELLM_MODEL', 'gemini/gemini-2.0-flash')
        # Convert display name to valid identifier for ADK Agent (no spaces allowed)
        agent_identifier = self.agent_name.replace(' ', '_').lower()
        self.agent = Agent(
            name=agent_identifier,
            instruction=self.instructions,
            model=LiteLlm(model=LITELLM_MODEL),
            disallow_transfer_to_parent=True,
            disallow_transfer_to_peers=True,
            generate_content_config=generate_content_config,
            tools=tools,
        )
        self.runner = AgentRunner()

    async def invoke(self, query, session_id) -> dict:
        logger.info(f'Running {self.agent_name} for session {session_id}')

        raise NotImplementedError('Please use the streraming function')

    async def stream(
        self, query, context_id, task_id
    ) -> AsyncIterable[dict[str, Any]]:
        logger.info(
            f'Running {self.agent_name} stream for session {context_id} {task_id} - {query}'
        )

        if not query:
            raise ValueError('Query cannot be empty')

        # Initialize agent if needed, with error handling
        if not self.agent:
            try:
                await self.init_agent()
            except Exception as e:
                logger.error(
                    f'Failed to initialize {self.agent_name}: {e}',
                    exc_info=True
                )
                # Yield an error response instead of raising
                yield {
                    'response_type': 'text',
                    'is_task_complete': True,
                    'require_user_input': False,
                    'content': f'Failed to initialize agent: {str(e)}. Please check the MCP server connection and try again.',
                }
                return
        
        # Stream agent responses with error handling
        try:
            async for chunk in self.runner.run_stream(
                self.agent, query, context_id
            ):
                logger.info(f'Received chunk {chunk}')
                if isinstance(chunk, dict) and chunk.get('type') == 'final_result':
                    response = chunk['response']
                    yield self.get_agent_response(response)
                else:
                    yield {
                        'is_task_complete': False,
                        'require_user_input': False,
                        'content': f'{self.agent_name}: Processing Request...',
                    }
        except Exception as e:
            logger.error(
                f'Error in {self.agent_name} stream: {e}',
                exc_info=True
            )
            # Yield an error response
            yield {
                'response_type': 'text',
                'is_task_complete': True,
                'require_user_input': False,
                'content': f'Error processing request: {str(e)}',
            }

    def format_response(self, chunk):
        patterns = [
            r'```\n(.*?)\n```',
            r'```json\s*(.*?)\s*```',
            r'```tool_outputs\s*(.*?)\s*```',
        ]

        for pattern in patterns:
            match = re.search(pattern, chunk, re.DOTALL)
            if match:
                content = match.group(1)
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return content
        return chunk

    def get_agent_response(self, chunk):
        logger.info(f'Response Type {type(chunk)}')
        data = self.format_response(chunk)
        logger.info(f'Formatted Response {data}')
        try:
            if isinstance(data, dict):
                if 'status' in data and data['status'] == 'input_required':
                    return {
                        'response_type': 'text',
                        'is_task_complete': False,
                        'require_user_input': True,
                        'content': data['question'],
                    }
                return {
                    'response_type': 'data',
                    'is_task_complete': True,
                    'require_user_input': False,
                    'content': data,
                }
            return_type = 'data'
            try:
                data = json.loads(data)
                return_type = 'data'
            except Exception as json_e:
                logger.error(f'Json conversion error {json_e}')
                return_type = 'text'
            return {
                'response_type': return_type,
                'is_task_complete': True,
                'require_user_input': False,
                'content': data,
            }
        except Exception as e:
            logger.error(f'Error in get_agent_response: {e}')
            return {
                'response_type': 'text',
                'is_task_complete': True,
                'require_user_input': False,
                'content': 'Could not complete calendar management request. Please try again.',
            }

