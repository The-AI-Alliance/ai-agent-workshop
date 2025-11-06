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
        preferences: MeetingPreferences,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Automatically book a meeting with the target agent.
        
        Args:
            target_agent_endpoint: A2A endpoint URL of the target agent
            preferences: Meeting preferences to share
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
        
        # Initial message with preferences
        initial_message = self._build_initial_message(preferences)
        
        if progress_callback:
            await progress_callback(0, "starting", "Initiating booking request...")
        
        # Conversation loop
        current_message = initial_message
        
        for turn in range(1, self.max_turns + 1):
            self.current_turn = turn
            
            try:
                # Send message to target agent
                if progress_callback:
                    await progress_callback(
                        turn,
                        "sending",
                        f"Turn {turn}/{self.max_turns}: Sending message to agent..."
                    )
                
                logger.info(f"Turn {turn}: Sending message: {current_message[:100]}...")
                
                response = await send_message_to_a2a_agent(
                    endpoint_url=target_agent_endpoint,
                    message_text=current_message
                )
                
                logger.info(f"Turn {turn}: Received response: {response[:200]}...")
                
                # Record conversation turn
                conversation_turn = ConversationTurn(
                    turn_number=turn,
                    message_sent=current_message,
                    response_received=response,
                    timestamp=datetime.now(),
                    metadata={}
                )
                self.conversation_history.append(conversation_turn)
                
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
    
    def _build_initial_message(self, preferences: MeetingPreferences) -> str:
        """Build the initial booking request message."""
        base_message = "I would like to book a meeting with you. "
        prefs_text = preferences.to_natural_language()
        
        return base_message + prefs_text
    
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
    
    def _build_followup_message(
        self,
        preferences: MeetingPreferences,
        missing_info: List[str],
        previous_response: str
    ) -> str:
        """Build a follow-up message providing missing information."""
        parts = []
        
        for info_type in missing_info:
            if info_type == 'time' and preferences.time:
                parts.append(f"Time: {preferences.time}")
            elif info_type == 'date' and preferences.date:
                parts.append(f"Date: {preferences.date}")
            elif info_type == 'duration' and preferences.duration:
                parts.append(f"Duration: {preferences.duration} minutes")
            elif info_type == 'partner_agent_id' and preferences.partner_agent_id:
                parts.append(f"Partner agent ID: {preferences.partner_agent_id}")
        
        if parts:
            return "Here is the additional information: " + ", ".join(parts) + "."
        else:
            return "I don't have that information. Please proceed with available details or suggest alternatives."
    
    def _build_acknowledgment_message(self, previous_response: str) -> str:
        """Build an acknowledgment message to continue the conversation."""
        # Simple acknowledgments to keep conversation flowing
        acknowledgments = [
            "Thank you. Please continue.",
            "Understood. What's next?",
            "Got it. Please proceed.",
            "Okay, please go ahead.",
            "I'm ready to proceed."
        ]
        
        # Rotate through acknowledgments based on turn number
        return acknowledgments[self.current_turn % len(acknowledgments)]
    
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

