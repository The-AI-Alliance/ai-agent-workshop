"""Main entry point for Calendar Agent - runs the aggregated server."""
import subprocess
import sys
import uvicorn
from pathlib import Path

from dotenv import load_dotenv
from pyngrok import ngrok

from agents.server import create_a2a_app
from common.server import app, attach_a2a_server, attach_mcp_server
from mmcp.server import create_mcp_app


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


def main() -> None:
    """Main entry point."""
    # Load environment variables
    load_environment_variables()
    
    # Launch Streamlit UI in a separate process
    launch_streamlit()
    
    # Create and attach MCP server
    print("🚀 Initializing MCP server...")
    mcp_app = create_mcp_app(host='localhost', port=10100)
    attach_mcp_server(mcp_app, prefix="/mcp")
    
    # Create and attach A2A agent server
    # Use Calendar Manager Agent as default
    agent_card_path = Path(__file__).parent / "agent_cards" / "calendar_admin.json"
    if agent_card_path.exists():
        print("🚀 Initializing A2A agent server...")
        try:
            a2a_app = create_a2a_app(str(agent_card_path))
            attach_a2a_server(a2a_app, prefix="/agent")
        except Exception as e:
            print(f"⚠️  Warning: Could not attach A2A agent server: {e}")
            print("   Continuing without A2A agent server...")
    else:
        print(f"⚠️  Warning: Agent card not found at {agent_card_path}")
        print("   Continuing without A2A agent server...")
    
    # Set up ngrok tunnel
    ngrok_url = setup_ngrok(port=8000)
    
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
    
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
