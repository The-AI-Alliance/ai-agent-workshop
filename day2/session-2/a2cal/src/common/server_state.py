"""Shared server state management for communication between main server and UI."""
import json
from pathlib import Path
from typing import Optional

STATE_FILE = Path(__file__).parent.parent / ".server_state.json"


def get_server_state() -> dict:
    """Get current server state from file.
    
    Returns:
        Dictionary with server state information
    """
    if STATE_FILE.exists():
        try:
            with STATE_FILE.open('r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def update_server_state(**updates) -> None:
    """Update server state file with new values.
    
    Args:
        **updates: Key-value pairs to update in the state
    """
    state = get_server_state()
    state.update(updates)
    
    try:
        with STATE_FILE.open('w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not write server state: {e}")


def set_mcp_server_status(started: bool, url: Optional[str] = None) -> None:
    """Set MCP server status and URL.
    
    Args:
        started: Whether the MCP server is running
        url: Public URL of the MCP server (ngrok URL if available)
    """
    update_server_state(
        mcp_server_started=started,
        mcp_server_url=url or "http://localhost:8000/mcp"
    )


def set_a2a_server_status(started: bool, url: Optional[str] = None) -> None:
    """Set A2A server status and URL.
    
    Args:
        started: Whether the A2A server is running
        url: Public URL of the A2A server (ngrok URL if available)
    """
    update_server_state(
        a2a_server_started=started,
        a2a_server_url=url or "http://localhost:8000/agent"
    )


def set_base_server_url(url: str) -> None:
    """Set base server URL (ngrok URL if available).
    
    Args:
        url: Public URL of the base server
    """
    update_server_state(base_server_url=url)


def set_calendar_admin_agent_did(agent_did: str) -> None:
    """Set Calendar Admin Agent DID.
    
    Args:
        agent_did: The DID of the Calendar Admin Agent
    """
    update_server_state(calendar_admin_agent_did=agent_did)


def register_agent_did(agent_did: str, agent_name: str, agent_card_path: str = None) -> None:
    """Register an agent DID with its metadata.
    
    Args:
        agent_did: The DID of the agent
        agent_name: The name of the agent
        agent_card_path: Optional path to the agent card JSON file
    """
    state = get_server_state()
    agents = state.get('agents', {})
    agents[agent_did] = {
        "name": agent_name,
        "agent_card_path": agent_card_path
    }
    update_server_state(agents=agents)


def get_all_agent_dids() -> dict:
    """Get all registered agent DIDs.
    
    Returns:
        Dictionary mapping DIDs to agent metadata
    """
    state = get_server_state()
    return state.get('agents', {})

