# type: ignore
"""Base Agent class with DID Peer support and service endpoints."""
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path
import json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import base58

# Import ngrok for public URLs (required)
try:
    from pyngrok import ngrok
    NGROK_AVAILABLE = True
except ImportError:
    import sys
    print("❌ ERROR: pyngrok is not installed. Please install it with: pip install pyngrok")
    sys.exit(1)

# Import did:peer:2 implementation
try:
    from common.did_peer_2 import generate, resolve, KeySpec, PurposeCode
    DID_PEER_AVAILABLE = True
except ImportError as e:
    DID_PEER_AVAILABLE = False
    generate = None
    resolve = None
    KeySpec = None
    PurposeCode = None
    logging.warning(f"Could not import did_peer_2: {e}")

logger = logging.getLogger(__name__)

class Agent:
    """Base Agent class that creates a did:peer on initialization and manages service endpoints.
    
    This class combines the BaseAgent interface (agent_name, description, content_types)
    with DID Peer support and service endpoint management.
    """
    
    def __init__(self, name: str = "Calendar Agent", host: str = "localhost", 
                 a2a_port: int = 10000, mcp_port: int = 8000,
                 description: str = "", content_types: list[str] = None,
                 agent_name: str = None):
        """
        Initialize the Agent with DID Peer and service endpoints.
        
        Args:
            name: Agent name (also used as agent_name if agent_name not provided)
            host: Host for service endpoints
            a2a_port: Port for A2A service endpoint
            mcp_port: Port for MCP service endpoint
            description: A brief description of the agent's purpose
            content_types: Supported content types (default: ['application/json'])
            agent_name: Explicit agent name (overrides name if provided)
        """
        # BaseAgent fields - support both name and agent_name for compatibility
        self.agent_name = agent_name or name
        self.name = self.agent_name  # Keep for backward compatibility
        self.description = description or f"{self.agent_name} - Autonomous AI agent with DID Peer support"
        self.content_types = content_types or ['application/json']
        
        # Service endpoint configuration
        self.host = host
        self.a2a_port = a2a_port
        self.mcp_port = mcp_port
        
        # Store keys for service updates
        self._keys: List[KeySpec] = []
        
        # Setup ngrok tunnels if available
        self.a2a_url = self._get_endpoint_url(a2a_port)
        self.mcp_url = self._get_endpoint_url(mcp_port, path="/mcp/calendar")
        
        # Create or load DID Peer
        logger.info(f"🔐 Initializing DID for agent: {self.agent_name}")
        self.did = self._get_or_create_did()
        self.did_doc = None
        
        # Resolve DID document if available (only for did:peer:2)
        if DID_PEER_AVAILABLE and self.did and self.did.startswith("did:peer:2"):
            try:
                logger.debug(f"Resolving DID document for: {self.did}")
                self.did_doc = resolve(self.did)
                logger.debug(f"Successfully resolved DID document")
            except Exception as e:
                logger.warning(f"⚠️  Error resolving DID document: {e}")
                print(f"⚠️  Error resolving DID document: {e}")
                import traceback
                logger.debug(traceback.format_exc())
        
        # Initialize service endpoints
        logger.info(f"🔗 Setting up service endpoints for agent: {self.agent_name}")
        self._setup_service_endpoints()
        
        # Final initialization log
        logger.info(f"✅ Agent '{self.name}' initialized with DID: {self.did}")
        logger.info(f"   A2A endpoint: {self.a2a_url}")
        logger.info(f"   MCP endpoint: {self.mcp_url}")
        print(f"✅ Agent '{self.name}' initialized with DID: {self.did}")
        print(f"   A2A endpoint: {self.a2a_url}")
        print(f"   MCP endpoint: {self.mcp_url}")
    
    def _get_endpoint_url(self, port: int, path: str = "") -> str:
        """
        Get the endpoint URL, using ngrok if available, otherwise localhost.
        Checks for existing tunnels before creating new ones.
        
        Args:
            port: The port number
            path: Optional path to append
            
        Returns:
            The endpoint URL
        """
        if NGROK_AVAILABLE and ngrok:
            try:
                # Check for existing tunnels first to avoid creating duplicates
                tunnels = ngrok.get_tunnels()
                existing_tunnel = None
                for tunnel in tunnels:
                    # Check if tunnel points to the same port
                    # Tunnel config addr can be in various formats: "localhost:8000", "127.0.0.1:8000", "8000", ":8000"
                    tunnel_addr = str(tunnel.config.get('addr', '')).strip()
                    # Check various possible formats
                    port_str = str(port)
                    if (tunnel_addr == f'localhost:{port}' or 
                        tunnel_addr == f'127.0.0.1:{port}' or 
                        tunnel_addr == port_str or 
                        tunnel_addr.endswith(f':{port}') or
                        tunnel_addr == f':{port}'):
                        existing_tunnel = tunnel
                        print(f"🔍 Found existing tunnel for port {port}: {tunnel.public_url} (addr: {tunnel_addr})")
                        break
                
                if existing_tunnel:
                    # Reuse existing tunnel
                    public_url = existing_tunnel.public_url.rstrip('/')
                    print(f"✅ Reusing existing ngrok tunnel for port {port}: {public_url}")
                    return f"{public_url}{path}"
                else:
                    # Create new tunnel only if no existing one found
                    tunnel = ngrok.connect(port, "http")
                    public_url = tunnel.public_url.rstrip('/')
                    print(f"✅ Created new ngrok tunnel for port {port}: {public_url}")
                    return f"{public_url}{path}"
            except Exception as e:
                print(f"⚠️  ngrok not available ({e}), falling back to localhost")
                return f"http://{self.host}:{port}{path}"
        else:
            return f"http://{self.host}:{port}{path}"
    
    def _is_ngrok_url(self, url: str) -> bool:
        """
        Check if a URL is an ngrok URL.
        
        Args:
            url: The URL to check
            
        Returns:
            True if it's an ngrok URL, False otherwise
        """
        return url.startswith("https://") and (".ngrok.io" in url or ".ngrok-free.app" in url or ".ngrok.app" in url)
    
    def _get_or_create_did(self) -> str:
        """Get existing DID or create a new one."""
        logger.info(f"🔍 Getting or creating DID for agent: {self.agent_name}")
        
        if not DID_PEER_AVAILABLE:
            logger.error("❌ did:peer:2 implementation not available. Please ensure did_peer2.py is present.")
            print("❌ did:peer:2 implementation not available. Please ensure did_peer2.py is present.")
            return "did:peer:error"
        
        # Try to load existing DID from file
        did_path = Path(__file__).parent / "agent_did.txt"
        logger.debug(f"Checking for existing DID at: {did_path}")
        
        if did_path.exists():
            try:
                with did_path.open("r", encoding="utf-8") as f:
                    did = f.read().strip()
                    if did.startswith("did:peer:2"):
                        # Check if it's the new format (has dots and purpose codes)
                        # New format: did:peer:2.Vz... or did:peer:2.Ez... etc.
                        # Old format: did:peer:2<hash> (no dots, no purpose codes)
                        if "." in did and len(did) > 12 and did[10] == ".":
                            # Valid new did:peer:2 format, return it
                            logger.info(f"🔑 Loaded existing DID for {self.agent_name}: {did}")
                            print(f"🔑 Loaded existing DID for {self.agent_name}: {did}")
                            
                            # Extract keys from existing DID document so we can add services later
                            try:
                                logger.debug("Extracting keys from existing DID document...")
                                current_doc = resolve(did)
                                if "verificationMethod" in current_doc:
                                    for vm in current_doc["verificationMethod"]:
                                        if "publicKeyMultibase" in vm:
                                            # Determine purpose from verification relationships
                                            purpose_code = "V"  # Default to authentication
                                            key_id = f"#{vm['id'].split('#')[-1]}"
                                            if "authentication" in current_doc and key_id in current_doc.get("authentication", []):
                                                purpose_code = "V"
                                            elif "keyAgreement" in current_doc and key_id in current_doc.get("keyAgreement", []):
                                                purpose_code = "E"
                                            elif "assertionMethod" in current_doc and key_id in current_doc.get("assertionMethod", []):
                                                purpose_code = "A"
                                            elif "capabilityInvocation" in current_doc and key_id in current_doc.get("capabilityInvocation", []):
                                                purpose_code = "I"
                                            elif "capabilityDelegation" in current_doc and key_id in current_doc.get("capabilityDelegation", []):
                                                purpose_code = "D"
                                            
                                            # Use PurposeCode from did_peer_2 module
                                            try:
                                                purpose_enum = PurposeCode(purpose_code)
                                                self._keys.append(KeySpec(purpose_enum, vm["publicKeyMultibase"]))
                                                logger.debug(f"Extracted key with purpose {purpose_code}")
                                            except ValueError as e:
                                                logger.warning(f"Invalid purpose code {purpose_code}: {e}")
                                                # Try to map to a valid purpose code
                                                purpose_enum = PurposeCode.authentication  # Default fallback
                                                self._keys.append(KeySpec(purpose_enum, vm["publicKeyMultibase"]))
                                                logger.debug(f"Using default authentication purpose for key")
                                    
                                    if self._keys:
                                        logger.info(f"✅ Extracted {len(self._keys)} key(s) from existing DID")
                                    else:
                                        logger.warning("⚠️ No keys extracted from existing DID document")
                                else:
                                    logger.warning("⚠️ No verificationMethod found in DID document")
                            except Exception as e:
                                logger.warning(f"⚠️ Could not extract keys from existing DID: {e}")
                                # Continue anyway - we'll try to extract later when adding services
                            
                            return did
                        else:
                            # Old hash-based format, need to migrate
                            logger.warning(f"⚠️  Found old DID format ({did[:30]}...), migrating to new did:peer:2 format...")
                            print(f"⚠️  Found old DID format ({did[:30]}...), migrating to new did:peer:2 format...")
                            # Delete old file and create new one
                            did_path.unlink()
                    elif did.startswith("did:peer:"):
                        # Very old format, need to migrate
                        logger.warning(f"⚠️  Found old DID format ({did[:20]}...), migrating to did:peer:2...")
                        print(f"⚠️  Found old DID format ({did[:20]}...), migrating to did:peer:2...")
                        # Delete old file and create new one
                        did_path.unlink()
            except Exception as e:
                logger.warning(f"Error reading existing DID file: {e}")
                pass
        
        # Create new DID Peer using did:peer:2 generate function
        logger.info(f"🔨 Creating new DID for agent: {self.agent_name}")
        try:
            # Generate Ed25519 key pair
            logger.debug("Generating Ed25519 key pair...")
            private_key = Ed25519PrivateKey.generate()
            public_key = private_key.public_key()
            
            # Serialize public key to raw bytes
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            
            # Encode as multibase (base58 with 'z' prefix)
            public_key_multibase = "z" + base58.b58encode(public_key_bytes).decode('utf-8')
            logger.debug(f"Generated public key multibase: {public_key_multibase[:20]}...")
            
            # Create KeySpec for authentication
            auth_key = KeySpec.authentication(public_key_multibase)
            self._keys = [auth_key]
            logger.debug("Created authentication KeySpec")
            
            # Store private key for later use (needed if we need to regenerate DID)
            self._private_key = private_key
            logger.debug("Stored private key")
            
            # Generate DID with authentication key and empty services (will add services later)
            logger.info("Generating DID with authentication key...")
            did = generate(keys=self._keys, services=[])
            
            # Log DID creation
            logger.info(f"✅ Created new DID for agent '{self.agent_name}': {did}")
            print(f"✅ Created new DID for agent '{self.agent_name}': {did}")
            
            # Save it
            try:
                with did_path.open("w", encoding="utf-8") as f:
                    f.write(did)
                logger.info(f"💾 Saved DID to {did_path}")
            except Exception as e:
                logger.warning(f"Could not save DID to file: {e}")
            
            return did
        except Exception as e:
            logger.error(f"❌ Error creating DID Peer for {self.agent_name}: {e}")
            print(f"❌ Error creating DID Peer for {self.agent_name}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            traceback.print_exc()
            return "did:peer:error"
    
    def _setup_service_endpoints(self):
        """Setup A2A and MCP service endpoints in the DID document (only if ngrok URLs are available)."""
        if not DID_PEER_AVAILABLE or not self.did:
            return
        
        # Only process did:peer:2 format
        if not self.did.startswith("did:peer:2"):
            print(f"⚠️  Skipping service endpoint setup - DID is not did:peer:2 format: {self.did[:30]}...")
            return
        
        # Only add services to DID if we have ngrok URLs
        if not self._is_ngrok_url(self.a2a_url) or not self._is_ngrok_url(self.mcp_url):
            print(f"⚠️  Skipping service endpoint setup - ngrok URLs not available. Using localhost endpoints.")
            return
        
        try:
            # Ensure we have keys - they should be stored from DID creation or extraction
            if not self._keys:
                logger.warning("⚠️ No keys available for DID regeneration. Extracting from resolved document...")
                logger.debug(f"Resolving DID: {self.did}")
                try:
                    current_doc = resolve(self.did)
                    logger.debug(f"Resolved DID document: {list(current_doc.keys())}")
                    
                    if "verificationMethod" in current_doc:
                        logger.debug(f"Found {len(current_doc['verificationMethod'])} verification method(s)")
                        for vm in current_doc["verificationMethod"]:
                            logger.debug(f"Processing verification method: {vm.get('id', 'unknown')}")
                            if "publicKeyMultibase" in vm:
                                # Determine purpose from verification relationships
                                purpose_code = "V"  # Default to authentication
                                key_id = f"#{vm['id'].split('#')[-1]}"
                                logger.debug(f"Key ID: {key_id}, checking verification relationships...")
                                
                                if "authentication" in current_doc and key_id in current_doc.get("authentication", []):
                                    purpose_code = "V"
                                    logger.debug("Key is for authentication")
                                elif "keyAgreement" in current_doc and key_id in current_doc.get("keyAgreement", []):
                                    purpose_code = "E"
                                    logger.debug("Key is for keyAgreement")
                                elif "assertionMethod" in current_doc and key_id in current_doc.get("assertionMethod", []):
                                    purpose_code = "A"
                                    logger.debug("Key is for assertionMethod")
                                elif "capabilityInvocation" in current_doc and key_id in current_doc.get("capabilityInvocation", []):
                                    purpose_code = "I"
                                    logger.debug("Key is for capabilityInvocation")
                                elif "capabilityDelegation" in current_doc and key_id in current_doc.get("capabilityDelegation", []):
                                    purpose_code = "D"
                                    logger.debug("Key is for capabilityDelegation")
                                
                                # Use PurposeCode from did_peer_2 module
                                try:
                                    purpose_enum = PurposeCode(purpose_code)
                                    key_spec = KeySpec(purpose_enum, vm["publicKeyMultibase"])
                                    self._keys.append(key_spec)
                                    logger.info(f"✅ Extracted key with purpose {purpose_code}: {vm['publicKeyMultibase'][:20]}...")
                                except ValueError as e:
                                    logger.warning(f"Invalid purpose code {purpose_code}: {e}")
                                    # Try to map to a valid purpose code (default to authentication)
                                    try:
                                        purpose_enum = PurposeCode.authentication  # Default fallback
                                        key_spec = KeySpec(purpose_enum, vm["publicKeyMultibase"])
                                        self._keys.append(key_spec)
                                        logger.info(f"✅ Using default authentication purpose for key: {vm['publicKeyMultibase'][:20]}...")
                                    except Exception as e2:
                                        logger.error(f"❌ Could not create KeySpec: {e2}")
                    else:
                        logger.warning("⚠️ No verificationMethod found in resolved DID document")
                        logger.debug(f"DID document keys: {list(current_doc.keys())}")
                except Exception as e:
                    logger.error(f"❌ Error resolving DID or extracting keys: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                
                if not self._keys:
                    logger.error("❌ Could not extract keys from DID document. Cannot add services.")
                    logger.error(f"DID: {self.did}")
                    logger.error("This might happen if:")
                    logger.error("  1. DID document resolution failed")
                    logger.error("  2. DID document has no verificationMethod")
                    logger.error("  3. Key extraction failed (invalid purpose codes)")
                    return
            else:
                logger.debug(f"✅ Using {len(self._keys)} existing key(s) for DID regeneration")
            
            # Resolve to get existing services
            current_doc = resolve(self.did)
            
            # A2A service endpoint
            a2a_service = {
                "type": "A2A",
                "serviceEndpoint": self.a2a_url
            }
            
            # MCP service endpoint
            mcp_service = {
                "type": "MCP",
                "serviceEndpoint": self.mcp_url
            }
            
            # Create services list with ONLY the two services we want (A2A and MCP)
            # Remove any other services and ensure we only have these 2
            services = [a2a_service, mcp_service]
            
            # Check if services have changed by comparing with current document
            current_services = current_doc.get("service", [])
            current_a2a = next((s for s in current_services if s.get("type") == "A2A"), None)
            current_mcp = next((s for s in current_services if s.get("type") == "MCP"), None)
            
            # Only regenerate DID if services have changed
            services_changed = (
                not current_a2a or 
                current_a2a.get("serviceEndpoint") != self.a2a_url or
                not current_mcp or 
                current_mcp.get("serviceEndpoint") != self.mcp_url or
                len([s for s in current_services if s.get("type") in ["A2A", "MCP"]]) != 2
            )
            
            if services_changed:
                # Generate new DID with exactly 2 services (A2A and MCP)
                # Ensure keys are valid
                if not self._keys:
                    logger.error("❌ Cannot regenerate DID: no keys available")
                    return
                
                updated_did = generate(keys=self._keys, services=services)
                
                # Validate the generated DID format
                if not updated_did.startswith("did:peer:2"):
                    logger.error(f"❌ Generated DID has invalid format: {updated_did[:50]}...")
                    return
                
                # Update the DID and save it
                if updated_did != self.did:
                    self.did = updated_did
                    did_path = Path(__file__).parent / "agent_did.txt"
                    try:
                        with did_path.open("w", encoding="utf-8") as f:
                            f.write(self.did)
                        logger.info(f"💾 Saved updated DID to {did_path}")
                    except Exception as e:
                        logger.warning(f"Could not save updated DID: {e}")
                    
                    # Re-resolve the document
                    try:
                        self.did_doc = resolve(self.did)
                        print(f"✅ Updated DID with service endpoints: A2A={self.a2a_url}, MCP={self.mcp_url}")
                    except Exception as e:
                        logger.error(f"❌ Error resolving updated DID: {e}")
                        # Revert to old DID if resolution fails
                        self.did = current_doc.get("id", self.did)
            else:
                print(f"ℹ️  Service endpoints unchanged, keeping existing DID")
                
        except Exception as e:
            print(f"⚠️  Error adding service endpoints: {e}")
            import traceback
            logger.error(traceback.format_exc())
            traceback.print_exc()
    
    def get_did(self) -> str:
        """Get the agent's DID Peer identifier."""
        return self.did
    
    def get_a2a_endpoint(self) -> str:
        """Get the A2A service endpoint URL."""
        return self.a2a_url

    def get_mcp_endpoint(self) -> str:
        """Get the MCP service endpoint URL."""
        return self.mcp_url
    
    def get_service_endpoints(self) -> Dict[str, str]:
        """Get all service endpoints."""
        return {
            "A2A": self.get_a2a_endpoint(),
            "MCP": self.get_mcp_endpoint()
        }


# BaseAgent is an alias/class that agents can inherit from
# It provides the same interface but is a wrapper around Agent for compatibility
class BaseAgent(Agent):
    """Base class for agents that provides DID Peer support.
    
    This class extends Agent and provides the interface expected by CalendarAdminAgent
    and CalendarBookingAgent (agent_name, description, content_types).
    """
    
    def __init__(self, agent_name: str, description: str, content_types: list[str] = None,
                 host: str = "localhost", a2a_port: int = 10000, mcp_port: int = 8000):
        """
        Initialize the BaseAgent with DID Peer support.
        
        Args:
            agent_name: The name of the agent
            description: A brief description of the agent's purpose
            content_types: Supported content types (default: ['application/json'])
            host: Host for service endpoints (optional, defaults to localhost)
            a2a_port: Port for A2A service endpoint (optional, defaults to 10000)
            mcp_port: Port for MCP service endpoint (optional, defaults to 8000)
        """
        # Call parent Agent __init__ with proper parameters
        super().__init__(
            name=agent_name,
            description=description,
            content_types=content_types or ['application/json'],
            host=host,
            a2a_port=a2a_port,
            mcp_port=mcp_port
        )

