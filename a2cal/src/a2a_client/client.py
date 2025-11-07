"""A2A Client for sending messages to A2A agents."""
import asyncio
import logging
from uuid import uuid4
from pathlib import Path

# Initialize logger with file handler ONLY (no stderr/stdout to avoid broken pipe)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.handlers = []  # Remove any default handlers
logger.propagate = False  # Don't propagate to parent loggers (which might have stderr handlers)

# Add file handler for debugging (don't use stderr to avoid broken pipe)
# Wrap in try-except so logging failures don't crash the client
try:
    log_file = Path("/tmp/a2a_client.log")
    file_handler = logging.FileHandler(log_file, mode='a')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
except Exception:
    # If we can't set up logging, continue without it
    # Add a null handler to prevent "No handlers" warnings
    logger.addHandler(logging.NullHandler())

# Create safe logging functions that never raise exceptions
def safe_log_debug(msg):
    try:
        logger.debug(msg)
    except:
        pass

def safe_log_info(msg):
    try:
        logger.info(msg)
    except:
        pass

def safe_log_warning(msg):
    try:
        logger.warning(msg)
    except:
        pass

def safe_log_error(msg):
    try:
        logger.error(msg)
    except:
        pass

# Try to import required dependencies
A2A_SDK_AVAILABLE = False
_import_error = None
httpx = None
A2ACardResolver = None
A2AClient = None
AgentCard = None
Message = None
MessageSendParams = None
SendMessageRequest = None
SendMessageResponse = None
SendStreamingMessageRequest = None
SendStreamingMessageResponse = None
SendStreamingMessageSuccessResponse = None
TaskArtifactUpdateEvent = None
TaskStatusUpdateEvent = None
TextPart = None

try:
    import sys
    safe_log_debug(f"Python executable: {sys.executable}")
    safe_log_debug(f"Python path: {sys.path[:3]}")
    
    import httpx
    safe_log_debug("✓ httpx imported successfully")
    
    from a2a.client import A2ACardResolver, A2AClient
    safe_log_debug("✓ a2a.client imported successfully")
    
    from a2a.types import (
        AgentCard,
        DataPart,
        Message,
        MessageSendParams,
        SendMessageRequest,
        SendMessageResponse,
        SendStreamingMessageRequest,
        SendStreamingMessageResponse,
        SendStreamingMessageSuccessResponse,
        TaskArtifactUpdateEvent,
        TaskStatusUpdateEvent,
        TextPart,
    )
    safe_log_debug("✓ a2a.types imported successfully")
    
    A2A_SDK_AVAILABLE = True
    safe_log_info("✅ A2A SDK is available and ready to use")
except ImportError as e:
    A2A_SDK_AVAILABLE = False
    _import_error = e
    import sys
    safe_log_error(f"❌ Failed to import A2A SDK: {e}")
    safe_log_error(f"   Error type: {type(e).__name__}")
    safe_log_error(f"   Python executable: {sys.executable}")
    import traceback
    safe_log_debug(f"   Full traceback:\n{traceback.format_exc()}")
except Exception as e:
    A2A_SDK_AVAILABLE = False
    _import_error = e
    import sys
    safe_log_error(f"❌ Unexpected error importing A2A SDK: {e}")
    safe_log_error(f"   Python executable: {sys.executable}")
    import traceback
    safe_log_debug(f"   Full traceback:\n{traceback.format_exc()}")


async def get_agent_card_from_url(endpoint_url: str) -> AgentCard:
    """Fetch the agent card from the A2A endpoint using A2ACardResolver.
    
    Args:
        endpoint_url: The A2A service endpoint URL (e.g., 'https://example.com/agent')
        
    Returns:
        AgentCard: The agent's card with capabilities and metadata
        
    Raises:
        ImportError: If a2a-sdk is not installed
        Exception: If the agent card cannot be fetched
    """
    if not A2A_SDK_AVAILABLE:
        raise ImportError(
            "a2a-sdk is not installed. Please install it with: "
            "pip install 'a2a-sdk[http-server]' or uv add 'a2a-sdk[http-server]'"
        ) from _import_error
    
    safe_log_info(f"Fetching agent card from base URL: {endpoint_url}")
    
    async with httpx.AsyncClient(timeout=30.0) as httpx_client:
        card_resolver = A2ACardResolver(httpx_client, endpoint_url)
        # A2ACardResolver will construct the agent card URL automatically
        # It typically looks for: {endpoint_url}/.well-known/agent-card.json
        expected_card_url = f"{endpoint_url.rstrip('/')}/.well-known/agent-card.json"
        safe_log_info(f"Expected agent card URL: {expected_card_url}")
        card = await card_resolver.get_agent_card()
        safe_log_info(f"✅ Agent card fetched successfully")
        safe_log_debug(f"Agent card name: {card.name if hasattr(card, 'name') else 'unknown'}")
        safe_log_debug(f"Agent card URL: {card.url if hasattr(card, 'url') else 'unknown'}")
        return card


