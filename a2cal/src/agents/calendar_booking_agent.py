# type: ignore

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from collections.abc import AsyncIterable

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


class CalendarBookingAgent(BaseAgent):
    """Calendar Booking Agent backed by ADK."""

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

        logger.info(f'Init {self.agent_name}')

        self.instructions = instructions
        self.agent = None
        self.autonomous_mode = False
        self.conversation_state: Dict[str, Any] = {}

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
                'content': 'Could not complete calendar booking. Please try again.',
            }
    
    async def continue_autonomously(
        self,
        target_endpoint: str,
        target_did: str,
        preferences,
        conversation_history: List[Dict],
        context_id: Optional[str] = None,
        max_turns: int = 5
    ) -> Dict[str, Any]:
        """
        Continue the booking conversation autonomously.
        
        The agent manages its own conversation loop, sending messages directly
        to the target agent and analyzing responses to determine next steps.
        
        Args:
            target_endpoint: A2A endpoint URL of the target agent
            target_did: DID of the target agent
            preferences: MeetingPreferences object
            conversation_history: List of previous conversation turns
            context_id: Optional context ID for conversation continuity
            max_turns: Maximum number of turns to continue (default: 5)
            
        Returns:
            Dict with keys:
                - success: bool
                - message: str
                - conversation_history: List[Dict]
                - booking_details: Optional[Dict]
        """
        logger.info("="*80)
        logger.info("🤖 AGENT AUTONOMOUS MODE - Starting")
        logger.info(f"Target: {target_did} at {target_endpoint}")
        logger.info(f"Max turns: {max_turns}")
        logger.info("="*80)
        
        # Also print to console for visibility
        import sys
        print("\n" + "="*80, flush=True)
        print("[CalendarBookingAgent] 🤖 AGENT AUTONOMOUS MODE - Starting", flush=True)
        print(f"[CalendarBookingAgent] Target: {target_did} at {target_endpoint}", flush=True)
        print(f"[CalendarBookingAgent] Max turns: {max_turns}", flush=True)
        print("="*80 + "\n", flush=True)
        sys.stdout.flush()
        
        # Log start time for debugging
        import time
        start_time = time.time()
        logger.info(f"Autonomous mode start time: {start_time}")
        
        self.autonomous_mode = True
        autonomous_history = []
        current_context_id = context_id
        
        # Build initial context from conversation history
        context_parts = [
            "You are now in autonomous mode, managing the booking conversation directly.",
            f"Target Agent DID: {target_did}",
            f"Target Agent Endpoint: {target_endpoint}",
            "",
            "Previous Conversation:"
        ]
        
        for turn in conversation_history:
            context_parts.append(f"Turn {turn.get('turn', '?')}:")
            context_parts.append(f"  You sent: {turn.get('sent', '')}")
            context_parts.append(f"  Target responded: {turn.get('received', '')}")
            context_parts.append("")
        
        context_parts.extend([
            "Meeting Preferences:",
            preferences.to_natural_language() if hasattr(preferences, 'to_natural_language') else str(preferences),
            "",
            "Your goal: Continue the conversation to complete the booking.",
            "You can send messages directly to the target agent and analyze their responses.",
            "Continue until the booking is confirmed or you need to stop."
        ])
        
        conversation_context = "\n".join(context_parts)
        
        # Initialize agent if needed
        if not self.agent:
            logger.info("Agent not initialized - initializing now...")
            print("[CalendarBookingAgent] ⚠️ Agent not initialized - calling init_agent()...", flush=True)
            import sys
            import time
            sys.stdout.flush()
            init_start = time.time()
            try:
                print(f"[CalendarBookingAgent] Calling init_agent() with 30s timeout...", flush=True)
                sys.stdout.flush()
                await asyncio.wait_for(self.init_agent(), timeout=30.0)
                init_elapsed = time.time() - init_start
                logger.info(f"✅ Agent initialized successfully for autonomous mode (took {init_elapsed:.2f}s)")
                print(f"[CalendarBookingAgent] ✅ Agent initialized successfully (took {init_elapsed:.2f}s)", flush=True)
                sys.stdout.flush()
            except asyncio.TimeoutError:
                init_elapsed = time.time() - init_start
                error_msg = f"Agent initialization timed out after {init_elapsed:.2f}s (timeout was 30s)"
                logger.error(error_msg)
                print(f"[CalendarBookingAgent] ❌ {error_msg}", flush=True)
                sys.stdout.flush()
                return {
                    'success': False,
                    'message': error_msg,
                    'conversation_history': [],
                    'booking_details': None
                }
            except Exception as e:
                logger.error(f"Failed to initialize agent for autonomous mode: {e}", exc_info=True)
                return {
                    'success': False,
                    'message': f'Failed to initialize agent: {str(e)}',
                    'conversation_history': [],
                    'booking_details': None
                }
        
        # Autonomous conversation loop
        for turn in range(1, max_turns + 1):
            logger.info(f"🤖 Autonomous Turn {turn}/{max_turns}")
            print(f"[CalendarBookingAgent] 🤖 Starting Autonomous Turn {turn}/{max_turns}")
            
            try:
                # Ask agent to formulate next message
                agent_prompt = f"""{conversation_context}

Current Turn: {turn}/{max_turns}

Based on the conversation so far, formulate your next message to the target agent.
Your message should:
1. Address any questions or requests from the target agent
2. Provide any needed information
3. Move toward confirming the booking
4. Be professional and clear

Generate ONLY the message you want to send. Do not include explanations."""
                
                # Get agent's message
                agent_response = None
                
                logger.info(f"Turn {turn}: Formulating message...")
                print(f"[CalendarBookingAgent] Turn {turn}: Asking agent to formulate message...")
                
                async def get_agent_message():
                    nonlocal agent_response
                    logger.info(f"Turn {turn}: Starting stream() call...")
                    print(f"[CalendarBookingAgent] Turn {turn}: Calling self.stream()...")
                    async for chunk in self.stream(
                        agent_prompt,
                        f"autonomous_{datetime.now().timestamp()}",
                        f"turn_{turn}"
                    ):
                        logger.debug(f"Turn {turn}: Received chunk: {chunk}")
                        if chunk.get('is_task_complete'):
                            agent_response = chunk.get('content')
                            logger.info(f"Turn {turn}: Agent response received")
                            print(f"[CalendarBookingAgent] Turn {turn}: ✅ Agent response received")
                            break
                
                try:
                    print(f"[CalendarBookingAgent] Turn {turn}: Waiting for agent response (timeout: 15s)...")
                    await asyncio.wait_for(get_agent_message(), timeout=15.0)
                    print(f"[CalendarBookingAgent] Turn {turn}: ✅ Agent response completed")
                except asyncio.TimeoutError:
                    logger.error(f"Turn {turn}: Agent timed out formulating message")
                    return {
                        'success': False,
                        'message': f'Agent timed out on turn {turn}',
                        'conversation_history': autonomous_history,
                        'booking_details': None
                    }
                
                if not agent_response:
                    logger.error(f"Turn {turn}: Agent did not provide a message")
                    return {
                        'success': False,
                        'message': f'Agent did not provide a message on turn {turn}',
                        'conversation_history': autonomous_history,
                        'booking_details': None
                    }
                
                # Extract message to send
                message_to_send = self._extract_autonomous_message(agent_response)
                logger.info(f"Turn {turn}: Sending: {message_to_send[:100]}...")
                print(f"[CalendarBookingAgent] Turn {turn}: 📤 Extracted message: {message_to_send[:100]}...")
                
                # Send message to target agent
                try:
                    print(f"[CalendarBookingAgent] Turn {turn}: 📤 Sending message to target agent...")
                    response_text, new_context_id = await self._send_message_to_target(
                        message=message_to_send,
                        endpoint=target_endpoint,
                        context_id=current_context_id
                    )
                    print(f"[CalendarBookingAgent] Turn {turn}: 📥 Response received (length: {len(response_text)} chars)")
                    
                    if new_context_id:
                        current_context_id = new_context_id
                    
                    logger.info(f"Turn {turn}: Received response: {response_text[:200]}...")
                    
                    # Record turn
                    autonomous_history.append({
                        'turn': len(conversation_history) + turn,
                        'sent': message_to_send,
                        'received': response_text,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    # Update conversation context
                    conversation_context += f"\n\nTurn {len(conversation_history) + turn}:\nYou sent: {message_to_send}\nTarget responded: {response_text}"
                    
                    # Analyze response
                    analysis = self._analyze_target_response(response_text)
                    
                    if analysis.get('is_complete'):
                        logger.info("✅ Booking complete!")
                        return {
                            'success': True,
                            'message': analysis.get('message', 'Booking confirmed'),
                            'conversation_history': autonomous_history,
                            'booking_details': analysis.get('booking_details')
                        }
                    
                    elif analysis.get('is_error'):
                        logger.warning(f"❌ Error detected: {analysis.get('message')}")
                        return {
                            'success': False,
                            'message': analysis.get('message', 'Booking failed'),
                            'conversation_history': autonomous_history,
                            'booking_details': None
                        }
                    
                    # Continue to next turn
                    logger.info(f"Turn {turn}: Continuing conversation...")
                    
                except asyncio.TimeoutError:
                    logger.error(f"Turn {turn}: Target agent timed out")
                    return {
                        'success': False,
                        'message': f'Target agent timed out on turn {turn}',
                        'conversation_history': autonomous_history,
                        'booking_details': None
                    }
                except Exception as e:
                    logger.error(f"Turn {turn}: Error communicating with target: {e}", exc_info=True)
                    return {
                        'success': False,
                        'message': f'Communication error on turn {turn}: {str(e)}',
                        'conversation_history': autonomous_history,
                        'booking_details': None
                    }
                    
            except Exception as e:
                logger.error(f"Error in autonomous turn {turn}: {e}", exc_info=True)
                return {
                    'success': False,
                    'message': f'Error on turn {turn}: {str(e)}',
                    'conversation_history': autonomous_history,
                    'booking_details': None
                }
        
        # Max turns reached
        logger.warning(f"⚠️ Max turns ({max_turns}) reached without completion")
        return {
            'success': False,
            'message': f'Booking incomplete after {max_turns} autonomous turns',
            'conversation_history': autonomous_history,
            'booking_details': None
        }
    
    def _extract_autonomous_message(self, agent_response: Any) -> str:
        """Extract the message to send from agent's response."""
        if isinstance(agent_response, dict):
            if 'question' in agent_response:
                return agent_response['question']
            if 'message' in agent_response:
                return agent_response['message']
            if 'text' in agent_response:
                return agent_response['text']
            return json.dumps(agent_response)
        elif isinstance(agent_response, str):
            return agent_response
        else:
            return str(agent_response)
    
    async def _send_message_to_target(
        self,
        message: str,
        endpoint: str,
        context_id: Optional[str] = None
    ) -> tuple[str, Optional[str]]:
        """
        Send a message to the target agent via A2A.
        
        Args:
            message: Message text to send
            endpoint: A2A endpoint URL
            context_id: Optional context ID for conversation continuity
            
        Returns:
            Tuple of (response_text, new_context_id)
        """
        from a2a_client.client import send_message_to_a2a_agent
        
        logger.info(f"📤 Sending message to {endpoint} (context_id: {context_id})")
        
        try:
            response_text, new_context_id = await asyncio.wait_for(
                send_message_to_a2a_agent(
                    endpoint_url=endpoint,
                    message_text=message,
                    context_id=context_id
                ),
                timeout=15.0
            )
            
            logger.info(f"📥 Received response (length: {len(response_text)} chars)")
            return response_text, new_context_id
            
        except asyncio.TimeoutError:
            logger.error("⏱️ Timeout waiting for target agent response")
            raise
        except Exception as e:
            logger.error(f"❌ Error sending message: {e}", exc_info=True)
            raise
    
    def _analyze_target_response(self, response: str) -> Dict[str, Any]:
        """
        Analyze the target agent's response to determine next action.
        
        Args:
            response: Response text from target agent
            
        Returns:
            Dict with keys:
                - is_complete: bool
                - is_error: bool
                - message: str
                - booking_details: Optional[Dict]
        """
        response_lower = response.lower()
        
        # Check for completion indicators
        completion_keywords = [
            'booking confirmed',
            'meeting scheduled',
            'event created',
            'successfully booked',
            'confirmed for',
            'meeting is set',
            'scheduled for',
            'confirmed'
        ]
        
        for keyword in completion_keywords:
            if keyword in response_lower:
                return {
                    'is_complete': True,
                    'is_error': False,
                    'message': 'Booking confirmed',
                    'booking_details': {
                        'confirmation_message': response,
                        'timestamp': datetime.now().isoformat()
                    }
                }
        
        # Check for error indicators
        error_keywords = [
            'cannot book',
            'unable to',
            'failed to',
            'error',
            'not available',
            'conflict',
            'no available slots',
            'declined',
            'rejected'
        ]
        
        for keyword in error_keywords:
            if keyword in response_lower:
                return {
                    'is_complete': False,
                    'is_error': True,
                    'message': response[:200],
                    'booking_details': None
                }
        
        # Still processing
        return {
            'is_complete': False,
            'is_error': False,
            'message': 'Conversation continuing',
            'booking_details': None
        }