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

logger = logging.getLogger(__name__)


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
        
    async def book_meeting(
        self,
        target_agent_endpoint: str,
        target_agent_did: str,
        preferences: MeetingPreferences,
        booking_agent,
        progress_callback: Optional[callable] = None
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
        logger.info(f"Starting automated booking flow with {target_agent_endpoint}")
        logger.info(f"Using BookingAgent: {booking_agent.agent_name}")
        
        # Import here to avoid circular dependencies
        try:
            from a2a_client.client import send_message_to_a2a_agent
        except ImportError as e:
            logger.error(f"Failed to import A2A client: {e}")
            return {
                'success': False,
                'message': f'A2A client not available: {str(e)}',
                'conversation_history': [],
                'booking_details': None
            }
        
        # Build the context for the booking agent
        booking_context = self._build_booking_context(preferences, target_agent_did)
        
        if progress_callback:
            await progress_callback(0, "starting", "Initiating AI-powered booking...")
        
        # Initialize booking agent if needed
        if not booking_agent.agent:
            if progress_callback:
                await progress_callback(0, "initializing", "Initializing booking agent...")
            
            try:
                # Add timeout to prevent hanging
                logger.info("Initializing booking agent with 30s timeout...")
                await asyncio.wait_for(booking_agent.init_agent(), timeout=30.0)
                logger.info("Booking agent initialized successfully")
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
        
        # Conversation loop - BookingAgent talks to target agent
        conversation_context = f"{booking_context}\n\nTarget Agent A2A Endpoint: {target_agent_endpoint}\nTarget Agent DID: {target_agent_did}"
        
        for turn in range(1, self.max_turns + 1):
            self.current_turn = turn
            print(f"\n[BookingAutomation] ========== STARTING TURN {turn}/{self.max_turns} ==========")
            
            try:
                # Ask booking agent to formulate the message
                if progress_callback:
                    await progress_callback(
                        turn,
                        "thinking",
                        f"Turn {turn}/{self.max_turns}: Booking agent is analyzing..."
                    )
                print(f"[BookingAutomation] Turn {turn}: Progress callback done, building prompt...")
                
                # Build prompt for booking agent
                agent_prompt = self._build_agent_prompt(turn, conversation_context, target_agent_did)
                
                logger.info(f"Turn {turn}: Asking booking agent to formulate message...")
                print(f"[BookingAutomation] Turn {turn}: Asking booking agent to formulate message...")
                
                # Get booking agent's intelligent response with timeout
                booking_agent_response = None
                
                async def get_agent_response():
                    nonlocal booking_agent_response
                    print(f"[BookingAutomation] Turn {turn}: Starting to stream from booking agent...")
                    async for chunk in booking_agent.stream(agent_prompt, f"auto_booking_{datetime.now().timestamp()}", f"turn_{turn}"):
                        logger.debug(f"Turn {turn}: Received chunk from booking agent: {chunk}")
                        print(f"[BookingAutomation] Turn {turn}: Received chunk: {chunk.get('is_task_complete', False)}")
                        if chunk.get('is_task_complete'):
                            booking_agent_response = chunk.get('content')
                            logger.info(f"Turn {turn}: Booking agent suggests: {str(booking_agent_response)[:200]}...")
                            print(f"[BookingAutomation] Turn {turn}: Booking agent response received")
                            break
                
                try:
                    await asyncio.wait_for(get_agent_response(), timeout=10.0)
                except asyncio.TimeoutError:
                    error_msg = f"Turn {turn}: Booking agent timed out while formulating response"
                    logger.error(error_msg)
                    print(f"[BookingAutomation] ⏱️ TIMEOUT: Booking agent timed out after 10 seconds")
                    
                    if progress_callback:
                        await progress_callback(
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
                
                # Extract the message to send from booking agent's response
                message_to_send = self._extract_message_from_agent_response(booking_agent_response)
                
                # Send message to target agent
                if progress_callback:
                    await progress_callback(
                        turn,
                        "sending",
                        f"Turn {turn}/{self.max_turns}: Sending to target agent..."
                    )
                
                logger.info(f"Turn {turn}: Sending to target: {message_to_send[:100]}...")
                print(f"[BookingAutomation] Turn {turn}: Sending to target agent at {target_agent_endpoint}")
                print(f"[BookingAutomation] Turn {turn}: Message: {message_to_send[:100]}...")
                
                # Add timeout to prevent hanging on A2A communication
                try:
                    print(f"[BookingAutomation] Turn {turn}: Waiting for A2A response (10s timeout)...")
                    response = await asyncio.wait_for(
                        send_message_to_a2a_agent(
                            endpoint_url=target_agent_endpoint,
                            message_text=message_to_send
                        ),
                        timeout=10.0  # 10 seconds for A2A response
                    )
                    logger.info(f"Turn {turn}: Target agent responded: {response[:200]}...")
                    print(f"[BookingAutomation] Turn {turn}: Target agent responded: {response[:200]}...")
                except asyncio.TimeoutError:
                    error_msg = f"Turn {turn}: Target agent did not respond within 10 seconds"
                    logger.error(error_msg)
                    print(f"[BookingAutomation] ⏱️ TIMEOUT: Target agent timed out after 10 seconds")
                    
                    if progress_callback:
                        await progress_callback(
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
                    
                    if progress_callback:
                        await progress_callback(
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
                conversation_turn = ConversationTurn(
                    turn_number=turn,
                    message_sent=message_to_send,
                    response_received=response,
                    timestamp=datetime.now(),
                    metadata={
                        'booking_agent_analysis': str(booking_agent_response)[:500]
                    }
                )
                self.conversation_history.append(conversation_turn)
                
                # Update conversation context with the new exchange
                conversation_context += f"\n\nTurn {turn}:\nYou sent: {message_to_send}\nTarget agent responded: {response}"
                
                if progress_callback:
                    await progress_callback(
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
                    
                    if progress_callback:
                        await progress_callback(
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
                    if progress_callback:
                        await progress_callback(
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
                    
                    if progress_callback:
                        await progress_callback(
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
                    if progress_callback:
                        await progress_callback(
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
                
                if progress_callback:
                    await progress_callback(
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
        if progress_callback:
            await progress_callback(
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
        if turn == 1:
            # First turn - initial booking request
            prompt = f"""{conversation_context}

This is your first contact with the target agent. Craft a clear, professional booking request that includes:
1. A greeting
2. Your intent to schedule a meeting
3. The key preferences (date/time/duration if specified)
4. A polite request for their availability

Generate ONLY the message you want to send to the target agent. Do not include explanations or meta-commentary."""
        else:
            # Subsequent turns - respond to target agent
            prompt = f"""{conversation_context}

Based on the target agent's latest response, formulate an appropriate reply that:
1. Addresses any questions they asked
2. Provides any requested information
3. Negotiates if needed
4. Moves toward confirming the booking

Generate ONLY the message you want to send to the target agent. Do not include explanations or meta-commentary."""
        
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

