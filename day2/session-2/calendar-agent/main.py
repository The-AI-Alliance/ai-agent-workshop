"""Main entry point for Calendar Agent - initializes MCP and A2A servers and runs Streamlit UI."""
import streamlit as st
import threading
import os
import importlib.util
from pathlib import Path

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

# Initialize MCP server in background thread (only once per Streamlit session)
if 'mcp_server_started' not in st.session_state:
    try:
        # Default MCP server configuration
        MCP_HOST = "localhost"
        MCP_PORT = 8000
        MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}/sse"
        
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

# A2A server is now merged with MCP server on port 8000
# Set A2A URL to the same port as MCP
A2A_URL = f"http://localhost:8000"
st.session_state.a2a_server_started = True
st.session_state.a2a_server_url = A2A_URL
print(f"✅ A2A server is merged with MCP server on port 8000")
print(f"   A2A endpoints available at: {A2A_URL}/.well-known/agent-card.json")

# Import and run the UI
from ui import main as run_ui

if __name__ == "__main__":
    run_ui()
