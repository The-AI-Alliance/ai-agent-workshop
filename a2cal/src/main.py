"""Main entry point for Calendar Agent - runs the aggregated server."""
import subprocess
import sys
import uvicorn
import argparse
from pathlib import Path

from dotenv import load_dotenv
from pyngrok import ngrok

from agents.server import create_a2a_app
from common.server import get_app, attach_a2a_server, attach_mcp_server
from common.server_state import set_a2a_server_status, set_base_server_url, set_mcp_server_status
from common.utils import config_logging
from mmcp.server import create_mcp_app, serve


def load_environment_variables() -> None:
    """Load environment variables from .env file."""
    # Try loading from src directory
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded .env file from {env_path}")
        return
    
    # Try loading from parent directory
    parent_env = Path(__file__).parent.parent / '.env'
    if parent_env.exists():
        load_dotenv(parent_env)
        print(f"✅ Loaded .env file from {parent_env}")
        return
    
    # Try loading from current working directory
    load_dotenv()
    print(f"ℹ️  No .env file found, using environment variables")


def setup_ngrok(port: int = 8000) -> str:
    """Set up ngrok tunnel for the server.
    
    Args:
        port: Port number for the server (default: 8000)
        
    Returns:
        Public URL from ngrok or localhost URL if ngrok unavailable
    """
    try:
        # Try to get existing tunnels first
        tunnels = ngrok.get_tunnels()
        existing_tunnel = None
        
        for tunnel in tunnels:
            tunnel_addr = str(tunnel.config.get('addr', '')).strip()
            port_str = str(port)
            if (tunnel_addr == f'localhost:{port}' or 
                tunnel_addr == f'127.0.0.1:{port}' or 
                tunnel_addr == port_str or 
                tunnel_addr.endswith(f':{port}') or
                tunnel_addr == f':{port}'):
                existing_tunnel = tunnel
                print(f"🔍 Found existing ngrok tunnel for port {port}: {tunnel.public_url}")
                break
        
        if existing_tunnel:
            ngrok_url = existing_tunnel.public_url.rstrip('/')
        else:
            # Create new ngrok tunnel
            tunnel = ngrok.connect(port, "http")
            ngrok_url = tunnel.public_url.rstrip('/')
        
        print(f"✅ ngrok tunnel ready: {ngrok_url}")
        return ngrok_url
        
    except Exception as e:
        localhost_url = f"http://localhost:{port}"
        print(f"⚠️  ngrok error: {e}")
        print(f"ℹ️  Using localhost URL: {localhost_url}")
        return localhost_url


def launch_streamlit() -> None:
    """Launch streamlit with the UI file in a separate process."""
    # Get the path to the UI file
    ui_path = Path(__file__).parent / "app" / "ui.py"
    print(f"🚀 Launching Streamlit UI on http://localhost:8501...")
    print(f"   File: {ui_path}")
    
    if not ui_path.exists():
        print(f"❌ Error: UI file not found at {ui_path}")
        return
    
    # Launch Streamlit in background (don't hide stderr so we can see errors)
    subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(ui_path), "--server.port=8501", "--server.headless=true"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    # Give Streamlit a moment to start
    import time
    time.sleep(2)


