"""Main entry point for Calendar Agent - runs Streamlit UI."""
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from pyngrok import ngrok

import streamlit as st
from app.ui import main as run_ui


def is_streamlit_running() -> bool:
    """Check if streamlit is already running."""
    return any("streamlit" in arg for arg in sys.argv) or "streamlit" in sys.modules


def launch_streamlit(script_path: Path) -> None:
    """Launch streamlit with the given script path."""
    print(f"🚀 Launching Streamlit UI...")
    print(f"   File: {script_path}")
    sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(script_path)]))


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


def setup_ngrok(port: int = 8501) -> str:
    """Set up ngrok tunnel for Streamlit.
    
    Args:
        port: Port number for Streamlit (default: 8501)
        
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


def main() -> None:
    """Main entry point."""
    # Load environment variables
    load_environment_variables()
    
    # Set up ngrok (optional)
    setup_ngrok()
    
    # Check if streamlit is already running
    if is_streamlit_running():
        # Streamlit is running, just execute the UI
        run_ui()
    else:
        # Launch streamlit
        script_path = Path(__file__).resolve()
        launch_streamlit(script_path)


if __name__ == "__main__":
    main()
