"""AgentFacts management and persistence."""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


AGENTFACTS_FILE = Path(__file__).parent / "agentfacts.json"


def load_agentfacts() -> Dict[str, Any]:
    """Load agent facts from file."""
    if AGENTFACTS_FILE.exists():
        try:
            with AGENTFACTS_FILE.open('r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    
    # Return default empty structure
    return {
        "core_identity": {
            "agent_id": "",
            "name": "Calendar Agent",
            "version": "1.0.0",
            "created": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "ttl": 3600
        },
        "baseline_model": {
            "foundation_model": "GPT-4",
            "model_version": "gpt-4",
            "model_provider": "OpenAI"
        },
        "classification": {
            "agent_type": "assistant",
            "operational_level": "supervised",
            "stakeholder_context": "consumer",
            "deployment_scope": "external",
            "interaction_mode": "synchronous"
        },
        "capabilities": {
            "tool_calling": ["MCP", "function_calls", "A2A"],
            "interface_types": ["REST API", "MCP", "A2A"],
            "domain_expertise": ["calendar", "scheduling"],
            "protocols": ["MCP", "A2A"]
        },
        "a2a": {
            "enabled": True,
            "agent_card_endpoint": "/.well-known/agent-card.json",
            "tools": [
                {
                    "name": "requestAvailableSlots",
                    "description": "Request available time slots for a meeting"
                },
                {
                    "name": "requestBooking",
                    "description": "Request a booking for a meeting at a specific time"
                },
                {
                    "name": "deleteBooking",
                    "description": "Delete or cancel a booking by event ID"
                }
            ]
        }
    }


def save_agentfacts(facts: Dict[str, Any]) -> bool:
    """Save agent facts to file."""
    try:
        # Update timestamps
        if "core_identity" in facts:
            if "created" not in facts["core_identity"] or not facts["core_identity"]["created"]:
                facts["core_identity"]["created"] = datetime.now().isoformat()
            facts["core_identity"]["last_updated"] = datetime.now().isoformat()
        
        with AGENTFACTS_FILE.open('w', encoding='utf-8') as f:
            json.dump(facts, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving agent facts: {e}")
        return False


def update_agent_id(agent_id: str):
    """Update the agent_id in agent facts."""
    facts = load_agentfacts()
    if "core_identity" not in facts:
        facts["core_identity"] = {}
    facts["core_identity"]["agent_id"] = agent_id
    save_agentfacts(facts)

