# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

### Installation & Setup
```bash
# Install dependencies (preferred method using uv)
make install
# or: uv sync

# Set required environment variables
export GEMINI_API_TOKEN=your_token_here
```

### Running the Application
```bash
# Run the full application (MCP + A2A servers + Streamlit UI)
make run

# Run MCP server standalone on port 10100
cd src && PYTHONPATH="$PWD:$PYTHONPATH" uv run python main.py --mcp-standalone

# Run with custom MCP port
cd src && PYTHONPATH="$PWD:$PYTHONPATH" uv run python main.py --mcp-standalone --mcp-port 8080
```

**Important**: The project uses a src-layout where modules like `mmcp`, `common`, `agents` are in the `src/` directory. When running Python scripts directly, you must:
1. Change to the `src/` directory first
2. Set `PYTHONPATH` to include `src/`
3. Run the script: `cd src && PYTHONPATH="$PWD:$PYTHONPATH" uv run python main.py`

### Other Commands
```bash
make clean          # Clean build artifacts and cache
make help           # Show all available commands
```

### Running Tests (when available)
```bash
make test           # Run pytest tests
uv run pytest tests/ -v  # Run specific tests
```

## Architecture Overview

### System Components

**a2cal** is a multi-agent calendar coordination system with three main layers:

1. **Protocol Layer** (MCP + A2A)
   - **MCP Server** (`src/mmcp/server.py`): Exposes calendar tools via Model Context Protocol on port 8000
   - **A2A Server** (`src/agents/server.py`): Handles agent-to-agent communication via A2A SDK

2. **Agent Layer** (Google ADK + LiteLLM)
   - **CalendarAdminAgent**: Manages incoming meeting requests, accepts/rejects proposals
   - **CalendarBookingAgent**: Initiates bookings, proposes meeting times
   - Both agents inherit from `BaseAgent` and use MCP tools for calendar operations

3. **Service Layer** (Calendar + Database)
   - **Calendar Service** (`src/services/calendar-service/calendar_api.py`): Core calendar logic, event management, conflict detection
   - **Database Adapter** (`src/services/calendar-service/db_adapter.py`): SQLite persistence layer
   - Singleton pattern: All components share one calendar/database instance via `get_shared_calendar_service()`

### Critical Architectural Patterns

**1. Shared Service Pattern**
- Calendar and database are **singletons** - get them via `get_shared_calendar_service()`
- All MCP tools, agents, and UI use the same instance
- Events loaded from database into memory at startup
- Database operations persist immediately

**2. Event Status Lifecycle**
```
proposed → accepted → confirmed → booked
            ↓
         rejected
            ↓
         failed
```
Never skip states. Use appropriate tool for each transition:
- `requestBooking()` → creates "proposed" event
- `acceptMeeting()` → proposed → accepted
- `confirmMeeting()` → accepted → confirmed/booked
- `rejectMeeting()` → any → rejected

**3. Import Pattern Due to src-layout**
All imports assume modules are at top-level:
```python
from mmcp.server import create_mcp_app
from common.utils import get_mcp_server_config
from agents.calendar_admin_agent import CalendarAdminAgent
```
This works because `PYTHONPATH` includes `src/` when running via the Makefile or proper commands.

**4. MCP Tool Error Handling**
- Tools **never raise exceptions** (prevents MCP stream breaks)
- Instead, catch exceptions and return JSON with error details:
```python
try:
    # ... operation
    return result
except Exception as e:
    return {"error": str(e), "status": "failed"}
```

**5. Agent Execution Pattern**
Agents use Google ADK's streaming API:
```python
async def stream(self, query, context_id, task_id):
    async for chunk in self.runner.run_stream(self.agent, query, context_id):
        if chunk.get('type') == 'final_result':
            yield self.get_agent_response(chunk['response'])
```

**6. DID Peer Management**
- Each agent has a `did:peer:2` identifier stored in `src/common/agent_did.txt`
- DIDs include service endpoints (A2A, MCP, AgentFacts)
- Auto-generated with Ed25519 keys
- Discoverable via `.well-known/agentfacts.json`

### Key Directories

```
src/
├── main.py                     # Entry point: orchestrates all servers, launches Streamlit UI
├── agents/                     # Agent implementations (CalendarAdmin, CalendarBooking)
│   └── server.py              # A2A server factory
├── mmcp/                       # Model Context Protocol server/client/tools
│   ├── server.py              # FastMCP server with calendar tools
│   ├── tools.py               # Tool definitions (@mcp.tool decorators)
│   └── client.py              # MCP client for connecting to server
├── common/                     # Shared utilities
│   ├── base_agent.py          # BaseAgent class with DID support
│   ├── agent_executor.py      # GenericAgentExecutor for A2A requests
│   ├── did_peer_2.py          # DID Peer v2 implementation
│   └── workflow.py            # Workflow graph management (NetworkX)
├── services/calendar-service/ # Calendar business logic + persistence
│   ├── calendar_api.py        # Calendar, Event, BookingPreferences classes
│   └── db_adapter.py          # CalendarDBAdapter for SQLite
├── app/ui.py                  # Streamlit UI for calendar visualization
└── agent_cards/               # Agent metadata JSON files
```

