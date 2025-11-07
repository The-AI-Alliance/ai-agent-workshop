"""
Automated A2A booking flow for scheduling meetings.

This module handles the automatic conversation flow between a booking agent
and a target agent to schedule a meeting.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from a2a_client.client import send_message_to_a2a_agent
 

# Configure dedicated file logger for booking automation
booking_log_file = Path("/tmp/booking_automation.log")
file_handler = logging.FileHandler(booking_log_file, mode='w')  # Overwrite each run
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    '%(asctime)s - [%(levelname)s] - %(message)s',
    datefmt='%H:%M:%S'
)
file_handler.setFormatter(file_formatter)

logger = logging.getLogger(__name__)
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)

# Also log to console with flush
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter('[BookingAutomation] %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# Log to file immediately on module load
logger.info("="*80)
logger.info("📋 BOOKING AUTOMATION MODULE LOADED")
logger.info(f"📁 Log file: {booking_log_file}")
logger.info("="*80)


@dataclass
class MeetingPreferences:
    """User's meeting preferences."""
    date: Optional[str] = None  # e.g., "tomorrow", "2025-11-07"
    time: Optional[str] = None  # e.g., "2pm", "14:00"
    duration: Optional[int] = None  # in minutes
    title: Optional[str] = None
    description: Optional[str] = None
    partner_agent_id: Optional[str] = None  # The DID of the agent to book with
    
    def to_natural_language(self) -> str:
        """Convert preferences to natural language for the agent."""
        parts = []
        
        if self.title:
            parts.append(f"Meeting title: {self.title}")
        
        if self.description:
            parts.append(f"Description: {self.description}")
        
        if self.date:
            parts.append(f"Date: {self.date}")
        
        if self.time:
            parts.append(f"Time: {self.time}")
        
        if self.duration:
            parts.append(f"Duration: {self.duration} minutes")
        
        if self.partner_agent_id:
            parts.append(f"Partner agent: {self.partner_agent_id}")
        
        if not parts:
            return "Schedule a meeting"
        
        return ". ".join(parts) + "."


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""
    turn_number: int
    message_sent: str
    response_received: str
    timestamp: datetime
    metadata: Dict[str, Any]


