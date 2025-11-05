"""Main entry point for Calendar Agent - initializes MCP and A2A servers and runs Streamlit UI."""
import sys
import os
import subprocess
import threading
import importlib.util
from pathlib import Path

# Check if we're being run directly (not via streamlit run)
# If so, automatically launch streamlit
if __name__ == "__main__":
    # Check if streamlit is already running (by checking if 'streamlit' is in sys.argv or sys.modules)
    is_streamlit = any("streamlit" in arg for arg in sys.argv) or "streamlit" in sys.modules
    
    if not is_streamlit:
        # Get the path to this file
        script_path = Path(__file__).resolve()
        # Launch streamlit with this file
        print(f"🚀 Launching Streamlit UI...")
        print(f"   File: {script_path}")
        sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(script_path)]))

# Load .env file at the beginning
try:
    from dotenv import load_dotenv
    # Load .env from the calendar-agent directory
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded .env file from {env_path}")
    else:
        # Try loading from parent directory
        parent_env = Path(__file__).parent.parent / '.env'
        if parent_env.exists():
            load_dotenv(parent_env)
            print(f"✅ Loaded .env file from {parent_env}")
        else:
            # Try loading from current working directory
            load_dotenv()
            print(f"ℹ️  No .env file found, using environment variables")
except ImportError:
    print("⚠️  python-dotenv not installed. Install with: pip install python-dotenv")
    print("   Environment variables must be set manually")

# Import Agent class
from agent import Agent

# Initialize agent with DID Peer - A2A now merged with MCP on port 8000
agent = Agent(name="Calendar Agent", host="localhost", a2a_port=8000, mcp_port=8000)

# Update agentfacts with the DID
try:
    from agentfacts import update_agent_id
    update_agent_id(agent.get_did())
except Exception as e:
    print(f"⚠️  Could not update agentfacts agent_id: {e}")

# Import MCP server
server_spec = importlib.util.spec_from_file_location("server", os.path.join(os.path.dirname(__file__), "server.py"))
server_module = importlib.util.module_from_spec(server_spec)
server_spec.loader.exec_module(server_module)

# Import A2A server
import a2a_server as a2a_module

# Import streamlit - needed for session state and UI
import streamlit as st

# Initialize MCP server in background thread (only once per Streamlit session)
if 'mcp_server_started' not in st.session_state:
    try:
        # Default MCP server configuration
        MCP_HOST = "localhost"
        MCP_PORT = 8000
        
        # Use ngrok URL from agent if available (reuses existing tunnel)
        # The agent instance already has ngrok URLs set up
        MCP_URL = agent.mcp_url  # This already includes ngrok if available
        
        def run_mcp_server():
            try:
                server_module.run_mcp_server(host=MCP_HOST, port=MCP_PORT)
            except Exception as e:
                print(f"⚠️ MCP Server error: {e}")
        
        mcp_thread = threading.Thread(target=run_mcp_server, daemon=True)
        mcp_thread.start()
        st.session_state.mcp_server_started = True
        st.session_state.mcp_server_url = MCP_URL
        print(f"🚀 MCP Server started in background thread at {MCP_URL}")
    except Exception as e:
        print(f"⚠️ Failed to start MCP server: {e}")
        st.session_state.mcp_server_started = False
        st.session_state.mcp_server_url = None

# Import streamlit - needed for session state and UI
import streamlit as st

# A2A server is now merged with MCP server on port 8000
# Use ngrok URL from agent if available (reuses existing tunnel)
A2A_URL = agent.a2a_url  # This already includes ngrok if available
st.session_state.a2a_server_started = True
st.session_state.a2a_server_url = A2A_URL
print(f"✅ A2A server is merged with MCP server on port 8000")
print(f"   A2A endpoints available at: {A2A_URL}/.well-known/agent-card.json")

# Import and run the UI
from ui import main as run_ui

# This block runs when streamlit executes the file
if __name__ == "__main__":
    run_ui()