### MCP Tools

Available in `src/mmcp/tools.py`, registered with `@mcp.tool()`:
- `find_agent(query)` - Semantic search on agent cards using Gemini embeddings
- `requestBooking()` / `proposeMeeting()` - Create "proposed" events
- `acceptMeeting()` / `rejectMeeting()` - Transition event status
- `confirmMeeting()` - Finalize accepted events as "booked"
- `getCalendarEvents()`, `getUpcomingEvents()`, `getPendingRequests()` - Query events
- `requestAvailableSlots()` - Find free time slots
- `cancelEvent()` - Cancel any event

### Database Schema

SQLite database at `src/calendar_agent.db`:

**events table**:
- `event_id` (TEXT PRIMARY KEY)
- `time` (TEXT, ISO format)
- `duration` (TEXT, e.g. "PT1H")
- `status` (TEXT: proposed/accepted/confirmed/booked/rejected/failed)
- `partner_agent_id` (TEXT)
- `title` (TEXT)
- `created_at`, `updated_at` (TEXT, ISO timestamps)

**preferences table** (single row, id=1):
- Scheduling preferences (preferred hours, days, buffer times, etc.)
- Auto-accept rules
- Timezone settings

### Configuration

**Environment Variables**:
- `GEMINI_API_TOKEN` (required) - Google Gemini API key
- `LITELLM_MODEL` (optional) - Defaults to "gemini/gemini-2.0-flash-exp"
- `DEBUG` (optional) - Enable debug logging for MCP

**Ports**:
- `8000` - Main FastAPI server (MCP at `/mcp`, A2A at `/agent`)
- `8501` - Streamlit UI
- `10100` - Standalone MCP server (when using `--mcp-standalone`)

### Agent Communication Flow

1. **Discovery**: Booking agent calls `find_agent("calendar management")` → finds Admin agent via semantic search
2. **Availability Check**: Calls `requestAvailableSlots()` → gets free time slots
3. **Proposal**: Calls `requestBooking(time, duration, partner_agent_id)` → creates "proposed" event
4. **Review**: Admin agent receives A2A message, calls `getCalendarEvents(status="proposed")`
5. **Decision**: Admin calls `acceptMeeting(event_id)` or `rejectMeeting(event_id)`
6. **Confirmation**: Booking agent calls `confirmMeeting(event_id)` → event becomes "booked"

### Common Development Patterns

**Adding a new MCP tool**:
1. Add tool function in `src/mmcp/tools.py` with `@mcp.tool()` decorator
2. Access shared calendar: `db_adapter, calendar = get_shared_calendar_service()`
3. Return JSON (never raise exceptions)
4. Tool auto-registers and becomes available to agents

**Creating a new agent**:
1. Inherit from `BaseAgent` in `src/common/base_agent.py`
2. Implement `async def init_agent()` to connect to MCP and load tools
3. Implement `async def stream(query, context_id, task_id)` for streaming responses
4. Create agent card JSON in `src/agent_cards/`

**Modifying calendar logic**:
- Edit `src/services/calendar-service/calendar_api.py`
- Calendar class methods: `add_event()`, `update_event_status()`, `get_events()`, `find_conflicts()`
- Changes automatically persist via CalendarDBAdapter

### Known Issues & Workarounds

1. **Module Import Errors**: If you see `ModuleNotFoundError: No module named 'mmcp'`:
   - Ensure you're running from `src/` directory with `PYTHONPATH` set
   - Use `make run` instead of running Python directly

2. **Database Path Issues**: Database uses absolute path resolution in `db_adapter.py` to work across different working directories

3. **ngrok Tunneling**: Main server tries to create ngrok tunnel for public accessibility. If it fails, falls back to localhost URLs

4. **Streamlit Launch**: UI launches as subprocess. Check stderr if it doesn't appear at localhost:8501

### Technologies & Frameworks

- **Google ADK** - Agent orchestration and LLM integration
- **FastMCP** - MCP protocol server implementation
- **A2A SDK** - Agent-to-agent communication protocol
- **LiteLLM** - Model abstraction layer (supports 100+ LLMs)
- **Pydantic** - Data validation and serialization
- **NetworkX** - Workflow graph management
- **SQLAlchemy** (via A2A SDK) - Database ORM
- **Streamlit** - Web UI framework
- **FastAPI/Starlette** - ASGI web framework
