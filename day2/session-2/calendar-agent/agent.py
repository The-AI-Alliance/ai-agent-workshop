"""Base Agent class with DID Peer support and service endpoints."""

from typing import Optional, Dict, Any, List
from pathlib import Path
import json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import base58

# Try to import ngrok for public URLs
try:
    from pyngrok import ngrok
    NGROK_AVAILABLE = True
except ImportError:
    NGROK_AVAILABLE = False
    ngrok = None

# Use local did:peer:2 implementation
try:
    from did_peer2 import generate, resolve, KeySpec
    DID_PEER_AVAILABLE = True
    print("✅ Using local did:peer:2 implementation")
except ImportError:
    DID_PEER_AVAILABLE = False
    generate = None
    resolve = None
    KeySpec = None
    print("❌ did:peer:2 implementation not available")


class Agent:
    """Base Agent class that creates a did:peer on initialization and manages service endpoints."""
    
    def __init__(self, name: str = "Calendar Agent", host: str = "localhost", 
                 a2a_port: int = 10000, mcp_port: int = 8000):
        """
        Initialize the Agent with DID Peer and service endpoints.
        
        Args:
            name: Agent name
            host: Host for service endpoints
            a2a_port: Port for A2A service endpoint
            mcp_port: Port for MCP service endpoint
        """
        self.name = name
        self.host = host
        self.a2a_port = a2a_port
        self.mcp_port = mcp_port
        
        # Store keys for service updates
        self._keys: List[KeySpec] = []
        
        # Setup ngrok tunnels if available
        self.a2a_url = self._get_endpoint_url(a2a_port)
        self.mcp_url = self._get_endpoint_url(mcp_port, path="/mcp/calendar")
        
        # Create or load DID Peer
        self.did = self._get_or_create_did()
        self.did_doc = None
        
        # Resolve DID document if available (only for did:peer:2)
        if DID_PEER_AVAILABLE and self.did and self.did.startswith("did:peer:2"):
            try:
                self.did_doc = resolve(self.did)
            except Exception as e:
                print(f"⚠️  Error resolving DID document: {e}")
        
        # Initialize service endpoints
        self._setup_service_endpoints()
        
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
        if NGROK_AVAILABLE:
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
        if not DID_PEER_AVAILABLE:
            print("❌ did:peer:2 implementation not available. Please ensure did_peer2.py is present.")
            return "did:peer:error"
        
        # Try to load existing DID from file
        did_path = Path(__file__).parent / "agent_did.txt"
        
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
                            print(f"🔑 Loaded existing DID: {did}")
                            return did
                        else:
                            # Old hash-based format, need to migrate
                            print(f"⚠️  Found old DID format ({did[:30]}...), migrating to new did:peer:2 format...")
                            # Delete old file and create new one
                            did_path.unlink()
                    elif did.startswith("did:peer:"):
                        # Very old format, need to migrate
                        print(f"⚠️  Found old DID format ({did[:20]}...), migrating to did:peer:2...")
                        # Delete old file and create new one
                        did_path.unlink()
            except Exception:
                pass
        
        # Create new DID Peer using did:peer:2 generate function
        try:
            # Generate Ed25519 key pair
            private_key = Ed25519PrivateKey.generate()
            public_key = private_key.public_key()
            
            # Serialize public key to raw bytes
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            
            # Encode as multibase (base58 with 'z' prefix)
            public_key_multibase = "z" + base58.b58encode(public_key_bytes).decode('utf-8')
            
            # Create KeySpec for authentication
            auth_key = KeySpec.authentication(public_key_multibase)
            self._keys = [auth_key]
            
            # Generate DID with authentication key and empty services (will add services later)
            did = generate(keys=self._keys, services=[])
            
            # Print DID to console
            print(f"🔑 Created new DID: {did}")
            
            # Save it
            try:
                with did_path.open("w", encoding="utf-8") as f:
                    f.write(did)
            except Exception:
                pass
            
            return did
        except Exception as e:
            print(f"❌ Error creating DID Peer: {e}")
            import traceback
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
            # If we don't have keys stored, extract from resolved document
            if not self._keys:
                current_doc = resolve(self.did)
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
                            
                            from did_peer2 import PurposeCode
                            self._keys.append(KeySpec(PurposeCode(purpose_code), vm["publicKeyMultibase"]))
            
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
                updated_did = generate(keys=self._keys, services=services)
                
                # Update the DID and save it
                if updated_did != self.did:
                    self.did = updated_did
                    did_path = Path(__file__).parent / "agent_did.txt"
                    try:
                        with did_path.open("w", encoding="utf-8") as f:
                            f.write(self.did)
                    except Exception:
                        pass
                    
                    # Re-resolve the document
                    self.did_doc = resolve(self.did)
                    print(f"✅ Updated DID with service endpoints: A2A={self.a2a_url}, MCP={self.mcp_url}")
            else:
                print(f"ℹ️  Service endpoints unchanged, keeping existing DID")
                
        except Exception as e:
            print(f"⚠️  Error adding service endpoints: {e}")
            import traceback
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