class BookingAutomation:
    """
    Handles automated booking flow between agents.
    
    This class manages the multi-turn conversation needed to book a meeting
    with a target agent via A2A protocol.
    """
    
    def __init__(self, max_turns: int = 5):
        """
        Initialize booking automation.
        
        Args:
            max_turns: Maximum number of conversation turns (default: 5)
        """
        self.max_turns = max_turns
        self.conversation_history: List[ConversationTurn] = []
        self.current_turn = 0
        self.booking_complete = False
        self.booking_result = None
    
    async def _safe_progress_callback(
        self,
        progress_callback: Optional[callable],
        turn: int,
        status: str,
        message: str,
        timeout: float = 0.5  # Very short timeout - 0.5 seconds
    ):
        """
        Safely call progress callback with timeout to prevent hanging.
        Uses a very short timeout and cancels immediately if it doesn't complete.
        
        Args:
            progress_callback: The callback function (may be None)
            turn: Turn number
            status: Status string
            message: Message string
            timeout: Timeout in seconds (default: 0.5)
        """
        if not progress_callback:
            return
        
        logger.debug(f"Calling progress callback (turn={turn}, status={status})...")
        print(f"[BookingAutomation] _safe_progress_callback: START (turn={turn}, status={status})", flush=True)
        import sys
        sys.stdout.flush()
        
        # For handover status, skip the callback entirely to avoid blocking
        # The UI will update from the handover message anyway
        if status == "handover":
            logger.info(f"Skipping progress callback for handover status to avoid blocking")
            print(f"[BookingAutomation] _safe_progress_callback: SKIPPING handover callback to avoid blocking", flush=True)
            sys.stdout.flush()
            return
        
        # Create a task with timeout
        task = None
        try:
            print(f"[BookingAutomation] _safe_progress_callback: Creating task...", flush=True)
            sys.stdout.flush()
            logger.debug("calling progress_callback(turn, status, message)")
            task = asyncio.create_task(progress_callback(turn, status, message))
            logger.debug("task created successfully")
            
            print(f"[BookingAutomation] _safe_progress_callback: Task created, waiting with timeout={timeout}s...", flush=True)
            sys.stdout.flush()
            
            # Wait with timeout
            await asyncio.wait_for(task, timeout=timeout)
            
            logger.debug(f"✓ Progress callback completed")
            print(f"[BookingAutomation] _safe_progress_callback: ✓ Completed", flush=True)
            sys.stdout.flush()
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ Progress callback timed out after {timeout}s - cancelling")
            print(f"[BookingAutomation] _safe_progress_callback: ⚠️ TIMEOUT - cancelling", flush=True)
            sys.stdout.flush()
            if task and not task.done():
                task.cancel()
        except Exception as e:
            logger.warning(f"⚠️ Progress callback error (turn={turn}, status={status}): {e} - continuing")
            logger.error(f"error: {e}")
            print(f"[BookingAutomation] _safe_progress_callback: ⚠️ ERROR: {e}", flush=True)
            sys.stdout.flush()
        
        print(f"[BookingAutomation] _safe_progress_callback: END", flush=True)
        sys.stdout.flush()
        
    async def book_meeting(
        self,
        target_agent_endpoint: str,
        target_agent_did: str,
        preferences: MeetingPreferences,
        booking_agent,
        progress_callback: Optional[callable] = None,
        overall_timeout: float = 120.0  # 2 minutes overall timeout
    ) -> Dict[str, Any]:
        """
        Automatically book a meeting with the target agent using a BookingAgent.
        
        The BookingAgent acts as an intelligent intermediary that:
        - Understands your preferences
        - Negotiates with the target agent via A2A
        - Finds the best match based on availability
        - Handles multi-turn conversations intelligently
        
        Args:
            target_agent_endpoint: A2A endpoint URL of the target agent
            target_agent_did: DID of the target agent
            preferences: Meeting preferences to share
            booking_agent: CalendarBookingAgent instance to use for intelligent booking
            progress_callback: Optional callback for progress updates
                               Signature: callback(turn: int, status: str, message: str)
        
        Returns:
            Dict containing booking result with keys:
                - success: bool
                - message: str
                - conversation_history: List[ConversationTurn]
                - booking_details: Optional[Dict]
        """
        logger.info("="*80)
        logger.info("🎯 book_meeting() FUNCTION CALLED!")
        logger.info("="*80)
        logger.info("Parameters received:")
        logger.info(f"  - target_agent_endpoint: {target_agent_endpoint}")
        logger.info(f"  - target_agent_did: {target_agent_did}")
        logger.info(f"  - preferences: {preferences}")
        logger.info(f"  - booking_agent: {booking_agent}")
        logger.info(f"  - progress_callback: {progress_callback}")
        logger.info(f"  - overall_timeout: {overall_timeout}s")
        
        logger.info(f"Starting automated booking flow with {target_agent_endpoint}")
        logger.info(f"Using BookingAgent: {booking_agent.agent_name}")
        logger.info(f"✓ Logger statements executed")
        
        # Wrap entire function in timeout to prevent indefinite hangs
        async def _book_meeting_internal():
            # Build the context for the booking agent
            logger.info(f"Building booking context...")
            booking_context = self._build_booking_context(preferences, target_agent_did)
            logger.info(f"✓ Booking context built")
        
            logger.info(f"Checking if progress_callback is provided...")
            await self._safe_progress_callback(
                progress_callback,
                0,
                "starting",
                "Initiating AI-powered booking..."
            )
            
            # Initialize booking agent if needed
            logger.info(f"Checking if booking agent needs initialization...")
            logger.info(f"booking_agent.agent = {booking_agent.agent}")
            if not booking_agent.agent:
                logger.info(f"Booking agent needs initialization")
                await self._safe_progress_callback(
                    progress_callback,
                    0,
                    "initializing",
                    "Initializing booking agent..."
                )
                
                try:
                    # Add timeout to prevent hanging
                    logger.info("Initializing booking agent with 30s timeout...")
                    logger.info(f"Calling booking_agent.init_agent() with 30s timeout...")
                    await asyncio.wait_for(booking_agent.init_agent(), timeout=30.0)
                    logger.info("Booking agent initialized successfully")
                    logger.info(f"✅ Booking agent initialized successfully")
                except asyncio.TimeoutError:
                    error_msg = "Booking agent initialization timed out after 30 seconds. Check MCP server connection."
                    logger.error(error_msg)
                    return {
                        'success': False,
                        'message': error_msg,
                        'conversation_history': [],
                        'booking_details': None
                    }
                except Exception as e:
                    error_msg = f"Failed to initialize booking agent: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    return {
                        'success': False,
                        'message': error_msg,
                        'conversation_history': [],
                        'booking_details': None
                    }
            else:
                logger.info(f"✓ Booking agent already initialized, skipping init")
            
            # Conversation loop - BookingAgent talks to target agent
            logger.info(f"Building conversation context...")
            conversation_context = f"{booking_context}\n\nTarget Agent A2A Endpoint: {target_agent_endpoint}\nTarget Agent DID: {target_agent_did}"
            logger.info(f"✓ Conversation context built")
            logger.info(f"🔄 ENTERING MAIN CONVERSATION LOOP (max_turns={self.max_turns})...")
            
            for turn in range(1, self.max_turns + 1):
                self.current_turn = turn
                logger.info(f"========== STARTING TURN {turn}/{self.max_turns} ==========")
                
                try:
                    # Ask booking agent to formulate the message
                    await self._safe_progress_callback(
                        progress_callback,
                        turn,
                        "thinking",
                        f"Turn {turn}/{self.max_turns}: Booking agent is analyzing..."
                    )
                    logger.info(f"Turn {turn}: Progress callback done, building prompt...")
                    
                    # Build prompt for booking agent
                    agent_prompt = self._build_agent_prompt(turn, conversation_context, target_agent_did)
                    
                    logger.info(f"Turn {turn}: Asking booking agent to formulate message...")
                    logger.info(f"Turn {turn}: Asking booking agent to formulate message...")
                    
                    # Get booking agent's intelligent response with timeout
                    booking_agent_response = None
                    
                    async def get_agent_response():
                        nonlocal booking_agent_response
                        logger.info(f"Turn {turn}: Starting to stream from booking agent...")
                        async for chunk in booking_agent.stream(agent_prompt, f"auto_booking_{datetime.now().timestamp()}", f"turn_{turn}"):
                            logger.debug(f"Turn {turn}: Received chunk from booking agent: {chunk}")
                            logger.info(f"Turn {turn}: Received chunk: {chunk.get('is_task_complete', False)}")
                            if chunk.get('is_task_complete'):
                                booking_agent_response = chunk.get('content')
                                logger.info(f"Turn {turn}: Booking agent suggests: {str(booking_agent_response)[:200]}...")
                                logger.info(f"Turn {turn}: Booking agent response received")
                                break
                    
                    try:
                        await asyncio.wait_for(get_agent_response(), timeout=10.0)
                    except asyncio.TimeoutError:
                        error_msg = f"Turn {turn}: Booking agent timed out while formulating response"
                        logger.error(error_msg)
                        logger.info(f"⏱️ TIMEOUT: Booking agent timed out after 10 seconds")
                        
                        await self._safe_progress_callback(
                            progress_callback,
                            turn,
                            "timeout",
                            f"⏱️ Booking agent timed out (10s)"
                        )
                        
                        return {
                            'success': False,
                            'message': f'Booking agent timed out on turn {turn}. Could not formulate message within 10 seconds.',
                            'conversation_history': self.conversation_history,
                            'booking_details': None
                        }
                    
                    if not booking_agent_response:
                        error_msg = f"Turn {turn}: Booking agent did not provide a response"
                        logger.error(error_msg)
                        raise Exception(error_msg)
                    
                    # Check if agent wants to take over (handover request)
                    handover_requested = await self._check_for_handover(booking_agent_response)
                    if handover_requested:
                        logger.info(f"Turn {turn}: 🤖 Agent requested handover - transferring control NOW.")
                        logger.info(f"Updating progress callback to handover...")
                        print(f"[BookingAutomation] Turn {turn}: About to call _safe_progress_callback for handover...", flush=True)
                        import sys
                        sys.stdout.flush()
                        
                        # Try to call progress callback with very short timeout
                        # If it hangs, we'll skip it and continue
                        try:
                            await asyncio.wait_for(
                                self._safe_progress_callback(
                                    progress_callback,
                                    turn,
                                    "handover",
                                    f"🤖 Agent taking over - continuing autonomously..."
                                ),
                                timeout=1.0  # Max 1 second total for the whole callback attempt
                            )
                            logger.info(f"✓ Progress callback updated to handover (or timed out)")
                            print(f"[BookingAutomation] Turn {turn}: ✓ _safe_progress_callback completed", flush=True)
                        except asyncio.TimeoutError:
                            logger.warning(f"⚠️ _safe_progress_callback itself timed out - skipping and continuing")
                            print(f"[BookingAutomation] ⚠️ _safe_progress_callback timed out - skipping", flush=True)
                        except Exception as e:
                            logger.warning(f"⚠️ _safe_progress_callback error: {e} - skipping and continuing")
                            print(f"[BookingAutomation] ⚠️ _safe_progress_callback error: {e} - skipping", flush=True)
                        
                        sys.stdout.flush()
                        
                    # Handover to agent for autonomous continuation
                    logger.info(f"Turn {turn}: About to call _handover_to_agent()...")
                    print(f"[BookingAutomation] Turn {turn}: About to call _handover_to_agent()...")
                    import sys
                    sys.stdout.flush()  # Force flush
                    
                    handover_result = await self._handover_to_agent(
                        booking_agent=booking_agent,
                        target_agent_endpoint=target_agent_endpoint,
                        target_agent_did=target_agent_did,
                        preferences=preferences,
                        conversation_context=conversation_context
                    )
                    
                    logger.info(f"Turn {turn}: _handover_to_agent() completed")
                    print(f"[BookingAutomation] Turn {turn}: _handover_to_agent() completed")
                    
                    # Merge handover conversation history with existing
                    if handover_result.get('conversation_history'):
                        # Convert handover history dicts to ConversationTurn objects
                        for turn_dict in handover_result['conversation_history']:
                            turn_obj = ConversationTurn(
                                turn_number=turn_dict.get('turn', len(self.conversation_history) + 1),
                                message_sent=turn_dict.get('sent', ''),
                                response_received=turn_dict.get('received', ''),
                                timestamp=datetime.fromisoformat(turn_dict.get('timestamp', datetime.now().isoformat())),
                                metadata={'autonomous': True}
                            )
                            self.conversation_history.append(turn_obj)
                    
                    return {
                        'success': handover_result.get('success', False),
                        'message': handover_result.get('message', 'Agent completed booking autonomously'),
                        'conversation_history': self.conversation_history,
                        'booking_details': handover_result.get('booking_details'),
                        'handover_occurred': True
                    }
                    
                    # Extract the message to send from booking agent's response
                    message_to_send = self._extract_message_from_agent_response(booking_agent_response)
                    
                    # Send message to target agent
                    await self._safe_progress_callback(
                        progress_callback,
                        turn,
                        "sending",
                        f"Turn {turn}/{self.max_turns}: Sending to target agent..."
                    )
                    
                    logger.info(f"Turn {turn}: Sending to target: {message_to_send[:100]}...")
                    logger.info(f"Turn {turn}: Sending to target agent at {target_agent_endpoint}")
                    logger.info(f"Turn {turn}: Message: {message_to_send[:100]}...")
                    
                    # Add timeout to prevent hanging on A2A communication
                    try:
                        logger.info(f"Turn {turn}: Calling send_message_to_a2a_agent...")
                        logger.info(f"Turn {turn}: Endpoint: {target_agent_endpoint}")
                        logger.info(f"Turn {turn}: Message length: {len(message_to_send)} chars")
                        logger.info(f"Turn {turn}: Message preview: {message_to_send[:100]}...")
                        logger.info(f"Turn {turn}: Waiting for A2A response (10s timeout)...")
                        
                        response_text, context_id = await asyncio.wait_for(
                            send_message_to_a2a_agent(
                                endpoint_url=target_agent_endpoint,
                                message_text=message_to_send,
                                context_id=getattr(self, '_target_agent_context_id', None)
                            ),
                            timeout=10.0  # 10 seconds for A2A response
                        )
                        
                        # Store context_id for conversation continuity across turns
                        if context_id:
                            self._target_agent_context_id = context_id
                            logger.info(f"Turn {turn}: ✅ Stored context_id for conversation: {context_id}")
                        
                        # Log response details
                        logger.info(f"Turn {turn}: ✅ Response received!")
                        logger.info(f"Turn {turn}: Response length: {len(response_text)} characters")
                        if response_text:
                            logger.info(f"Turn {turn}: Response preview: {response_text[:200]}...")
                            logger.info(f"Turn {turn}: Response (full): {response_text}")
                        else:
                            logger.warning(f"Turn {turn}: ⚠️ Response is empty or None!")
                            logger.warning(f"Turn {turn}: Response type: {type(response_text)}")
                            logger.warning(f"Turn {turn}: Response value: {repr(response_text)}")
                        
                        response = response_text  # Keep for backward compatibility with rest of code
                    except asyncio.TimeoutError:
                        error_msg = f"Turn {turn}: Target agent did not respond within 10 seconds"
                        logger.error(error_msg)
                        logger.info(f"⏱️ TIMEOUT: Target agent timed out after 10 seconds")
                        
                        await self._safe_progress_callback(
                            progress_callback,
                            turn,
                            "timeout",
                            f"⏱️ Target agent timed out (10s)"
                        )
                        
                        return {
                            'success': False,
                            'message': f'Target agent timed out on turn {turn}. No response received within 10 seconds.',
                            'conversation_history': self.conversation_history,
                            'booking_details': None
                        }
                    except Exception as e:
                        error_msg = f"Turn {turn}: Error communicating with target agent: {str(e)}"
                        logger.error(error_msg, exc_info=True)
                        
                        await self._safe_progress_callback(
                            progress_callback,
                            turn,
                            "error",
                            f"❌ Communication error"
                        )
                        
                        return {
                            'success': False,
                            'message': f'Communication error on turn {turn}: {str(e)}',
                            'conversation_history': self.conversation_history,
                            'booking_details': None
                        }
                    
                    # Record conversation turn
                    logger.info(f"Turn {turn}: Recording conversation turn...")
                    logger.info(f"Turn {turn}: Message sent length: {len(message_to_send)}")
                    logger.info(f"Turn {turn}: Response received length: {len(response) if response else 0}")
                    
                    conversation_turn = ConversationTurn(
                        turn_number=turn,
                        message_sent=message_to_send,
                        response_received=response or "",  # Ensure we always have a string
                        timestamp=datetime.now(),
                        metadata={
                            'booking_agent_analysis': str(booking_agent_response)[:500]
                        }
                    )
                    self.conversation_history.append(conversation_turn)
                    logger.info(f"Turn {turn}: ✅ Conversation turn recorded (history length: {len(self.conversation_history)})")
                    
                    # Update conversation context with the new exchange
                    response_text = response if response else "[No response received]"
                    conversation_context += f"\n\nTurn {turn}:\nYou sent: {message_to_send}\nTarget agent responded: {response_text}"
                    logger.info(f"Turn {turn}: ✅ Conversation context updated (context length: {len(conversation_context)} chars)")
                    
                    await self._safe_progress_callback(
                        progress_callback,
                        turn,
                        "received",
                        f"Turn {turn}/{self.max_turns}: Response received"
                    )
                    
                    # Analyze response and determine next action
                    analysis = self._analyze_response(response)
                    
                    if analysis['is_complete']:
                        # Booking is complete!
                        self.booking_complete = True
                        self.booking_result = analysis.get('booking_details')
                        
                        await self._safe_progress_callback(
                            progress_callback,
                            turn,
                            "complete",
                            f"✅ Booking complete! {analysis.get('message', '')}"
                        )
                        
                        return {
                            'success': True,
                            'message': analysis.get('message', 'Meeting booked successfully'),
                            'conversation_history': self.conversation_history,
                            'booking_details': self.booking_result
                        }
                    
                    elif analysis['is_error']:
                        # Error occurred
                        await self._safe_progress_callback(
                            progress_callback,
                            turn,
                            "error",
                            f"❌ Error: {analysis.get('message', 'Unknown error')}"
                        )
                        
                        return {
                            'success': False,
                            'message': analysis.get('message', 'Booking failed'),
                            'conversation_history': self.conversation_history,
                            'booking_details': None
                        }
                    
                    elif analysis['needs_more_info']:
                        # Agent needs more information
                        missing_info = analysis.get('missing_info', [])
                        
                        await self._safe_progress_callback(
                            progress_callback,
                            turn,
                            "info_needed",
                            f"ℹ️ Agent needs: {', '.join(missing_info)}"
                        )
                        
                        # Build next message with missing info
                        current_message = self._build_followup_message(
                            preferences,
                            missing_info,
                            response
                        )
                        
                        # Continue to next turn
                        continue
                    
                    else:
                        # Agent is still processing
                        await self._safe_progress_callback(
                            progress_callback,
                            turn,
                            "processing",
                            f"⏳ Agent is processing: {analysis.get('message', '')}"
                        )
                        
                        # Build acknowledgment message
                        current_message = self._build_acknowledgment_message(response)
                        
                        # Continue to next turn
                        continue
                
                except Exception as e:
                    logger.error(f"Error in turn {turn}: {e}", exc_info=True)
                    
                    await self._safe_progress_callback(
                        progress_callback,
                        turn,
                        "error",
                        f"❌ Error communicating with agent: {str(e)}"
                    )
                    
                    return {
                        'success': False,
                        'message': f'Communication error: {str(e)}',
                        'conversation_history': self.conversation_history,
                        'booking_details': None
                    }
        
            # Max turns reached without completion
            await self._safe_progress_callback(
                progress_callback,
                self.max_turns,
                "timeout",
                f"⚠️ Maximum turns ({self.max_turns}) reached without completing booking"
            )
            
            return {
                'success': False,
                'message': f'Booking incomplete after {self.max_turns} turns',
                'conversation_history': self.conversation_history,
                'booking_details': None
            }
        
        # Execute with overall timeout
        try:
            logger.info(f"⏱️ Starting book_meeting with overall timeout: {overall_timeout}s")
            return await asyncio.wait_for(_book_meeting_internal(), timeout=overall_timeout)
        except asyncio.TimeoutError:
            error_msg = f"Booking automation timed out after {overall_timeout} seconds"
            logger.error(error_msg)
            print(f"[BookingAutomation] ❌ {error_msg}")
            await self._safe_progress_callback(
                progress_callback,
                self.current_turn or self.max_turns,
                "timeout",
                f"⏱️ Overall timeout ({overall_timeout}s) exceeded"
            )
            return {
                'success': False,
                'message': error_msg,
                'conversation_history': self.conversation_history,
                'booking_details': None
            }
    
    def _build_booking_context(self, preferences: MeetingPreferences, target_agent_did: str) -> str:
        """Build the context for the booking agent."""
        context_parts = [
            "You are helping to automatically book a meeting with another agent.",
            f"Target Agent DID: {target_agent_did}",
            "",
            "Meeting Preferences:",
            preferences.to_natural_language(),
            "",
            "Your goal is to:",
            "1. Communicate clearly and professionally with the target agent",
            "2. Negotiate the best meeting time based on preferences",
            "3. Handle any questions or requests for additional information",
            "4. Confirm the booking once agreed upon",
            "",
            "Remember: You are representing a user who wants to schedule a meeting."
        ]
        return "\n".join(context_parts)
    
    def _build_agent_prompt(self, turn: int, conversation_context: str, target_agent_did: str) -> str:
        """Build the prompt for the booking agent at each turn."""
        handover_instruction = """

OPTIONAL HANDOVER: If you feel confident you can handle the rest of this conversation autonomously, you can request to take over. To do this, include in your response:
- A JSON object with {"handover": true, "reason": "brief explanation"}
- Then provide the message you want to send

If you don't request handover, just provide the message to send normally."""

        if turn == 1:
            # First turn - initial booking request
            prompt = f"""{conversation_context}

This is your first contact with the target agent. Craft a clear, professional booking request that includes:
1. A greeting
2. Your intent to schedule a meeting
3. The key preferences (date/time/duration if specified)
4. A polite request for their availability

Generate ONLY the message you want to send to the target agent. Do not include explanations or meta-commentary.{handover_instruction}"""
        else:
            # Subsequent turns - respond to target agent
            prompt = f"""{conversation_context}

Based on the target agent's latest response, formulate an appropriate reply that:
1. Addresses any questions they asked
2. Provides any requested information
3. Negotiates if needed
4. Moves toward confirming the booking

Generate ONLY the message you want to send to the target agent. Do not include explanations or meta-commentary.{handover_instruction}"""
        
        return prompt
    
    def _extract_message_from_agent_response(self, agent_response: Any) -> str:
        """Extract the actual message to send from the booking agent's response."""
        if isinstance(agent_response, dict):
            # If it's a dict with a question field (input required)
            if 'question' in agent_response:
                return agent_response['question']
            # If it has other fields, try to extract text
            if 'message' in agent_response:
                return agent_response['message']
            # Otherwise convert to JSON string
            import json
            return json.dumps(agent_response)
        elif isinstance(agent_response, str):
            return agent_response
        else:
            return str(agent_response)
    
    def _analyze_response(self, response: str) -> Dict[str, Any]:
        """
        Analyze the agent's response to determine next action.
        
        Returns:
            Dict with keys:
                - is_complete: bool - booking is complete
                - is_error: bool - an error occurred
                - needs_more_info: bool - agent needs more information
                - missing_info: List[str] - what information is missing
                - message: str - status message
                - booking_details: Optional[Dict] - booking confirmation details
        """
        response_lower = response.lower()
        
        # Check for completion indicators
        completion_keywords = [
            'booking confirmed',
            'meeting scheduled',
            'event created',
            'successfully booked',
            'confirmed for',
            'meeting is set'
        ]
        
        for keyword in completion_keywords:
            if keyword in response_lower:
                return {
                    'is_complete': True,
                    'is_error': False,
                    'needs_more_info': False,
                    'missing_info': [],
                    'message': 'Meeting booked successfully',
                    'booking_details': self._extract_booking_details(response)
                }
        
        # Check for error indicators
        error_keywords = [
            'cannot book',
            'unable to',
            'failed to',
            'error',
            'not available',
            'conflict',
            'no available slots'
        ]
        
        for keyword in error_keywords:
            if keyword in response_lower:
                return {
                    'is_complete': False,
                    'is_error': True,
                    'needs_more_info': False,
                    'missing_info': [],
                    'message': response[:200],
                    'booking_details': None
                }
        
        # Check for information requests
        missing_info = []
        
        if 'time' in response_lower and '?' in response:
            missing_info.append('time')
        if 'date' in response_lower and '?' in response:
            missing_info.append('date')
        if 'duration' in response_lower and '?' in response:
            missing_info.append('duration')
        if 'partner' in response_lower or 'agent id' in response_lower:
            missing_info.append('partner_agent_id')
        
        if missing_info:
            return {
                'is_complete': False,
                'is_error': False,
                'needs_more_info': True,
                'missing_info': missing_info,
                'message': f'Agent needs: {", ".join(missing_info)}',
                'booking_details': None
            }
        
        # Still processing
        return {
            'is_complete': False,
            'is_error': False,
            'needs_more_info': False,
            'missing_info': [],
            'message': 'Agent is processing request',
            'booking_details': None
        }
    
    def _extract_booking_details(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract booking confirmation details from response."""
        # TODO: Implement proper extraction logic based on response format
        # For now, return the full response as details
        return {
            'confirmation_message': response,
            'timestamp': datetime.now().isoformat()
        }
    
    async def _check_for_handover(self, agent_response: Any) -> bool:
        """
        Check if agent wants to take over the conversation.
        
        Args:
            agent_response: The agent's response (dict, str, or other)
            
        Returns:
            True if agent requested handover, False otherwise
        """
        import json
        import re
        
        # Convert response to string for parsing
        response_str = str(agent_response)
        
        # Look for JSON handover request
        # Pattern: {"handover": true, ...}
        handover_pattern = r'\{\s*["\']handover["\']\s*:\s*true'
        if re.search(handover_pattern, response_str, re.IGNORECASE):
            logger.info("✅ Handover request detected in agent response")
            return True
        
        # Try to parse as JSON if it's a dict or string
        try:
            if isinstance(agent_response, dict):
                if agent_response.get('handover') is True:
                    logger.info("✅ Handover request detected in agent response dict")
                    return True
            elif isinstance(agent_response, str):
                # Try to extract JSON from string
                json_match = re.search(r'\{[^{}]*"handover"[^{}]*\}', response_str, re.IGNORECASE)
                if json_match:
                    parsed = json.loads(json_match.group())
                    if parsed.get('handover') is True:
                        logger.info("✅ Handover request detected in agent response string")
                        return True
        except Exception as e:
            logger.debug(f"Error parsing handover request: {e}")
        
        return False
    
    async def _handover_to_agent(
        self,
        booking_agent,
        target_agent_endpoint: str,
        target_agent_did: str,
        preferences: MeetingPreferences,
        conversation_context: str
    ) -> Dict[str, Any]:
        """
        Handover control to the booking agent for autonomous continuation.
        
        Args:
            booking_agent: CalendarBookingAgent instance
            target_agent_endpoint: A2A endpoint of target agent
            target_agent_did: DID of target agent
            preferences: Meeting preferences
            conversation_context: Current conversation context
            
        Returns:
            Dict with booking result from agent's autonomous execution
        """
        logger.info("="*80)
        logger.info("🤖 HANDOVER TO AGENT - Starting autonomous mode")
        logger.info("="*80)
        print("\n" + "="*80, flush=True)
        print("[BookingAutomation] 🤖 HANDOVER TO AGENT - Starting autonomous mode", flush=True)
        print("="*80 + "\n", flush=True)
        import sys
        sys.stdout.flush()
        
        # Build conversation history for agent
        conversation_history = [
            {
                'turn': turn.turn_number,
                'sent': turn.message_sent,
                'received': turn.response_received,
                'timestamp': turn.timestamp.isoformat()
            }
            for turn in self.conversation_history
        ]
        
        # Get current context_id if available
        context_id = getattr(self, '_target_agent_context_id', None)
        
        try:
            # Check if agent has continue_autonomously method
            if hasattr(booking_agent, 'continue_autonomously'):
                logger.info("✅ Agent has continue_autonomously method - calling it")
                print("[BookingAutomation] ✅ Calling booking_agent.continue_autonomously()...", flush=True)
                print(f"[BookingAutomation] Parameters:", flush=True)
                print(f"  - target_endpoint: {target_agent_endpoint}", flush=True)
                print(f"  - target_did: {target_agent_did}", flush=True)
                print(f"  - max_turns: {self.max_turns - self.current_turn}", flush=True)
                print(f"  - context_id: {context_id}", flush=True)
                import sys
                sys.stdout.flush()
                
                # Add overall timeout for autonomous mode (45 seconds per remaining turn, max 20 seconds)
                remaining_turns = self.max_turns - self.current_turn
                autonomous_timeout = min(45.0 * remaining_turns, 20.0)  # Max 20 seconds total
                
                logger.info(f"⏱️ Setting autonomous mode timeout: {autonomous_timeout}s (for {remaining_turns} turns)")
                logger.debug(f"[BookingAutomation] ⏱️ Setting autonomous mode timeout: {autonomous_timeout}s")
                print(f"[BookingAutomation] ⏱️ Setting autonomous mode timeout: {autonomous_timeout}s", flush=True)
                
                logger.debug(f"[BookingAutomation] ⏳ About to await continue_autonomously()...")
                print(f"[BookingAutomation] ⏳ About to await continue_autonomously()...", flush=True)
                import sys
                sys.stdout.flush()
                
                # Create the coroutine first
                print(f"[BookingAutomation] Creating continue_autonomously coroutine...", flush=True)
                sys.stdout.flush()
                
                autonomous_coro = booking_agent.continue_autonomously(
                    target_endpoint=target_agent_endpoint,
                    target_did=target_agent_did,
                    preferences=preferences,
                    conversation_history=conversation_history,
                    context_id=context_id,
                    max_turns=remaining_turns
                )
                
                print(f"[BookingAutomation] ✓ Coroutine created, creating task...", flush=True)
                sys.stdout.flush()
                
                # Create a task so we can cancel it if needed
                autonomous_task = asyncio.create_task(autonomous_coro)
                
                print(f"[BookingAutomation] ✓ Task created, waiting with timeout={autonomous_timeout}s...", flush=True)
                sys.stdout.flush()
                
                # Use wait_for with timeout - track time manually in case wait_for doesn't work
                import time
                start_time = time.time()
                
                # Create a monitoring task that will check if we've exceeded timeout
                async def timeout_monitor():
                    await asyncio.sleep(autonomous_timeout + 0.5)  # Slightly longer than timeout
                    if not autonomous_task.done():
                        elapsed = time.time() - start_time
                        logger.error(f"⚠️ TIMEOUT MONITOR: Task still running after {elapsed:.2f}s (timeout was {autonomous_timeout}s)")
                        print(f"[BookingAutomation] ⚠️ TIMEOUT MONITOR: Task still running after {elapsed:.2f}s!", flush=True)
                        sys.stdout.flush()
                
                monitor_task = asyncio.create_task(timeout_monitor())
                
                try:
                    # Try wait_for first
                    print(f"[BookingAutomation] Awaiting autonomous_task with wait_for(timeout={autonomous_timeout}s)...", flush=True)
                    sys.stdout.flush()
                    result = await asyncio.wait_for(autonomous_task, timeout=autonomous_timeout)
                    elapsed = time.time() - start_time
                    monitor_task.cancel()  # Cancel monitor since we're done
                    logger.debug(f"[BookingAutomation] ✅ continue_autonomously() returned (took {elapsed:.2f}s)")
                    print(f"[BookingAutomation] ✅ continue_autonomously() returned (took {elapsed:.2f}s)", flush=True)
                    sys.stdout.flush()
                except asyncio.TimeoutError:
                    elapsed = time.time() - start_time
                    logger.error(f"❌ continue_autonomously() timed out after {elapsed:.2f}s (timeout was {autonomous_timeout}s)")
                    print(f"[BookingAutomation] ❌ TIMEOUT: continue_autonomously() timed out after {elapsed:.2f}s", flush=True)
                    sys.stdout.flush()
                    monitor_task.cancel()
                    # Cancel the task aggressively
                    if not autonomous_task.done():
                        autonomous_task.cancel()
                        # Don't wait for cancellation - just raise immediately
                    raise
                except Exception as e:
                    elapsed = time.time() - start_time
                    logger.error(f"❌ continue_autonomously() error after {elapsed:.2f}s: {e}", exc_info=True)
                    print(f"[BookingAutomation] ❌ ERROR: continue_autonomously() failed after {elapsed:.2f}s: {e}", flush=True)
                    sys.stdout.flush()
                    monitor_task.cancel()
                    raise
                finally:
                    # Always cancel monitor
                    if not monitor_task.done():
                        monitor_task.cancel()
                
                logger.info(f"✅ Agent autonomous mode completed: success={result.get('success')}, message={result.get('message')[:100]}")
                logger.info(f"Result: success={result.get('success')}, message={result.get('message')[:100]}")
                
                return result
            else:
                # Fallback: agent doesn't support autonomous mode yet
                logger.warning("⚠️ Agent doesn't support autonomous mode - falling back to orchestrated mode")
                return {
                    'success': False,
                    'message': 'Agent does not support autonomous mode yet',
                    'conversation_history': [],
                    'booking_details': None
                }
        except asyncio.TimeoutError as e:
            # autonomous_timeout might not be in scope if timeout happens before it's set
            timeout_duration = getattr(e, 'timeout', 'unknown')
            error_msg = f"Agent autonomous mode timed out after {timeout_duration}s"
            logger.error(error_msg)
            print(f"[BookingAutomation] ❌ {error_msg}")
            return {
                'success': False,
                'message': error_msg,
                'conversation_history': [],
                'booking_details': None
            }
        except Exception as e:
            logger.error(f"❌ Error in agent autonomous mode: {e}", exc_info=True)
            print(f"[BookingAutomation] ❌ Error in agent autonomous mode: {e}")
            return {
                'success': False,
                'message': f'Error in agent autonomous mode: {str(e)}',
                'conversation_history': [],
                'booking_details': None
            }
    
    def get_conversation_summary(self) -> str:
        """Get a formatted summary of the conversation."""
        if not self.conversation_history:
            return "No conversation yet."
        
        summary_parts = [f"Conversation Summary ({len(self.conversation_history)} turns):"]
        summary_parts.append("=" * 60)
        
        for turn in self.conversation_history:
            summary_parts.append(f"\n🔵 Turn {turn.turn_number} ({turn.timestamp.strftime('%H:%M:%S')})")
            summary_parts.append(f"   📤 Sent: {turn.message_sent[:100]}...")
            summary_parts.append(f"   📥 Received: {turn.response_received[:100]}...")
        
        return "\n".join(summary_parts)

