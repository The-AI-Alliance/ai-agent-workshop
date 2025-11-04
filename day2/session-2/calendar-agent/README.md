# Calendar Agent

A full-featured calendar agent with Streamlit UI, DID Peer 2 support, and integrated MCP/A2A servers.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- (Optional) ngrok account for public URLs

### Installation

```bash
# Install dependencies
uv sync

# Or using pip
pip install -r requirements.txt
```

### Running the Application

```bash
# Start the Streamlit UI (includes MCP/A2A servers)
uv run streamlit run main.py

# Or using the project script
uv run calendar-agent
```

The application will:
1. Generate a `did:peer:2` identifier for the agent
2. Start the MCP server on port 8000
3. Start the A2A server (merged with MCP) on port 8000
4. Launch the Streamlit UI on port 8501
5. Create ngrok tunnels (if available) for public endpoints

## 📍 Access Points

Once running, you can access:

- **Streamlit UI**: http://localhost:8501
- **MCP Server (SSE)**: http://localhost:8000/sse
- **AgentFacts**: http://localhost:8000/.well-known/agentfacts.json
- **A2A Agent Card**: http://localhost:8000/.well-known/agent-card.json
- **Health Check**: http://localhost:8000/health

## 🔑 Features

### DID Peer 2 Identity

- Automatically generates a `did:peer:2` identifier on startup
- Stores DID in `agent_did.txt`
- Includes service endpoints (A2A and MCP) in DID document when ngrok is available
- DID is used as `agent_id` in AgentFacts

### MCP Server

Exposes calendar tools via MCP:
- `requestAvailableSlots` - Find available time slots for meetings
- `requestBooking` - Book a meeting at a specific time
- `deleteBooking` - Delete or cancel a booking

### A2A Server

A2A protocol support merged with MCP server:
- Agent card at `/.well-known/agent-card.json`
- Request handling at `/a2a/request`
- Same tools available as MCP

### AgentFacts

Metadata about the agent:
- Configure via Streamlit UI
- Accessible at `/.well-known/agentfacts.json`
- Includes core identity, capabilities, and A2A configuration

### Streamlit UI

Interactive web interface for:
- Viewing calendar events
- Booking new meetings
- Configuring AgentFacts
- Setting booking preferences
- Managing events

## 📁 Project Structure

```
calendar-agent/
├── main.py              # Entry point - initializes agent and servers
├── server.py            # MCP server with merged A2A support
├── agent.py             # Agent class with DID and service endpoints
├── agentfacts.py        # AgentFacts loading and saving
├── agentfacts.json      # AgentFacts data (created on first run)
├── agentfacts.jsonschema # AgentFacts schema
├── did_peer2.py         # did:peer:2 specification implementation
├── ui.py                # Streamlit UI components
├── calendar_module.py   # Calendar business logic
├── db_adapter.py        # Database persistence
├── a2a-server.py        # A2A server implementation
└── agent_did.txt        # Stored DID identifier
```

## 🔧 Configuration

### Agent Settings

Edit `agent.py` to customize:

```python
agent = Agent(
    name="Calendar Agent",
    host="localhost",
    a2a_port=8000,
    mcp_port=8000
)
```

### Port Configuration

To change ports, update:
1. `main.py` - Agent initialization
2. `server.py` - Server port in `run_mcp_server()`
3. `ui.py` - Any port references in the UI

### ngrok Setup

For public URLs (optional):

1. Install ngrok: `uv add pyngrok`
2. Configure ngrok (set auth token if required)
3. The agent will automatically create tunnels

Without ngrok, the agent uses localhost URLs.

## 📋 AgentFacts Configuration

1. Start the application
2. Click "Configure AgentFacts" in the sidebar
3. Fill in:
   - Core identity (name, version)
   - Baseline model information
   - Classification (agent type, operational level)
   - Capabilities (tools, interfaces)
   - A2A configuration
4. Click "Save AgentFacts"

The configuration is saved to `agentfacts.json`.

## 🛠️ Development

### Adding New MCP Tools

1. Add tool function to `server.py`:

```python
@mcp.tool
def myNewTool(param1: str, param2: int) -> Dict[str, Any]:
    """Description of the tool."""
    # Implementation
    return {"result": "success"}
```

2. Add corresponding A2A handler in `a2a-server.py`:

```python
def handle_my_new_tool(tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """Handle myNewTool tool call."""
    # Implementation
    return {"success": True}
```

3. Update agent card in `a2a-server.py` to include the tool

### Modifying DID

The DID is generated in `agent.py`. To customize:

1. Edit `_get_or_create_did()` to change key generation
2. Modify `_setup_service_endpoints()` to change service endpoints
3. Update key purposes in `did_peer2.py` if needed

### Database

Events are stored in `calendar_agent.db` (SQLite). The database is managed by `db_adapter.py`.

## 🔍 Troubleshooting

### Port 8000 Already in Use

```bash
# Find process using port 8000
lsof -i :8000

# Kill the process or change port in agent.py
```

### DID Not Generating

- Check console for error messages
- Ensure `did_peer2.py` is present
- Verify dependencies: `uv sync`
- Check file permissions for `agent_did.txt`

### ngrok Not Working

- Install: `uv add pyngrok`
- Check ngrok configuration
- Agent will fall back to localhost automatically

### AgentFacts Not Loading

- Ensure `agentfacts.json` exists (created on first run)
- Check file permissions
- Try deleting and recreating via UI

### MCP Server Not Starting

- Check console output for errors
- Verify FastMCP is installed: `uv sync`
- Ensure port 8000 is available

## 📚 API Reference

### MCP Tools

#### requestAvailableSlots

Find available time slots for a meeting.

**Parameters:**
- `requester_agent_id` (str): DID of requesting agent
- `start_time` (datetime): Earliest start time
- `end_time` (datetime): Latest end time
- `duration` (int): Duration in minutes
- `message` (str, optional): Context message

**Returns:** List of available slots with start/end times

#### requestBooking

Book a meeting at a specific time.

**Parameters:**
- `requester_agent_id` (str): DID of requesting agent
- `start_time` (datetime): Desired start time
- `duration` (int): Duration in minutes
- `message` (str, optional): Context message

**Returns:** Status (SUCCESS/CONFLICT/ERROR) and event_id

#### deleteBooking

Delete a booking by event ID.

**Parameters:**
- `event_id` (str): Event ID to delete

**Returns:** Status and event_id

### A2A Protocol

Same tools as MCP, accessible via POST to `/a2a/request`:

```json
{
  "method": "tools/call",
  "params": {
    "tool_name": "requestAvailableSlots",
    "input": {
      "start_date": "2025-01-15T10:00:00Z",
      "end_date": "2025-01-15T18:00:00Z",
      "duration": "30m"
    }
  }
}
```

## 📝 License

See the main repository LICENSE file.
