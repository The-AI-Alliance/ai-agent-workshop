# AI Summit Fall 2025 - Workshops

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![MCP](https://img.shields.io/badge/protocol-MCP-blue.svg)
![A2A](https://img.shields.io/badge/protocol-A2A-purple.svg)

This repo contains the example code for several of the workshops that will be held at the [Fall 2025 AI Summit](https://techequity-ai.org/)

## Workshops

- **[Allycat](allycat/)** - Chat with a website using LLM.  And expose the functionality via MCP so other tools / agents can use it.
- **[Harvest AI Alliance Member Data Agent](./harvest-ai-alliance-members/)** - Web scraping agent that creates summaries for each company in the AI Alliance
- **[Match Attendees Agent](./match-attendees/)** - Agent that finds synergies between conference attendees and AI Alliance members
- **[A2cal - Calendar Agent with A2A Support](./a2cal/)** - Autonomous AI agent system for calendar management and meeting coordination between AI agents using the Agent-to-Agent (A2A) protocol

## Getting Started

### Prerequisites

1. **Laptop** with modern operating system (macOS, Linux, or Windows)
2. **Installed software:**
   - Git
   - Python 3.8+
   - [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver
3. **API Keys** - depending on which workshop you're running.  Check setup instructions for workshops.

### Quick Setup

1. **Clone the repository:**
   ```bash
   git clone git@github.com:The-AI-Alliance/ai-agent-workshop.git
   cd ai-agent-workshop
   ```

2. **Navigate to a specific workshop:**
   - For allycat: `cd allycat`  
   - For Harvest Agent: `cd harvest-ai-alliance-members`
   - For Match Attendees: `cd match-attendees`
   - For A2cal Calendar Agent: `cd a2cal`

3. And follow instructions specific to the workshop.  See below.

<!-- 3. **Install dependencies:**
   ```bash
   uv init  # If not already initialized
   uv sync  # Install dependencies from pyproject.toml
   ```

4. **Configure API keys:**
   - Create `mcp_agent.secrets.yaml` in the workshop directory
   - See the [example file](https://github.com/lastmile-ai/mcp-agent/blob/main/examples/basic/mcp_basic_agent/mcp_agent.secrets.yaml.example) for reference

5. **Run the workshop:**
   ```bash
   uv run main.py
   ``` -->


## Workshop 1:  Allycat - Chat with a website using LLMs

Allycat implements **end-to-end RAG pipeline** for website content.

Features:
- crawl a website content
- perform cleanup and extract text from HTML / PDF documents
- index them into a vector database with embeddings
- And query the documents using LLMs (running locally or remotely)
- And expose the RAG functionality as an MCP server.

[See full README](allycat/README.md)

## Workshop 2: Harvest AI Alliance Member Data Agent

Web scraping agent that creates summaries for each company in the AI Alliance. It uses a master list of AI Alliance company URLs and scrapes each website to summarize what they do.

**Key Features:**
- Scrapes company websites
- Generates summaries using LLM
- Stores results in local filesystem

[See full README](./harvest-ai-alliance-members/README.md)

## Workshop 3: Match Attendees Agent

Agent that uses summarized AI Alliance member data and attendee data to find synergies and describe/score those synergies.

**Key Features:**
- Semantic matching between attendees and members
- Synergy scoring and description
- Markdown summary generation

[See full README](./match-attendees/README.md)

## Workshop 4: A2cal - Calendar Agent with A2A Support

Autonomous AI agent system for calendar management and meeting coordination between AI agents. Enables agents to discover each other, propose meetings, negotiate schedules, and manage calendar events through standardized protocols.

**Key Features:**
- **A2A Protocol Integration** - Agent-to-Agent communication
- **MCP Server** - Model Context Protocol for tool exposure
- **Multi-Agent Coordination** - Agents can autonomously schedule meetings
- **Calendar Management** - Full event lifecycle with conflict detection

**Technologies:**
- A2A SDK for agent-to-agent communication
- Google ADK (Agent Development Kit)
- FastMCP for high-performance MCP server
- SQLite for persistence

[See full README](./a2cal/README.md)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[Specify license if applicable]

---

**Made with ❤️ for the AI Alliance**
