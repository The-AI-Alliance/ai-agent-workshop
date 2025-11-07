"""A2A Client for sending messages to A2A agents."""
import asyncio
import logging
from uuid import uuid4

# Initialize logger first
logger = logging.getLogger(__name__)

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
    logger.debug(f"Python executable: {sys.executable}")
    logger.debug(f"Python path: {sys.path[:3]}")
    
    import httpx
    logger.debug("✓ httpx imported successfully")
    
    from a2a.client import A2ACardResolver, A2AClient
    logger.debug("✓ a2a.client imported successfully")
    
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
    logger.debug("✓ a2a.types imported successfully")
    
    A2A_SDK_AVAILABLE = True
    logger.info("✅ A2A SDK is available and ready to use")
except ImportError as e:
    A2A_SDK_AVAILABLE = False
    _import_error = e
    import sys
    logger.error(f"❌ Failed to import A2A SDK: {e}")
    logger.error(f"   Error type: {type(e).__name__}")
    logger.error(f"   Python executable: {sys.executable}")
    import traceback
    logger.debug(f"   Full traceback:\n{traceback.format_exc()}")
except Exception as e:
    A2A_SDK_AVAILABLE = False
    _import_error = e
    import sys
    logger.error(f"❌ Unexpected error importing A2A SDK: {e}")
    logger.error(f"   Python executable: {sys.executable}")
    import traceback
    logger.debug(f"   Full traceback:\n{traceback.format_exc()}")


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
    
    logger.info(f"Fetching agent card from base URL: {endpoint_url}")
    
    async with httpx.AsyncClient(timeout=30.0) as httpx_client:
        card_resolver = A2ACardResolver(httpx_client, endpoint_url)
        # A2ACardResolver will construct the agent card URL automatically
        # It typically looks for: {endpoint_url}/.well-known/agent-card.json
        expected_card_url = f"{endpoint_url.rstrip('/')}/.well-known/agent-card.json"
        logger.info(f"Expected agent card URL: {expected_card_url}")
        card = await card_resolver.get_agent_card()
        logger.info(f"✅ Agent card fetched successfully")
        logger.debug(f"Agent card name: {card.name if hasattr(card, 'name') else 'unknown'}")
        logger.debug(f"Agent card URL: {card.url if hasattr(card, 'url') else 'unknown'}")
        return card


