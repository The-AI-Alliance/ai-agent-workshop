"""Main entry point for Calendar Agent - initializes MCP and A2A servers and runs Streamlit UI."""
import streamlit as st
import threading
import os
import importlib.util
from pathlib import Path

# Import Agent class
from agent import Agent

# Initialize agent with DID Peer
agent = Agent(name="Calendar Agent", host="localhost", a2a_port=10000, mcp_port=8000)

# Import MCP server
server_spec = importlib.util.spec_from_file_location("server", os.path.join(os.path.dirname(__file__), "server.py"))
server_module = importlib.util.module_from_spec(server_spec)
server_spec.loader.exec_module(server_module)

# Import A2A server
a2a_spec = importlib.util.spec_from_file_location("a2a_server", os.path.join(os.path.dirname(__file__), "a2a-server.py"))
a2a_module = importlib.util.module_from_spec(a2a_spec)
a2a_spec.loader.exec_module(a2a_module)

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

# Initialize A2A server in background thread (only once per Streamlit session)
if 'a2a_server_started' not in st.session_state:
    try:
        # Default A2A server configuration
        A2A_HOST = "localhost"
        A2A_PORT = 10000
        A2A_URL = f"http://{A2A_HOST}:{A2A_PORT}"
        
        def run_a2a_server():
            try:
                print(f"🔧 Attempting to start A2A server on {A2A_HOST}:{A2A_PORT}...")
                print(f"🔧 A2A module available: {hasattr(a2a_module, 'run_a2a_server')}")
                print(f"🔧 A2A SDK available: {getattr(a2a_module, 'A2A_AVAILABLE', False)}")
                if not getattr(a2a_module, 'A2A_AVAILABLE', False):
                    print("❌ A2A SDK is not available. Cannot start server.")
                    print("   Install with: uv add 'a2a-sdk[http-server]'")
                    return
                a2a_module.run_a2a_server(host=A2A_HOST, port=A2A_PORT)
            except Exception as e:
                print(f"⚠️ A2A Server error: {e}")
                import traceback
                traceback.print_exc()
        
        # Check if A2A SDK is available before starting
        if getattr(a2a_module, 'A2A_AVAILABLE', False):
            a2a_thread = threading.Thread(target=run_a2a_server, daemon=True)
            a2a_thread.start()
            st.session_state.a2a_server_started = True
            st.session_state.a2a_server_url = A2A_URL
            print(f"🚀 A2A Server thread started - attempting to start server at {A2A_URL}")
            print(f"   (Server may take a moment to start. Check console for confirmation.)")
        else:
            st.session_state.a2a_server_started = False
            st.session_state.a2a_server_url = None
            print(f"⚠️ A2A SDK not available. Server not started.")
            print(f"   Install with: uv add 'a2a-sdk[http-server]'")
    except Exception as e:
        print(f"⚠️ Failed to start A2A server: {e}")
        st.session_state.a2a_server_started = False
        st.session_state.a2a_server_url = None

# Import and run the UI
from ui import main as run_ui

if __name__ == "__main__":
    run_ui()