async def send_message_to_a2a_agent(
    endpoint_url: str,
    message_text: str,
    context_id: str = None,
    task_id: str = None,
    use_streaming: bool = True,
) -> tuple[str, str]:
    """Send a message to an A2A agent and get a response.
    
    Args:
        endpoint_url: The A2A service endpoint URL
        message_text: The message text to send
        context_id: Optional context ID for conversation continuity
        task_id: Optional task ID
        use_streaming: Whether to use streaming (if supported by agent)
        
    Returns:
        str: The agent's response text
        
    Raises:
        ImportError: If a2a-sdk is not installed
        Exception: If the message cannot be sent or response cannot be received
    """
    import sys
    
    # CRITICAL: Print to stdout to ensure we see it
    safe_log_info("="*80)
    safe_log_info("🚨 A2A CLIENT FUNCTION CALLED")
    safe_log_info(f"Endpoint: {endpoint_url}")
    safe_log_info(f"Message: {message_text[:50]}...")
    safe_log_info(f"A2A_SDK_AVAILABLE: {A2A_SDK_AVAILABLE}")
    safe_log_info("="*80)
    
    safe_log_info("="*80)
    safe_log_info(f"🚨 A2A CLIENT FUNCTION CALLED")
    safe_log_info(f"  - endpoint_url: {endpoint_url}")
    safe_log_info(f"  - message: {message_text[:50]}...")
    safe_log_info(f"  - A2A_SDK_AVAILABLE: {A2A_SDK_AVAILABLE}")
    safe_log_info(f"  - Python executable: {sys.executable}")
    safe_log_info(f"  - httpx available: {httpx is not None}")
    safe_log_info(f"  - A2AClient available: {A2AClient is not None}")
    safe_log_info("="*80)
    
    # Ensure log file exists at start of call
    try:
        Path("/tmp/a2a_client.log").touch(exist_ok=True)
    except:
        pass  # If we can't create it, continue without logging

    if not A2A_SDK_AVAILABLE:
        error_msg = (
            f"a2a-sdk is not installed. Please install it with: "
            f"pip install 'a2a-sdk[http-server]' or uv add 'a2a-sdk[http-server]'\n\n"
            f"Debug info:\n"
            f"  - Python executable: {sys.executable}\n"
            f"  - Import error: {_import_error}\n"
            f"  - Error type: {type(_import_error).__name__ if _import_error else 'None'}"
        )
        safe_log_error(error_msg)
        raise ImportError(error_msg) from _import_error
    # Generate IDs if not provided
    if not context_id:
        context_id = str(uuid4())
    if not task_id:
        task_id = str(uuid4())
    message_id = str(uuid4())
    
    # Fetch agent card using A2ACardResolver
    safe_log_info(f"📡 Connecting to A2A agent at base URL: {endpoint_url}")
    expected_card_url = f"{endpoint_url.rstrip('/')}/.well-known/agent-card.json"
    safe_log_info(f"📋 Agent card will be fetched from: {expected_card_url}")
    
    async with httpx.AsyncClient(timeout=60.0) as httpx_client:
        card_resolver = A2ACardResolver(httpx_client, endpoint_url)
        agent_card = await card_resolver.get_agent_card()
        safe_log_info(f"✅ Agent card fetched: {agent_card.name if hasattr(agent_card, 'name') else 'unknown'}")
        
        # Check if agent supports streaming
        supports_streaming = (
            agent_card.capabilities and 
            agent_card.capabilities.streaming is True and
            use_streaming
        )
        
        # Determine the message endpoint URL
        # A2AClient uses the agent_card.url or constructs from the base URL
        message_endpoint = agent_card.url if hasattr(agent_card, 'url') and agent_card.url else endpoint_url
        safe_log_info("\n" + "="*70)
        safe_log_info("📤 SENDING MESSAGE TO A2A AGENT")
        safe_log_info(f"🌐 Endpoint: {message_endpoint}")
        safe_log_info(f"💬 Message: {message_text[:100]}..." if len(message_text) > 100 else f"💬 Message: {message_text}")
        safe_log_info(f"📡 Streaming: {supports_streaming}")
        safe_log_info("="*70)
        
        a2a_client = A2AClient(httpx_client, agent_card=agent_card)
        
        # Create message using string role (matching reference implementation)
        message = Message(
            role='user',
            parts=[TextPart(text=message_text)],
            message_id=message_id,
            context_id=context_id,
        )
        
        # Create payload with id parameter (matching reference implementation)
        message_payload = MessageSendParams(id=str(uuid4()), message=message)
        
        response_text = ""
        # raw_chunks_debug disabled to avoid broken pipe errors
        raw_chunks_debug = []
        extracted_context_id = context_id  # Start with provided context_id, extract from response if available
        
        if supports_streaming:
            # Use streaming (matching reference implementation)
            request = SendStreamingMessageRequest(
                id=str(uuid4()),
                params=message_payload
            )
            
            safe_log_info("\n" + "="*70)
            safe_log_info("📤 SENDING STREAMING REQUEST")
            safe_log_info("="*70)
            
            response_stream = a2a_client.send_message_streaming(request)
            
            safe_log_info("\n" + "="*70)
            safe_log_info("📥 RECEIVING STREAMING RESPONSE")
            safe_log_info("="*70)
            
            chunk_count = 0
            async for chunk in response_stream:
                # Skip debug tracking to avoid broken pipe errors
                # (chunk object's __str__ can trigger broken pipe)
                chunk_count += 1
                
                # Log chunk details to file (handle broken pipe)
                try:
                    safe_log_debug("="*70)
                    safe_log_debug(f"📦 RAW CHUNK #{chunk_count}")
                    safe_log_debug(f"Type: {type(chunk)}")
                    safe_log_debug(f"Chunk: {chunk}")

                    # Try to dump it
                    try:
                        if hasattr(chunk, 'model_dump'):
                            import json
                            dumped = json.dumps(chunk.model_dump(), indent=2, default=str)
                            safe_log_debug(f"Dumped structure: {dumped[:500]}...")
                        elif hasattr(chunk, '__dict__'):
                            safe_log_debug(f"Dict: {chunk.__dict__}")
                    except Exception as e:
                        safe_log_debug(f"Could not dump: {e}")

                    safe_log_debug("="*70)
                except (BrokenPipeError, OSError):
                    # Broken pipe during logging - skip this chunk's debug info
                    pass
                
                # NEW: Direct parsing of the actual structure we're receiving
                # Based on debug file: chunk.data.result contains the event
                result_data = None
                
                # Debug: Check what attributes chunk actually has
                safe_log_info(f"🔍 Chunk type: {type(chunk)}")
                safe_log_info(f"🔍 Has 'data': {hasattr(chunk, 'data')}")
                safe_log_info(f"🔍 Has 'result': {hasattr(chunk, 'result')}")
                safe_log_info(f"🔍 Is dict: {isinstance(chunk, dict)}")
                
                # Check what attributes it ACTUALLY has
                if hasattr(chunk, '__dict__'):
                    safe_log_info(f"🔍 Actual attributes: {list(chunk.__dict__.keys())}")
                if hasattr(chunk, 'model_fields'):
                    safe_log_info(f"🔍 Model fields: {list(chunk.model_fields.keys())}")
                
                # BETTER APPROACH: Convert chunk to dict using model_dump(), then parse
                chunk_dict = None
                try:
                    if hasattr(chunk, 'model_dump'):
                        chunk_dict = chunk.model_dump()
                        safe_log_info(f"✅ Converted chunk to dict using model_dump()")
                        safe_log_info(f"🔍 Dict keys: {list(chunk_dict.keys())}")
                    elif isinstance(chunk, dict):
                        chunk_dict = chunk
                        safe_log_info(f"✅ Chunk is already a dict")
                except Exception as e:
                    safe_log_error(f"❌ Could not convert chunk to dict: {e}")
                
                # Extract result from the dict
                if chunk_dict:
                    if 'data' in chunk_dict and isinstance(chunk_dict['data'], dict):
                        if 'result' in chunk_dict['data']:
                            result_data = chunk_dict['data']['result']
                            safe_log_info(f"✅ Got result_data from chunk_dict['data']['result']")
                    elif 'result' in chunk_dict:
                        result_data = chunk_dict['result']
                        safe_log_info(f"✅ Got result_data from chunk_dict['result']")
                
                # Old approach as fallback
                if not result_data:
                    # Try to get result from chunk.data.result (as seen in debug file)
                    if hasattr(chunk, 'data'):
                        safe_log_info(f"🔍 chunk.data type: {type(chunk.data)}")
                        safe_log_info(f"🔍 chunk.data has 'result': {hasattr(chunk.data, 'result')}")
                        
                        if hasattr(chunk.data, 'result'):
                            result_data = chunk.data.result
                            safe_log_info(f"✅ Got result_data from chunk.data.result")
                        elif isinstance(chunk.data, dict) and 'result' in chunk.data:
                            result_data = chunk.data['result']
                            safe_log_info(f"✅ Got result_data from chunk.data['result']")
                    
                    # Fallback: try chunk.result directly
                    if not result_data and hasattr(chunk, 'result'):
                        result_data = chunk.result
                        safe_log_info(f"✅ Got result_data from chunk.result")
                    
                    # Fallback: try dict access
                    if not result_data and isinstance(chunk, dict) and 'result' in chunk:
                        result_data = chunk['result']
                        safe_log_info(f"✅ Got result_data from chunk['result']")
                
                if result_data:
                    safe_log_info(f"🎯 result_data type: {type(result_data)}")
                    safe_log_info(f"🎯 result_data has 'kind': {hasattr(result_data, 'kind')}")
                    
                    # Extract contextId from result_data for conversation continuity
                    if isinstance(result_data, dict):
                        if 'contextId' in result_data:
                            extracted_context_id = result_data['contextId']
                            safe_log_info(f"✅ Extracted contextId from result_data: {extracted_context_id}")
                    elif hasattr(result_data, 'contextId'):
                        extracted_context_id = result_data.contextId
                        safe_log_info(f"✅ Extracted contextId from result_data: {extracted_context_id}")
                else:
                    safe_log_warning(f"❌ Could not extract result_data from chunk!")
                
                if result_data:
                    safe_log_info(f"✅ Found result_data, checking kind...")
                    
                    # Get the 'kind' field to determine what type of event this is
                    event_kind = result_data.get('kind') if isinstance(result_data, dict) else getattr(result_data, 'kind', None)
                    safe_log_info(f"   Event kind: {event_kind}")
                    
                    # Handle artifact-update (THIS IS WHERE THE MAIN RESPONSE IS)
                    if event_kind == 'artifact-update':
                        safe_log_info(f"   📦 Processing artifact-update")
                        
                        artifact = result_data.get('artifact') if isinstance(result_data, dict) else getattr(result_data, 'artifact', None)
                        
                        if artifact:
                            safe_log_info(f"   Found artifact: {type(artifact)}")
                            parts = artifact.get('parts') if isinstance(artifact, dict) else getattr(artifact, 'parts', None)
                            
                            if parts:
                                safe_log_info(f"   Found {len(parts)} parts in artifact")
                                
                                for i, part in enumerate(parts):
                                    part_kind = part.get('kind') if isinstance(part, dict) else getattr(part, 'kind', None)
                                    safe_log_info(f"   Part {i} kind: {part_kind}")
                                    
                                    # Handle kind="text" - extract from 'text' field
                                    if part_kind == 'text':
                                        text_value = part.get('text') if isinstance(part, dict) else getattr(part, 'text', None)
                                        if text_value:
                                            response_text += text_value
                                            safe_log_info(f"   ✅ Extracted TEXT from part {i}: {len(text_value)} chars")
                                        else:
                                            safe_log_warning(f"   ⚠️ Part {i} kind='text' but no text value found")
                                    
                                    # Handle kind="data" - extract from 'data.question' or 'data.message' field
                                    elif part_kind == 'data':
                                        data_value = part.get('data') if isinstance(part, dict) else getattr(part, 'data', None)
                                        safe_log_info(f"   Part {i} has data: {data_value}")
                                        
                                        if data_value and isinstance(data_value, dict):
                                            # Try common keys for text content
                                            text_value = None
                                            if 'question' in data_value:
                                                text_value = data_value['question']
                                                safe_log_info(f"   Found 'question' in data")
                                            elif 'message' in data_value:
                                                text_value = data_value['message']
                                                safe_log_info(f"   Found 'message' in data")
                                            elif 'text' in data_value:
                                                text_value = data_value['text']
                                                safe_log_info(f"   Found 'text' in data")
                                            else:
                                                # Fallback: stringify the whole data object
                                                import json
                                                text_value = json.dumps(data_value, indent=2)
                                                safe_log_info(f"   Using full data as JSON string")
                                            
                                            if text_value:
                                                response_text += text_value
                                                safe_log_info(f"   ✅ Extracted DATA from part {i}: {len(text_value)} chars")
                                        else:
                                            safe_log_warning(f"   ⚠️ Part {i} kind='data' but no data value found or data is not a dict")
                                    
                                    else:
                                        safe_log_warning(f"   ⚠️ Skipping part {i} with unknown kind={part_kind}")
                            else:
                                safe_log_warning(f"   ⚠️ Artifact has no parts!")
                        else:
                            safe_log_warning(f"   ⚠️ No artifact found in artifact-update event!")
                    
                    # Handle status-update (may contain status messages)
                    elif event_kind == 'status-update':
                        status = getattr(result_data, 'status', None) or (result_data.get('status') if isinstance(result_data, dict) else None)
                        
                        if status:
                            message = getattr(status, 'message', None) or (status.get('message') if isinstance(status, dict) else None)
                            
                            if message:
                                parts = getattr(message, 'parts', None) or (message.get('parts') if isinstance(message, dict) else None)
                                
                                if parts:
                                    for i, part in enumerate(parts):
                                        part_kind = getattr(part, 'kind', None) or (part.get('kind') if isinstance(part, dict) else None)
                                        
                                        if part_kind == 'text':
                                            text_value = getattr(part, 'text', None) or (part.get('text') if isinstance(part, dict) else None)
                                            if text_value:
                                                # Optionally include status messages
                                                # response_text += f"\n[Status: {text_value}]\n"
                    
                    # Handle task (initial task submission)
                    elif event_kind == 'task':
                    
                    else:
                    
                    continue  # Skip the old parsing logic below
                
                # OLD LOGIC (fallback) - Handle streaming response - chunk is SendStreamingMessageResponse
                if hasattr(chunk, 'root') and isinstance(chunk.root, SendStreamingMessageSuccessResponse):
                    event = chunk.root.result
                    
                    safe_log_debug(f"-------- EVENT TO TRANSFORM #{chunk_count} --------")
                    safe_log_debug(f"Event type: {type(event).__name__}")
                    
                    # Log the full event structure for debugging
                    try:
                        event_dict = event.model_dump() if hasattr(event, 'model_dump') else {}
                        safe_log_debug(f"Event keys: {list(event_dict.keys())}")
                    except:
                        pass
                    
                    # Handle TaskStatusUpdateEvent (contains messages)
                    if isinstance(event, TaskStatusUpdateEvent):
                        safe_log_debug("Processing TaskStatusUpdateEvent")
                        if hasattr(event, 'message') and event.message:
                            message = event.message
                            safe_log_debug(f"Message parts: {message.parts if hasattr(message, 'parts') else 'no parts'}")
                            if hasattr(message, 'parts') and message.parts:
                                for part in message.parts:
                                    safe_log_debug(f"Part type: {type(part)}, has text: {hasattr(part, 'text')}")
                                    if isinstance(part, TextPart) and hasattr(part, 'text'):
                                        response_text += part.text
                                        safe_log_debug(f"Extracted text from TextPart: {part.text[:50]}")
                                    elif hasattr(part, 'text') and part.text:
                                        response_text += part.text
                                        safe_log_debug(f"Extracted text from part: {part.text[:50]}")
                    
                    # Handle TaskArtifactUpdateEvent (contains artifacts) - THIS IS WHERE THE RESPONSE USUALLY IS
                    elif isinstance(event, TaskArtifactUpdateEvent):
                        artifact = event.artifact
                        
                        safe_log_debug("-------- ARTIFACT RECEIVED --------")
                        safe_log_debug(f"Artifact type: {type(artifact)}")
                        if hasattr(artifact, 'name'):
                            safe_log_debug(f"Artifact name: {artifact.name}")
                        
                        # Check artifact.parts (common structure) - THIS IS THE PRIMARY LOCATION
                        if hasattr(artifact, 'parts') and artifact.parts:
                            safe_log_debug(f"-------- TRANSFORMING {len(artifact.parts)} PARTS --------")
                            for i, part in enumerate(artifact.parts):
                                # Check 'kind' attribute FIRST (works for both dicts and objects)
                                part_kind = getattr(part, 'kind', None) or (part.get('kind') if isinstance(part, dict) else None)
                                safe_log_debug(f"Part #{i} kind: {part_kind}")
                                
                                # Handle kind="text" - extract from 'text' field
                                if part_kind == 'text':
                                    text_value = getattr(part, 'text', None) or (part.get('text') if isinstance(part, dict) else None)
                                    if text_value:
                                        response_text += text_value
                                        safe_log_info("="*60)
                                        safe_log_info(f"🎯 AGENT RESPONSE EXTRACTED (Part #{i})")
                                        safe_log_info(f"📝 Text: {text_value[:200]}...")
                                        safe_log_info("="*60)
                                        continue
                                
                                # Handle kind="data" - extract from 'data' field
                                if part_kind == 'data':
                                    data_value = getattr(part, 'data', None) or (part.get('data') if isinstance(part, dict) else None)
                                    if data_value:
                                        extracted_text = None
                                        if isinstance(data_value, dict):
                                            if 'question' in data_value:
                                                extracted_text = data_value['question']
                                                response_text += extracted_text
                                            elif 'message' in data_value:
                                                extracted_text = data_value['message']
                                                response_text += extracted_text
                                            else:
                                                import json
                                                extracted_text = json.dumps(data_value, indent=2)
                                                response_text += extracted_text
                                        else:
                                            extracted_text = str(data_value)
                                            response_text += extracted_text
                                        
                                        if extracted_text:
                                            safe_log_info("="*60)
                                            safe_log_info(f"🎯 AGENT RESPONSE EXTRACTED (Part #{i}, type=data)")
                                            safe_log_info(f"📝 Content: {extracted_text[:200]}...")
                                            safe_log_info("="*60)
                                        continue
                                
                                # Fallback: Handle TextPart class instances
                                if isinstance(part, TextPart) and hasattr(part, 'text') and part.text:
                                    response_text += part.text
                                    safe_log_info("="*60)
                                    safe_log_info(f"🎯 AGENT RESPONSE EXTRACTED (Part #{i}, TextPart)")
                                    safe_log_info(f"📝 Text: {part.text[:200]}...")
                                    safe_log_info("="*60)
                                    continue
                                
                                # Fallback: Handle DataPart class instances or objects with 'data' attribute
                                if isinstance(part, DataPart) or (hasattr(part, 'data') and part.data):
                                    data_value = part.data if hasattr(part, 'data') else None
                                    if isinstance(data_value, dict):
                                        if 'question' in data_value:
                                            response_text += data_value['question']
                                            safe_log_info(f"✅ Extracted question from DataPart")
                                        elif 'message' in data_value:
                                            response_text += data_value['message']
                                            safe_log_info(f"✅ Extracted message from DataPart")
                                        elif 'text' in data_value:
                                            response_text += str(data_value['text'])
                                            safe_log_info(f"✅ Extracted text from DataPart")
                                        else:
                                            import json
                                            response_text += json.dumps(data_value, indent=2)
                                            safe_log_info(f"✅ Formatted DataPart as JSON")
                                    elif isinstance(data_value, str):
                                        response_text += data_value
                                        safe_log_info(f"✅ Extracted string from DataPart")
                                    elif data_value is not None:
                                        response_text += str(data_value)
                                        safe_log_info(f"✅ Converted DataPart to string")
                                    continue
                                
                                # Final fallback: check for 'text' attribute
                                if hasattr(part, 'text') and part.text:
                                    response_text += part.text
                                    safe_log_info(f"✅ Extracted text from part.text attribute")
                                    continue
                        # Also check artifact.content (alternative structure)
                        elif hasattr(artifact, 'content') and artifact.content:
                            safe_log_debug(f"-------- TRANSFORMING {len(artifact.content)} CONTENT ITEMS --------")
                            for part in artifact.content:
                                if isinstance(part, TextPart) and hasattr(part, 'text'):
                                    response_text += part.text
                                    safe_log_info(f"✅ Extracted text from content")
                                elif hasattr(part, 'text') and part.text:
                                    response_text += part.text
                                    safe_log_info(f"✅ Extracted text from content")
                                elif hasattr(part, 'data') and part.data:
                                    data_value = part.data
                                    if isinstance(data_value, dict) and 'question' in data_value:
                                        response_text += data_value['question']
                                    else:
                                        response_text += str(data_value)
                                    safe_log_info(f"✅ Extracted data from content")
                    
                    # Handle Message directly
                    elif isinstance(event, Message):
                        if hasattr(event, 'parts') and event.parts:
                            safe_log_debug(f"-------- TRANSFORMING MESSAGE WITH {len(event.parts)} PARTS --------")
                            for part in event.parts:
                                if isinstance(part, TextPart) and hasattr(part, 'text'):
                                    response_text += part.text
                                    safe_log_info(f"✅ Extracted text from Message")
                                elif hasattr(part, 'text') and part.text:
                                    response_text += part.text
                                    safe_log_info(f"✅ Extracted text from Message")
                    
                    # Try to extract text from event attributes directly
                    if not response_text:
                        if hasattr(event, 'text') and event.text:
                            response_text += event.text
                            safe_log_info(f"✅ Extracted text from event.text")
                else:
                    # Chunk doesn't have .root structure - try to parse directly
                    safe_log_warning(f"Chunk doesn't have expected .root structure: {type(chunk)}")
                    
                    # Try to parse chunk directly as an event
                    try:
                        if hasattr(chunk, 'model_dump'):
                            chunk_dict = chunk.model_dump()
                            safe_log_info(f"Chunk dict keys: {list(chunk_dict.keys())}")
                        
                        # Try common attributes
                        if hasattr(chunk, 'text'):
                            response_text += str(chunk.text)
                        elif hasattr(chunk, 'content'):
                            response_text += str(chunk.content)
                        elif hasattr(chunk, 'message'):
                            response_text += str(chunk.message)
                    except Exception as e:
                        safe_log_error(f"Error parsing chunk directly: {e}")
        else:
            # Use non-streaming
            request = SendMessageRequest(
                id=str(uuid4()),
                params=message_payload
            )
            
            safe_log_info("\n" + "="*70)
            safe_log_info("📤 SENDING NON-STREAMING REQUEST")
            safe_log_info("="*70)
            
            response = await a2a_client.send_message(request)
            
            safe_log_info("\n" + "="*70)
            safe_log_info("📥 RAW RESPONSE RECEIVED")
            safe_log_info("="*70)
            safe_log_info(f"Type: {type(response)}")
            safe_log_info(f"Response: {response}")
            
            # Try to dump it
            try:
                if hasattr(response, 'model_dump'):
                    import json
                    safe_log_info(f"Dumped: {json.dumps(response.model_dump(), indent=2, default=str)}")
                elif hasattr(response, '__dict__'):
                    safe_log_info(f"Dict: {response.__dict__}")
            except Exception as e:
                safe_log_info(f"Could not dump: {e}")
            
            safe_log_info("="*70 + "\n")
            
            # Extract text from response - response is SendMessageResponse
            if hasattr(response, 'root'):
                # Check if it's a success response
                if hasattr(response.root, 'result'):
                    event = response.root.result
                    
                    # Extract contextId from non-streaming response
                    if isinstance(event, Message) and hasattr(event, 'context_id'):
                        extracted_context_id = event.context_id
                        safe_log_info(f"✅ Extracted contextId from Message: {extracted_context_id}")
                    elif hasattr(event, 'contextId'):
                        extracted_context_id = event.contextId
                        safe_log_info(f"✅ Extracted contextId from event: {extracted_context_id}")
                    
                    # Handle Message
                    if isinstance(event, Message):
                        if hasattr(event, 'parts'):
                            for part in event.parts:
                                if isinstance(part, TextPart):
                                    response_text += part.text
                                elif hasattr(part, 'text'):
                                    response_text += part.text
                    
                    # Handle TaskStatusUpdateEvent
                    elif isinstance(event, TaskStatusUpdateEvent):
                        if hasattr(event, 'message') and event.message:
                            message = event.message
                            if hasattr(message, 'parts'):
                                for part in message.parts:
                                    if isinstance(part, TextPart):
                                        response_text += part.text
                                    elif hasattr(part, 'text'):
                                        response_text += part.text
        
        # Build debug info (always, regardless of whether text was extracted)
        debug_parts = ["\n\n---\n\n**A2A Client Debug Info:**"]
        debug_parts.append(f"\n**Received {len(raw_chunks_debug)} chunk(s) from agent:**")
        
        # Write detailed debug info to a file
        debug_file_path = "/tmp/a2a_client_debug.json"
        try:
            import json
            import os
            debug_data = {
                'endpoint': endpoint_url,
                'message': message_text[:200],
                'chunks_received': len(raw_chunks_debug),
                'raw_chunks': raw_chunks_debug,
                'supports_streaming': supports_streaming,
                'text_extracted': bool(response_text),
                'text_length': len(response_text)
            }
            with open(debug_file_path, 'w') as f:
                json.dump(debug_data, f, indent=2, default=str)
            debug_parts.append(f"\n**Debug data written to:** `{debug_file_path}`")
            safe_log_info(f"Debug data written to {debug_file_path}")
        except Exception as e:
            safe_log_error(f"Failed to write debug file: {e}")
        
        # Include summary of chunks in error message
        for i, chunk_info in enumerate(raw_chunks_debug[:3]):  # Show first 3 chunks
            chunk_type = chunk_info.get('type', 'Unknown')
            debug_parts.append(f"\n**Chunk {i+1}:** Type `{chunk_type}`")
            
            # Try to show meaningful data
            chunk_data = chunk_info.get('data', {})
            if isinstance(chunk_data, dict):
                if 'root' in chunk_data:
                    debug_parts.append(f"  - Has `.root` attribute")
                    root_data = chunk_data['root']
                    if isinstance(root_data, dict):
                        debug_parts.append(f"  - Root type: `{root_data.get('type', 'unknown')}`")
                        if 'result' in root_data:
                            debug_parts.append(f"  - Has `.root.result`")
                # Show first few keys
                keys = list(chunk_data.keys())[:5]
                debug_parts.append(f"  - Keys: `{keys}`")
            else:
                debug_parts.append(f"  - Data: `{str(chunk_data)[:100]}`")
        
        if len(raw_chunks_debug) > 3:
            debug_parts.append(f"\n_... and {len(raw_chunks_debug) - 3} more chunk(s)_")
        
        if not raw_chunks_debug:
            debug_parts.append("\n⚠️ **No chunks received from server!** The streaming response may be empty or not properly formatted.")
        
        debug_parts.append(f"\n\n**Check debug file for full details:** `{debug_file_path}`")
        
        debug_info = "\n".join(debug_parts)
        
        # Return response (debug info is saved to file, will be shown in UI separately)
        # Wrap ALL logging in try-except to prevent BrokenPipeError from blocking the return
        try:
            if not response_text:
                safe_log_warning("\n" + "="*70)
                safe_log_warning("⚠️  NO TEXT EXTRACTED FROM AGENT RESPONSE")
                safe_log_warning("="*70)

                # Show simple warning message (debug info will be in the UI debug expander)
                response_text = f"⚠️ **No text content extracted from agent response.**\n\n💡 Check the Debug Info section below for details."

                safe_log_warning(f"Final error message: {response_text[:500]}")

                # Log to file for debugging
                safe_log_warning("="*70)
                safe_log_warning("🚨 A2A CLIENT: NO TEXT EXTRACTED")
                safe_log_warning("="*70)
                safe_log_warning(f"Chunks received: {len(raw_chunks_debug)}")
                safe_log_warning(f"Debug file: {debug_file_path}")
                safe_log_warning("="*70)
            else:
                safe_log_info("\n" + "="*70)
                safe_log_info("✅ FINAL AGENT RESPONSE")
                safe_log_info(f"📊 Total length: {len(response_text)} characters")
                safe_log_info(f"📝 Content preview: {response_text[:300]}...")
                safe_log_info("="*70 + "\n")
        except (BrokenPipeError, OSError):
            # Logging failed, but we have the response - continue
            pass

        # Return response text and context_id for conversation continuity
        # This MUST execute even if logging fails
        return response_text, extracted_context_id