async def send_message_to_a2a_agent(
    endpoint_url: str,
    message_text: str,
    context_id: str = None,
    task_id: str = None,
    use_streaming: bool = True,
) -> str:
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
    print("\n" + "="*80)
    print("🚨 A2A CLIENT FUNCTION CALLED")
    print(f"Endpoint: {endpoint_url}")
    print(f"Message: {message_text[:50]}...")
    print(f"A2A_SDK_AVAILABLE: {A2A_SDK_AVAILABLE}")
    print("="*80 + "\n")
    
    logger.info("="*80)
    logger.info(f"🚨 A2A CLIENT FUNCTION CALLED")
    logger.info(f"  - endpoint_url: {endpoint_url}")
    logger.info(f"  - message: {message_text[:50]}...")
    logger.info(f"  - A2A_SDK_AVAILABLE: {A2A_SDK_AVAILABLE}")
    logger.info(f"  - Python executable: {sys.executable}")
    logger.info(f"  - httpx available: {httpx is not None}")
    logger.info(f"  - A2AClient available: {A2AClient is not None}")
    logger.info("="*80)
    
    if not A2A_SDK_AVAILABLE:
        error_msg = (
            f"a2a-sdk is not installed. Please install it with: "
            f"pip install 'a2a-sdk[http-server]' or uv add 'a2a-sdk[http-server]'\n\n"
            f"Debug info:\n"
            f"  - Python executable: {sys.executable}\n"
            f"  - Import error: {_import_error}\n"
            f"  - Error type: {type(_import_error).__name__ if _import_error else 'None'}"
        )
        logger.error(error_msg)
        raise ImportError(error_msg) from _import_error
    # Generate IDs if not provided
    if not context_id:
        context_id = str(uuid4())
    if not task_id:
        task_id = str(uuid4())
    message_id = str(uuid4())
    
    # Fetch agent card using A2ACardResolver
    logger.info(f"📡 Connecting to A2A agent at base URL: {endpoint_url}")
    expected_card_url = f"{endpoint_url.rstrip('/')}/.well-known/agent-card.json"
    logger.info(f"📋 Agent card will be fetched from: {expected_card_url}")
    
    async with httpx.AsyncClient(timeout=60.0) as httpx_client:
        card_resolver = A2ACardResolver(httpx_client, endpoint_url)
        agent_card = await card_resolver.get_agent_card()
        logger.info(f"✅ Agent card fetched: {agent_card.name if hasattr(agent_card, 'name') else 'unknown'}")
        
        # Check if agent supports streaming
        supports_streaming = (
            agent_card.capabilities and 
            agent_card.capabilities.streaming is True and
            use_streaming
        )
        
        # Determine the message endpoint URL
        # A2AClient uses the agent_card.url or constructs from the base URL
        message_endpoint = agent_card.url if hasattr(agent_card, 'url') and agent_card.url else endpoint_url
        logger.info("\n" + "="*70)
        logger.info("📤 SENDING MESSAGE TO A2A AGENT")
        logger.info(f"🌐 Endpoint: {message_endpoint}")
        logger.info(f"💬 Message: {message_text[:100]}..." if len(message_text) > 100 else f"💬 Message: {message_text}")
        logger.info(f"📡 Streaming: {supports_streaming}")
        logger.info("="*70)
        
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
        raw_chunks_debug = []  # Store raw chunks for debugging
        
        if supports_streaming:
            # Use streaming (matching reference implementation)
            request = SendStreamingMessageRequest(
                id=str(uuid4()),
                params=message_payload
            )
            
            logger.info("\n" + "="*70)
            logger.info("📤 SENDING STREAMING REQUEST")
            logger.info("="*70)
            
            response_stream = a2a_client.send_message_streaming(request)
            
            logger.info("\n" + "="*70)
            logger.info("📥 RECEIVING STREAMING RESPONSE")
            logger.info("="*70)
            
            chunk_count = 0
            async for chunk in response_stream:
                # Store raw chunk for debugging
                try:
                    if hasattr(chunk, 'model_dump'):
                        raw_chunks_debug.append({
                            'type': type(chunk).__name__,
                            'data': chunk.model_dump()
                        })
                    else:
                        raw_chunks_debug.append({
                            'type': type(chunk).__name__,
                            'data': str(chunk)[:500]
                        })
                except:
                    raw_chunks_debug.append({
                        'type': type(chunk).__name__,
                        'data': 'Could not serialize'
                    })
                chunk_count += 1
                
                # Print to stderr so it shows in Streamlit
                import sys
                print(f"\n{'='*70}", file=sys.stderr)
                print(f"📦 RAW CHUNK #{chunk_count}", file=sys.stderr)
                print(f"Type: {type(chunk)}", file=sys.stderr)
                print(f"{'='*70}\n", file=sys.stderr)
                
                logger.info("\n" + "="*70)
                logger.info(f"📦 RAW CHUNK #{chunk_count}")
                logger.info("="*70)
                logger.info(f"Type: {type(chunk)}")
                logger.info(f"Chunk: {chunk}")
                
                # Try to dump it
                try:
                    if hasattr(chunk, 'model_dump'):
                        import json
                        dumped = json.dumps(chunk.model_dump(), indent=2, default=str)
                        logger.info(f"Dumped: {dumped}")
                        print(f"Dumped structure: {dumped[:500]}...", file=sys.stderr)
                    elif hasattr(chunk, '__dict__'):
                        logger.info(f"Dict: {chunk.__dict__}")
                        print(f"Dict: {chunk.__dict__}", file=sys.stderr)
                except Exception as e:
                    logger.info(f"Could not dump: {e}")
                    print(f"Could not dump: {e}", file=sys.stderr)
                
                logger.info("="*70 + "\n")
                
                # NEW: Direct parsing of the actual structure we're receiving
                # Based on debug file: chunk.data.result contains the event
                result_data = None
                
                # Debug: Check what attributes chunk actually has
                logger.info(f"🔍 Chunk type: {type(chunk)}")
                logger.info(f"🔍 Has 'data': {hasattr(chunk, 'data')}")
                logger.info(f"🔍 Has 'result': {hasattr(chunk, 'result')}")
                logger.info(f"🔍 Is dict: {isinstance(chunk, dict)}")
                
                # Check what attributes it ACTUALLY has
                if hasattr(chunk, '__dict__'):
                    logger.info(f"🔍 Actual attributes: {list(chunk.__dict__.keys())}")
                if hasattr(chunk, 'model_fields'):
                    logger.info(f"🔍 Model fields: {list(chunk.model_fields.keys())}")
                
                # BETTER APPROACH: Convert chunk to dict using model_dump(), then parse
                chunk_dict = None
                try:
                    if hasattr(chunk, 'model_dump'):
                        chunk_dict = chunk.model_dump()
                        logger.info(f"✅ Converted chunk to dict using model_dump()")
                        logger.info(f"🔍 Dict keys: {list(chunk_dict.keys())}")
                    elif isinstance(chunk, dict):
                        chunk_dict = chunk
                        logger.info(f"✅ Chunk is already a dict")
                except Exception as e:
                    logger.error(f"❌ Could not convert chunk to dict: {e}")
                
                # Extract result from the dict
                if chunk_dict:
                    if 'data' in chunk_dict and isinstance(chunk_dict['data'], dict):
                        if 'result' in chunk_dict['data']:
                            result_data = chunk_dict['data']['result']
                            logger.info(f"✅ Got result_data from chunk_dict['data']['result']")
                    elif 'result' in chunk_dict:
                        result_data = chunk_dict['result']
                        logger.info(f"✅ Got result_data from chunk_dict['result']")
                
                # Old approach as fallback
                if not result_data:
                    # Try to get result from chunk.data.result (as seen in debug file)
                    if hasattr(chunk, 'data'):
                        logger.info(f"🔍 chunk.data type: {type(chunk.data)}")
                        logger.info(f"🔍 chunk.data has 'result': {hasattr(chunk.data, 'result')}")
                        
                        if hasattr(chunk.data, 'result'):
                            result_data = chunk.data.result
                            logger.info(f"✅ Got result_data from chunk.data.result")
                        elif isinstance(chunk.data, dict) and 'result' in chunk.data:
                            result_data = chunk.data['result']
                            logger.info(f"✅ Got result_data from chunk.data['result']")
                    
                    # Fallback: try chunk.result directly
                    if not result_data and hasattr(chunk, 'result'):
                        result_data = chunk.result
                        logger.info(f"✅ Got result_data from chunk.result")
                    
                    # Fallback: try dict access
                    if not result_data and isinstance(chunk, dict) and 'result' in chunk:
                        result_data = chunk['result']
                        logger.info(f"✅ Got result_data from chunk['result']")
                
                if result_data:
                    logger.info(f"🎯 result_data type: {type(result_data)}")
                    logger.info(f"🎯 result_data has 'kind': {hasattr(result_data, 'kind')}")
                else:
                    logger.warning(f"❌ Could not extract result_data from chunk!")
                
                if result_data:
                    print(f"✅ Found result_data, checking kind...", file=sys.stderr)
                    logger.info(f"✅ Found result_data, checking kind...")
                    
                    # Get the 'kind' field to determine what type of event this is
                    event_kind = result_data.get('kind') if isinstance(result_data, dict) else getattr(result_data, 'kind', None)
                    print(f"   Event kind: {event_kind}", file=sys.stderr)
                    logger.info(f"   Event kind: {event_kind}")
                    
                    # Handle artifact-update (THIS IS WHERE THE MAIN RESPONSE IS)
                    if event_kind == 'artifact-update':
                        print(f"   📦 Processing artifact-update", file=sys.stderr)
                        logger.info(f"   📦 Processing artifact-update")
                        
                        artifact = result_data.get('artifact') if isinstance(result_data, dict) else getattr(result_data, 'artifact', None)
                        
                        if artifact:
                            logger.info(f"   Found artifact: {type(artifact)}")
                            parts = artifact.get('parts') if isinstance(artifact, dict) else getattr(artifact, 'parts', None)
                            
                            if parts:
                                print(f"   Found {len(parts)} parts in artifact", file=sys.stderr)
                                logger.info(f"   Found {len(parts)} parts in artifact")
                                
                                for i, part in enumerate(parts):
                                    part_kind = part.get('kind') if isinstance(part, dict) else getattr(part, 'kind', None)
                                    logger.info(f"   Part {i} kind: {part_kind}")
                                    print(f"   Part {i}: {part}", file=sys.stderr)
                                    
                                    # Handle kind="text" - extract from 'text' field
                                    if part_kind == 'text':
                                        text_value = part.get('text') if isinstance(part, dict) else getattr(part, 'text', None)
                                        if text_value:
                                            response_text += text_value
                                            print(f"   ✅ Extracted TEXT from part {i}: {text_value[:100]}...", file=sys.stderr)
                                            logger.info(f"   ✅ Extracted TEXT from part {i}: {len(text_value)} chars")
                                        else:
                                            logger.warning(f"   ⚠️ Part {i} kind='text' but no text value found")
                                    
                                    # Handle kind="data" - extract from 'data.question' or 'data.message' field
                                    elif part_kind == 'data':
                                        data_value = part.get('data') if isinstance(part, dict) else getattr(part, 'data', None)
                                        logger.info(f"   Part {i} has data: {data_value}")
                                        
                                        if data_value and isinstance(data_value, dict):
                                            # Try common keys for text content
                                            text_value = None
                                            if 'question' in data_value:
                                                text_value = data_value['question']
                                                logger.info(f"   Found 'question' in data")
                                            elif 'message' in data_value:
                                                text_value = data_value['message']
                                                logger.info(f"   Found 'message' in data")
                                            elif 'text' in data_value:
                                                text_value = data_value['text']
                                                logger.info(f"   Found 'text' in data")
                                            else:
                                                # Fallback: stringify the whole data object
                                                import json
                                                text_value = json.dumps(data_value, indent=2)
                                                logger.info(f"   Using full data as JSON string")
                                            
                                            if text_value:
                                                response_text += text_value
                                                print(f"   ✅ Extracted DATA from part {i}: {text_value[:100]}...", file=sys.stderr)
                                                logger.info(f"   ✅ Extracted DATA from part {i}: {len(text_value)} chars")
                                        else:
                                            logger.warning(f"   ⚠️ Part {i} kind='data' but no data value found or data is not a dict")
                                    
                                    else:
                                        logger.warning(f"   ⚠️ Skipping part {i} with unknown kind={part_kind}")
                            else:
                                logger.warning(f"   ⚠️ Artifact has no parts!")
                        else:
                            logger.warning(f"   ⚠️ No artifact found in artifact-update event!")
                    
                    # Handle status-update (may contain status messages)
                    elif event_kind == 'status-update':
                        print(f"   📊 Processing status-update", file=sys.stderr)
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
                                                print(f"   ℹ️ Status message: {text_value}", file=sys.stderr)
                    
                    # Handle task (initial task submission)
                    elif event_kind == 'task':
                        print(f"   📋 Task submission received", file=sys.stderr)
                    
                    else:
                        print(f"   ⚠️ Unknown event kind: {event_kind}", file=sys.stderr)
                    
                    continue  # Skip the old parsing logic below
                
                # OLD LOGIC (fallback) - Handle streaming response - chunk is SendStreamingMessageResponse
                if hasattr(chunk, 'root') and isinstance(chunk.root, SendStreamingMessageSuccessResponse):
                    print(f"✅ [FALLBACK] Chunk has .root with SendStreamingMessageSuccessResponse", file=sys.stderr)
                    event = chunk.root.result
                    
                    logger.debug(f"-------- EVENT TO TRANSFORM #{chunk_count} --------")
                    logger.debug(f"Event type: {type(event).__name__}")
                    
                    # Log the full event structure for debugging
                    try:
                        event_dict = event.model_dump() if hasattr(event, 'model_dump') else {}
                        logger.debug(f"Event keys: {list(event_dict.keys())}")
                    except:
                        pass
                    
                    # Handle TaskStatusUpdateEvent (contains messages)
                    if isinstance(event, TaskStatusUpdateEvent):
                        logger.debug("Processing TaskStatusUpdateEvent")
                        if hasattr(event, 'message') and event.message:
                            message = event.message
                            logger.debug(f"Message parts: {message.parts if hasattr(message, 'parts') else 'no parts'}")
                            if hasattr(message, 'parts') and message.parts:
                                for part in message.parts:
                                    logger.debug(f"Part type: {type(part)}, has text: {hasattr(part, 'text')}")
                                    if isinstance(part, TextPart) and hasattr(part, 'text'):
                                        response_text += part.text
                                        logger.debug(f"Extracted text from TextPart: {part.text[:50]}")
                                    elif hasattr(part, 'text') and part.text:
                                        response_text += part.text
                                        logger.debug(f"Extracted text from part: {part.text[:50]}")
                    
                    # Handle TaskArtifactUpdateEvent (contains artifacts) - THIS IS WHERE THE RESPONSE USUALLY IS
                    elif isinstance(event, TaskArtifactUpdateEvent):
                        artifact = event.artifact
                        
                        logger.debug("-------- ARTIFACT RECEIVED --------")
                        logger.debug(f"Artifact type: {type(artifact)}")
                        if hasattr(artifact, 'name'):
                            logger.debug(f"Artifact name: {artifact.name}")
                        
                        # Check artifact.parts (common structure) - THIS IS THE PRIMARY LOCATION
                        if hasattr(artifact, 'parts') and artifact.parts:
                            logger.debug(f"-------- TRANSFORMING {len(artifact.parts)} PARTS --------")
                            for i, part in enumerate(artifact.parts):
                                # Check 'kind' attribute FIRST (works for both dicts and objects)
                                part_kind = getattr(part, 'kind', None) or (part.get('kind') if isinstance(part, dict) else None)
                                logger.debug(f"Part #{i} kind: {part_kind}")
                                
                                # Handle kind="text" - extract from 'text' field
                                if part_kind == 'text':
                                    text_value = getattr(part, 'text', None) or (part.get('text') if isinstance(part, dict) else None)
                                    if text_value:
                                        response_text += text_value
                                        logger.info("="*60)
                                        logger.info(f"🎯 AGENT RESPONSE EXTRACTED (Part #{i})")
                                        logger.info(f"📝 Text: {text_value[:200]}...")
                                        logger.info("="*60)
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
                                            logger.info("="*60)
                                            logger.info(f"🎯 AGENT RESPONSE EXTRACTED (Part #{i}, type=data)")
                                            logger.info(f"📝 Content: {extracted_text[:200]}...")
                                            logger.info("="*60)
                                        continue
                                
                                # Fallback: Handle TextPart class instances
                                if isinstance(part, TextPart) and hasattr(part, 'text') and part.text:
                                    response_text += part.text
                                    logger.info("="*60)
                                    logger.info(f"🎯 AGENT RESPONSE EXTRACTED (Part #{i}, TextPart)")
                                    logger.info(f"📝 Text: {part.text[:200]}...")
                                    logger.info("="*60)
                                    continue
                                
                                # Fallback: Handle DataPart class instances or objects with 'data' attribute
                                if isinstance(part, DataPart) or (hasattr(part, 'data') and part.data):
                                    data_value = part.data if hasattr(part, 'data') else None
                                    if isinstance(data_value, dict):
                                        if 'question' in data_value:
                                            response_text += data_value['question']
                                            logger.info(f"✅ Extracted question from DataPart")
                                        elif 'message' in data_value:
                                            response_text += data_value['message']
                                            logger.info(f"✅ Extracted message from DataPart")
                                        elif 'text' in data_value:
                                            response_text += str(data_value['text'])
                                            logger.info(f"✅ Extracted text from DataPart")
                                        else:
                                            import json
                                            response_text += json.dumps(data_value, indent=2)
                                            logger.info(f"✅ Formatted DataPart as JSON")
                                    elif isinstance(data_value, str):
                                        response_text += data_value
                                        logger.info(f"✅ Extracted string from DataPart")
                                    elif data_value is not None:
                                        response_text += str(data_value)
                                        logger.info(f"✅ Converted DataPart to string")
                                    continue
                                
                                # Final fallback: check for 'text' attribute
                                if hasattr(part, 'text') and part.text:
                                    response_text += part.text
                                    logger.info(f"✅ Extracted text from part.text attribute")
                                    continue
                        # Also check artifact.content (alternative structure)
                        elif hasattr(artifact, 'content') and artifact.content:
                            logger.debug(f"-------- TRANSFORMING {len(artifact.content)} CONTENT ITEMS --------")
                            for part in artifact.content:
                                if isinstance(part, TextPart) and hasattr(part, 'text'):
                                    response_text += part.text
                                    logger.info(f"✅ Extracted text from content")
                                elif hasattr(part, 'text') and part.text:
                                    response_text += part.text
                                    logger.info(f"✅ Extracted text from content")
                                elif hasattr(part, 'data') and part.data:
                                    data_value = part.data
                                    if isinstance(data_value, dict) and 'question' in data_value:
                                        response_text += data_value['question']
                                    else:
                                        response_text += str(data_value)
                                    logger.info(f"✅ Extracted data from content")
                    
                    # Handle Message directly
                    elif isinstance(event, Message):
                        if hasattr(event, 'parts') and event.parts:
                            logger.debug(f"-------- TRANSFORMING MESSAGE WITH {len(event.parts)} PARTS --------")
                            for part in event.parts:
                                if isinstance(part, TextPart) and hasattr(part, 'text'):
                                    response_text += part.text
                                    logger.info(f"✅ Extracted text from Message")
                                elif hasattr(part, 'text') and part.text:
                                    response_text += part.text
                                    logger.info(f"✅ Extracted text from Message")
                    
                    # Try to extract text from event attributes directly
                    if not response_text:
                        if hasattr(event, 'text') and event.text:
                            response_text += event.text
                            logger.info(f"✅ Extracted text from event.text")
                else:
                    # Chunk doesn't have .root structure - try to parse directly
                    print(f"⚠️ Chunk doesn't have .root structure, attempting direct parse", file=sys.stderr)
                    logger.warning(f"Chunk doesn't have expected .root structure: {type(chunk)}")
                    
                    # Try to parse chunk directly as an event
                    try:
                        if hasattr(chunk, 'model_dump'):
                            chunk_dict = chunk.model_dump()
                            logger.info(f"Chunk dict keys: {list(chunk_dict.keys())}")
                            print(f"Chunk dict keys: {list(chunk_dict.keys())}", file=sys.stderr)
                        
                        # Try common attributes
                        if hasattr(chunk, 'text'):
                            response_text += str(chunk.text)
                            print(f"✅ Extracted from chunk.text", file=sys.stderr)
                        elif hasattr(chunk, 'content'):
                            response_text += str(chunk.content)
                            print(f"✅ Extracted from chunk.content", file=sys.stderr)
                        elif hasattr(chunk, 'message'):
                            response_text += str(chunk.message)
                            print(f"✅ Extracted from chunk.message", file=sys.stderr)
                    except Exception as e:
                        logger.error(f"Error parsing chunk directly: {e}")
                        print(f"❌ Error parsing chunk: {e}", file=sys.stderr)
        else:
            # Use non-streaming
            request = SendMessageRequest(
                id=str(uuid4()),
                params=message_payload
            )
            
            logger.info("\n" + "="*70)
            logger.info("📤 SENDING NON-STREAMING REQUEST")
            logger.info("="*70)
            
            response = await a2a_client.send_message(request)
            
            logger.info("\n" + "="*70)
            logger.info("📥 RAW RESPONSE RECEIVED")
            logger.info("="*70)
            logger.info(f"Type: {type(response)}")
            logger.info(f"Response: {response}")
            
            # Try to dump it
            try:
                if hasattr(response, 'model_dump'):
                    import json
                    logger.info(f"Dumped: {json.dumps(response.model_dump(), indent=2, default=str)}")
                elif hasattr(response, '__dict__'):
                    logger.info(f"Dict: {response.__dict__}")
            except Exception as e:
                logger.info(f"Could not dump: {e}")
            
            logger.info("="*70 + "\n")
            
            # Extract text from response - response is SendMessageResponse
            if hasattr(response, 'root'):
                # Check if it's a success response
                if hasattr(response.root, 'result'):
                    event = response.root.result
                    
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
            logger.info(f"Debug data written to {debug_file_path}")
        except Exception as e:
            logger.error(f"Failed to write debug file: {e}")
        
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
        if not response_text:
            logger.warning("\n" + "="*70)
            logger.warning("⚠️  NO TEXT EXTRACTED FROM AGENT RESPONSE")
            logger.warning("="*70)
            
            # Show simple warning message (debug info will be in the UI debug expander)
            response_text = f"⚠️ **No text content extracted from agent response.**\n\n💡 Check the Debug Info section below for details."
            
            logger.warning(f"Final error message: {response_text[:500]}")
            
            # Also print to console for visibility
            print("\n" + "="*70)
            print("🚨 A2A CLIENT: NO TEXT EXTRACTED")
            print("="*70)
            print(f"Chunks received: {len(raw_chunks_debug)}")
            print(f"Debug file: {debug_file_path}")
            print("="*70 + "\n")
        else:
            logger.info("\n" + "="*70)
            logger.info("✅ FINAL AGENT RESPONSE")
            logger.info(f"📊 Total length: {len(response_text)} characters")
            logger.info(f"📝 Content preview: {response_text[:300]}...")
            logger.info("="*70 + "\n")
            
            # Debug info is NOT appended - it will be shown in the UI debug expander
        
        return response_text