def run_mcp_standalone(host: str = "localhost", port: int = 10100, transport: str = "sse") -> None:
    """Run MCP server standalone on a separate port.
    
    Args:
        host: Host to bind to (default: localhost)
        port: Port to run on (default: 10100)
        transport: Transport type (default: sse)
    """
    print("="*60)
    print("🧪 Running MCP Server Standalone")
    print(f"📍 Host: {host}")
    print(f"🔌 Port: {port}")
    print(f"📡 Transport: {transport}")
    print(f"🌐 URL: http://{host}:{port}/mcp")
    print(f"📡 SSE URL: http://{host}:{port}/mcp/sse")
    print("="*60)
    print("\n🚀 Starting MCP server...")
    print("Press CTRL+C to stop\n")
    
    try:
        serve(host=host, port=port, transport=transport)
    except KeyboardInterrupt:
        print("\n\n⚠️  MCP server stopped by user")
    except Exception as e:
        print(f"\n❌ Error running MCP server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    # Configure logging first (suppress LiteLLM debug logs)
    config_logging()
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="A2Cal Calendar Agent Server")
    parser.add_argument(
        "--mcp-standalone",
        action="store_true",
        help="Run MCP server standalone on port 10100 (instead of integrated server)"
    )
    parser.add_argument(
        "--mcp-port",
        type=int,
        default=10100,
        help="Port for standalone MCP server (default: 10100)"
    )
    parser.add_argument(
        "--mcp-host",
        type=str,
        default="localhost",
        help="Host for standalone MCP server (default: localhost)"
    )
    parser.add_argument(
        "--mcp-transport",
        type=str,
        default="sse",
        choices=["sse", "stdio"],
        help="Transport for standalone MCP server (default: sse)"
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_environment_variables()
    
    # If standalone MCP mode, run just the MCP server
    if args.mcp_standalone:
        run_mcp_standalone(host=args.mcp_host, port=args.mcp_port, transport=args.mcp_transport)
        return
    
    # Otherwise, run the integrated server
    # Launch Streamlit UI in a separate process
    launch_streamlit()
    
    # Create and attach MCP server
    # Note: host/port are ignored when mounting - they're only used for standalone mode
    print("🚀 Initializing MCP server...")
    mcp_app = create_mcp_app()  # Uses shared calendar service
    attach_mcp_server(mcp_app, prefix="/mcp")
    
    # Create and attach A2A agent servers
    # Create both Calendar Admin and Calendar Booking agents
    a2a_started = False
    
    # Calendar Admin Agent
    admin_card_path = Path(__file__).parent / "agent_cards" / "calendar_admin.json"
    if admin_card_path.exists():
        print("🚀 Initializing Calendar Admin A2A agent server...")
        try:
            a2a_app = create_a2a_app(
                str(admin_card_path),
                host="localhost",
                a2a_port=8000,  # A2A is at /agent on port 8000
                mcp_port=8000   # MCP is at /mcp on port 8000
            )
            attach_a2a_server(a2a_app, prefix="/agent")
            a2a_started = True
            print("✅ Calendar Admin Agent server started")
        except Exception as e:
            print(f"⚠️  Warning: Could not attach Calendar Admin A2A agent server: {e}")
            print("   Continuing without Calendar Admin agent server...")
    else:
        print(f"⚠️  Warning: Agent card not found at {admin_card_path}")
    
    # Calendar Booking Agent (register but don't attach as separate server)
    # We'll just register it so it appears in agents.json
    booking_card_path = Path(__file__).parent / "agent_cards" / "calendar_booking.json"
    if booking_card_path.exists():
        print("🚀 Registering Calendar Booking Agent...")
        try:
            # Create the agent to generate DID and register it
            # But don't attach as a separate server (it can use the same MCP server)
            from common.server_state import register_agent_did
            import json
            from a2a.types import AgentCard
            from agents.calendar_booking_agent import CalendarBookingAgent
            
            # Load agent card
            with booking_card_path.open() as f:
                card_data = json.load(f)
            agent_card = AgentCard(**card_data)
            
            # Create agent to generate DID
            agent = CalendarBookingAgent(
                agent_name=agent_card.name,
                description=agent_card.description or 'Calendar Booking Agent',
                instructions="",
                host="localhost",
                a2a_port=8000,
                mcp_port=8000
            )
            
            # Register the agent
            if hasattr(agent, 'get_did'):
                agent_did = agent.get_did()
                agent_card_abs_path = booking_card_path.resolve()
                register_agent_did(agent_did, agent_card.name, str(agent_card_abs_path))
                print(f"✅ Calendar Booking Agent registered with DID: {agent_did}")
        except Exception as e:
            print(f"⚠️  Warning: Could not register Calendar Booking Agent: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"⚠️  Warning: Agent card not found at {booking_card_path}")
    
    # Set up ngrok tunnel
    ngrok_url = setup_ngrok(port=8000)
    
    # Update server state with ngrok URLs (use public URL, not localhost)
    # Check if ngrok_url is actually an ngrok URL (contains ngrok domain) or localhost
    if "localhost" not in ngrok_url and "127.0.0.1" not in ngrok_url:
        # It's an ngrok/public URL
        base_url = ngrok_url
    else:
        # Fallback to localhost
        base_url = f"http://localhost:8000"
    
    mcp_url = f"{base_url}/mcp"
    a2a_url = f"{base_url}/agent" if a2a_started else None
    
    # Update state: MCP server is running
    set_mcp_server_status(started=True, url=mcp_url)
    set_base_server_url(base_url)
    if a2a_started:
        set_a2a_server_status(started=True, url=a2a_url)
    else:
        set_a2a_server_status(started=False)
    
    # Run the aggregated server
    print("\n" + "="*60)
    print("🚀 Starting A2Cal server on http://localhost:8000")
    print("📋 Available endpoints:")
    print("   - Root: http://localhost:8000/")
    print("   - Health: http://localhost:8000/health")
    print("   - MCP: http://localhost:8000/mcp")
    print("   - A2A Agent: http://localhost:8000/agent")
    print("   - Streamlit UI: http://localhost:8501")
    if ngrok_url and ngrok_url.startswith("http"):
        print(f"\n🌐 Public URLs (via ngrok):")
        print(f"   - Root: {ngrok_url}/")
        print(f"   - Health: {ngrok_url}/health")
        print(f"   - MCP: {ngrok_url}/mcp")
        print(f"   - A2A Agent: {ngrok_url}/agent")
    print("="*60 + "\n")
    
    # Get the app instance (created with MCP lifespan by attach_mcp_server)
    app = get_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
