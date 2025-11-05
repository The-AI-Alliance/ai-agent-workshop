# a2cal

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![MCP](https://img.shields.io/badge/protocol-MCP-blue.svg)
![A2A](https://img.shields.io/badge/protocol-A2A-purple.svg)
![Google ADK](https://img.shields.io/badge/framework-Google%20ADK-orange.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

**A2cal** is an autonomous AI agent system for calendar management and meeting coordination between AI agents. It enables agents to discover each other, propose meetings, negotiate schedules, and manage calendar events through a standardized protocol.

## Goal

The primary goal of a2cal is to demonstrate and enable **autonomous agent-to-agent calendar coordination**. The system allows AI agents to:

- **Discover other agents** through agent cards and semantic search
- **Propose meeting times** with other agents
- **Accept, reject, or negotiate** calendar requests
- **Manage calendar events** with conflict detection and status tracking
- **Persist calendar data** across sessions using SQLite

The system serves as a foundation for building multi-agent systems where agents can autonomously schedule and coordinate meetings with each other, similar to how humans use calendar systems.

## Architecture

a2cal is built on a modern multi-protocol architecture that combines several key technologies:

### Core Components

1. **MCP Server** (`src/mcp/server.py`)
   - Exposes calendar management tools via Model Context Protocol (MCP)
   - Provides tools for: finding agents, booking meetings, managing events, querying availability
   - Uses FastMCP for efficient server implementation
   - Runs on port 8000 (configurable)

2. **A2A Protocol Integration**
   - Implements Agent-to-Agent (A2A) communication protocol
   - Enables agents to discover and communicate with each other
   - Uses A2A SDK for agent card management and messaging

3. **Calendar Service** (`src/services/calendar-service/`)
   - **Calendar API** (`calendar_api.py`): Core calendar logic with event management, conflict detection, and status tracking
   - **Database Adapter** (`db_adapter.py`): SQLite persistence layer for events and preferences

4. **Agent Framework**
   - Built on **Google ADK (Agent Development Kit)**
   - Uses **LiteLLM** for model abstraction (default: Gemini 2.0 Flash)
   - Leverages **MCP Toolset** for tool discovery and execution

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Discovery Layer                     │
│  (Agent Cards with Embeddings, Semantic Search via MCP)     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              AI Agents (CalendarAdmin, CalendarBooking)      │
│  ┌──────────────────────┐  ┌────────────────────────────┐  │
│  │ CalendarAdminAgent   │  │ CalendarBookingAgent       │  │
│  │ (Manages Requests)   │  │ (Books Meetings)           │  │
│  └──────────────────────┘  └────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    MCP Server (Port 8000)                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Tools: find_agent, requestBooking, acceptMeeting,   │  │
│  │         getCalendarEvents, requestAvailableSlots, ... │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Calendar Service Layer                          │
│  ┌──────────────────────┐  ┌────────────────────────────┐  │
│  │   Calendar API       │  │   Database Adapter        │  │
│  │   (Event Management) │  │   (SQLite Persistence)    │  │
│  └──────────────────────┘  └────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Key Technologies

- **MCP (Model Context Protocol)**: Standardized protocol for exposing tools to AI models
- **A2A SDK**: Agent-to-Agent communication framework
- **Google ADK**: Agent Development Kit for building AI agents
- **FastMCP**: High-performance MCP server implementation
- **SQLite**: Lightweight database for event persistence
- **Pydantic**: Data validation and serialization
- **NetworkX**: Workflow graph management (for complex agent workflows)

## Agents

a2cal includes two specialized agents, both built on the Google ADK framework:

### 1. Calendar Admin Agent (`CalendarAdminAgent`)

**Purpose**: Manages incoming calendar requests and makes decisions about accepting or rejecting meeting proposals.

**Capabilities**:
- Reviews incoming meeting proposals
- Accepts or rejects meeting requests based on calendar availability
- Manages calendar preferences and constraints
- Handles meeting confirmations and status updates

**Implementation**: `src/agents/calendar_admin_agent.py`
- Inherits from `BaseAgent`
- Uses Google ADK with LiteLLM model backend
- Connects to MCP server for calendar tools
- Streams responses for real-time interaction

### 2. Calendar Booking Agent (`CalendarBookingAgent`)

**Purpose**: Initiates calendar bookings and proposes meeting times with other agents.

**Capabilities**:
- Finds available time slots
- Proposes meeting times to other agents
- Requests calendar bookings
- Negotiates meeting schedules

**Implementation**: `src/agents/calendar_booking_agent.py`
- Similar architecture to Calendar Admin Agent
- Focused on booking and proposal workflows
- Uses same MCP tools but with different agent instructions

### Agent Communication Flow

1. **Discovery**: Agent uses `find_agent` tool to discover partner agents via semantic search
2. **Proposal**: Booking agent proposes a meeting time using `requestBooking` or `proposeMeeting`
3. **Decision**: Admin agent reviews and accepts/rejects using `acceptMeeting` or `rejectMeeting`
4. **Confirmation**: Meeting is confirmed via `confirmMeeting` and marked as booked

### Agent Base Class

All agents inherit from `BaseAgent` (`src/common/base_agent.py`), which provides:
- Standardized agent interface
- Content type support
- Agent metadata (name, description)

## Repository Structure

```
a2cal/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
│
├── src/
│   ├── main.py                 # Main entry point (Streamlit UI launcher)
│   │
│   ├── agents/                 # Agent implementations
│   │   ├── __main__.py         # Agent server entry point (A2A server)
│   │   ├── calendar_admin_agent.py    # Calendar management agent
│   │   └── calendar_booking_agent.py  # Calendar booking agent
│   │
│   ├── common/                 # Shared utilities and base classes
│   │   ├── agent_executor.py   # Generic agent executor for A2A
│   │   ├── agent_runner.py     # Agent execution runner
│   │   ├── agentfacts.py       # Agent metadata management
│   │   ├── base_agent.py       # Base agent class
│   │   ├── did_peer_2.py        # DID (Decentralized ID) peer management
│   │   ├── prompts.py          # System prompts for various agents
│   │   ├── types.py            # Type definitions
│   │   ├── utils.py            # Utility functions
│   │   └── workflow.py          # Workflow graph management
│   │
│   ├── mcp/                    # Model Context Protocol
│   │   ├── client.py           # MCP client implementation
│   │   └── server.py           # MCP server with calendar tools
│   │
│   └── services/               # Backend services
│       └── calendar-service/
│           ├── calendar_api.py    # Calendar logic and event management
│           └── db_adapter.py       # SQLite database adapter
```

### Key Files

- **`src/mcp/server.py`**: The MCP server that exposes all calendar tools. This is the core integration point between agents and the calendar system.

- **`src/services/calendar-service/calendar_api.py`**: Contains the `Calendar`, `Event`, and `BookingPreferences` classes that handle all calendar logic, conflict detection, and event lifecycle management.

- **`src/services/calendar-service/db_adapter.py`**: SQLite database adapter that persists calendar events and preferences to disk.

- **`src/agents/__main__.py`**: Entry point for running agents as A2A servers. Accepts agent card JSON files and starts the appropriate agent.

- **`src/common/workflow.py`**: Workflow graph management for orchestrating multi-agent tasks.

### MCP Tools Available

The MCP server exposes the following tools:

- `find_agent(query: str)`: Semantic search for agent cards
- `requestAvailableSlots(start_date, end_date, duration)`: Get available time slots
- `requestBooking(time, duration, partner_agent_id)`: Request a calendar booking
- `proposeMeeting(time, duration, partner_agent_id)`: Propose a meeting (alias for requestBooking)
- `acceptMeeting(event_id)`: Accept a proposed meeting
- `rejectMeeting(event_id)`: Reject a proposed meeting
- `confirmMeeting(event_id)`: Confirm an accepted meeting
- `getCalendarEvents(status)`: Get all events, optionally filtered by status
- `getUpcomingEvents(limit)`: Get upcoming confirmed/booked events
- `getPendingRequests()`: Get all pending meeting requests
- `cancelEvent(event_id)`: Cancel an event

### Data Models

- **Event**: Represents a calendar meeting with status lifecycle (proposed → accepted → confirmed → booked)
- **Calendar**: Manages collections of events with conflict detection
- **BookingPreferences**: Configurable preferences for automatic meeting acceptance rules

## Getting Started

### Prerequisites

- Python 3.8+
- Google API key (for Gemini models via LiteLLM)
- A2A SDK installed

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GOOGLE_API_KEY="your-api-key"
export LITELLM_MODEL="gemini/gemini-2.0-flash"  # Optional, defaults to this
```

### Running the MCP Server

```bash
# Start the MCP server
python -m src.mcp.server
```

### Running an Agent

```bash
# Run an agent with an agent card JSON file
python -m src.agents --host localhost --port 10101 --agent-card path/to/agent_card.json
```

## Development

The system is designed to be extensible:

- **Add new agents**: Create new agent classes inheriting from `BaseAgent`
- **Add new tools**: Register new `@mcp.tool()` functions in `src/mcp/server.py`
- **Customize calendar logic**: Modify `src/services/calendar-service/calendar_api.py`
- **Extend persistence**: Add new tables/methods in `src/services/calendar-service/db_adapter.py`

## License

[Specify license if applicable]

---

<div align="center">

**Made with ❤️ for the AI Alliance by [Agent Overlay](https://github.com/agent-overlay)**

</div>
