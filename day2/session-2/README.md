# AI Agent Workshop - Session 2

This repository contains a calendar agent implementation with support for Decentralized Identifiers (DIDs), MCP (Model Context Protocol), and A2A (Agent-to-Agent) protocols.

## 📁 Repository Structure

```
session-2/
├── calendar-agent/          # Full-featured calendar agent with UI
│   ├── main.py              # Entry point (Streamlit UI)
│   ├── server.py             # MCP server with merged A2A support
│   ├── agent.py             # Agent class with DID Peer support
│   ├── agentfacts.py        # AgentFacts management
│   ├── did_peer2.py         # did:peer:2 implementation
│   ├── ui.py                # Streamlit UI components
│   └── ...
│
├── mcp-calendar-service/    # Standalone MCP calendar service
│   ├── main.py              # FastMCP calendar service
│   ├── agent.py             # Agent class with DID support
│   └── ...
│
└── registry/                # Agent registry (if applicable)
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** (for calendar-agent) or **Python 3.12+** (for mcp-calendar-service)
- **uv** package manager ([install uv](https://github.com/astral-sh/uv))
- **Git**

### Option 1: Calendar Agent (Recommended)

The calendar agent is a full-featured implementation with:
- **Streamlit UI** for managing calendar events
- **DID Peer 2** support for decentralized identity
- **MCP Server** on port 8000
- **A2A Server** merged with MCP on port 8000
- **AgentFacts** metadata endpoint
- **ngrok** support for public URLs

#### Setup and Run

```bash
cd calendar-agent

# Install dependencies using uv
uv sync

# Run the application
uv run streamlit run main.py
```

The application will:
- Start the Streamlit UI at `http://localhost:8501`
- Start the MCP/A2A server on port 8000
- Generate a `did:peer:2` identifier for the agent
- Create ngrok tunnels (if available) for public endpoints

#### Access Points

- **Streamlit UI**: http://localhost:8501
- **MCP Server (SSE)**: http://localhost:8000/sse
- **AgentFacts**: http://localhost:8000/.well-known/agentfacts.json
- **A2A Agent Card**: http://localhost:8000/.well-known/agent-card.json
- **Health Check**: http://localhost:8000/health

### Option 2: MCP Calendar Service

A standalone MCP calendar service without the UI.

#### Setup and Run

```bash
cd mcp-calendar-service

# Install dependencies
uv sync

# Run the service
uv run main.py
```

The service will start on port 8000 with the MCP endpoint at `/mcp/calendar`.

## 🔑 Key Features

### DID Peer 2 Support

The agent automatically generates a `did:peer:2` identifier on startup. This DID:
- Is stored in `agent_did.txt`
- Includes service endpoints (A2A and MCP) when ngrok URLs are available
- Can be resolved to a DID document
- Is used as the `agent_id` in AgentFacts

### AgentFacts

AgentFacts provide metadata about the agent:
- Core identity (agent_id, name, version)
- Baseline model information
- Classification (agent type, operational level)
- Capabilities (tools, interfaces, protocols)
- A2A configuration

Access AgentFacts at: `http://localhost:8000/.well-known/agentfacts.json`

### MCP Tools

The MCP server exposes these tools:
- `requestAvailableSlots` - Find available time slots
- `requestBooking` - Book a meeting
- `deleteBooking` - Delete a booking

### A2A Protocol

The A2A server is merged with the MCP server and provides:
- Agent card at `/.well-known/agent-card.json`
- Request handling at `/a2a/request`
- Same tools as MCP (requestAvailableSlots, requestBooking, deleteBooking)

### ngrok Integration

If `pyngrok` is installed and configured, the agent will:
- Create public URLs for A2A and MCP endpoints
- Add these public URLs to the DID document
- Fall back to localhost if ngrok is unavailable

## 📋 Configuration

### Agent Configuration

Edit `calendar-agent/agent.py` or `mcp-calendar-service/agent.py` to customize:
- Agent name
- Host and ports
- Service endpoints

### AgentFacts Configuration

1. Start the Streamlit UI
2. Click "Configure AgentFacts" in the sidebar
3. Fill in your agent's metadata
4. Save the configuration

The AgentFacts are stored in `calendar-agent/agentfacts.json`.

## 🛠️ Development

### Project Structure

**calendar-agent/**
- `main.py` - Entry point that initializes agent, MCP server, and Streamlit UI
- `server.py` - MCP server implementation with merged A2A support
- `agent.py` - Agent class managing DID and service endpoints
- `agentfacts.py` - AgentFacts loading and saving
- `did_peer2.py` - did:peer:2 specification implementation
- `ui.py` - Streamlit UI for calendar management
- `calendar_module.py` - Calendar business logic
- `db_adapter.py` - Database persistence

**mcp-calendar-service/**
- `main.py` - FastMCP calendar service
- `agent.py` - Agent class with DID support
- `did_peer2.py` - did:peer:2 implementation

### Adding New Tools

1. Add the tool function to `server.py` with the `@mcp.tool` decorator
2. Add corresponding handler in `a2a-server.py` if needed
3. Update the agent card in `a2a-server.py` to include the new tool

### Customizing DID

The DID is generated using Ed25519 keys. To customize:
1. Modify `_get_or_create_did()` in `agent.py`
2. Adjust key purposes (authentication, key agreement, etc.)
3. Update service endpoints as needed

## 🔍 Troubleshooting

### Port Already in Use

If port 8000 is already in use:
```python
# Edit agent initialization in main.py or server.py
agent = Agent(name="Calendar Agent", host="localhost", a2a_port=8001, mcp_port=8001)
```

### ngrok Not Working

If ngrok is not available:
- The agent will fall back to localhost URLs
- Service endpoints in the DID will only be added when ngrok URLs are available
- Install ngrok: `pip install pyngrok` or `uv add pyngrok`

### DID Not Generating

Check:
1. `did_peer2.py` is present in the project
2. Dependencies are installed: `uv sync`
3. Check console output for error messages

### AgentFacts Not Found

Ensure:
1. `agentfacts.json` exists (created automatically on first run)
2. The Streamlit UI has been run at least once
3. Check file permissions

## 📚 Additional Resources

- [DID Peer 2 Specification](https://identity.foundation/peer-did-method-spec/)
- [MCP Documentation](https://modelcontextprotocol.io/)
- [A2A Protocol](https://a2a-protocol.org)
- [AgentFacts Schema](https://agentfacts.org)

## 🎯 Workshop Goals

This implementation demonstrates:
- ✅ DID-based agent identity
- ✅ MCP protocol integration
- ✅ A2A protocol support
- ✅ AgentFacts metadata
- ✅ Calendar booking and scheduling
- ✅ Public endpoint exposure via ngrok

## 📝 License

See the main repository LICENSE file.
