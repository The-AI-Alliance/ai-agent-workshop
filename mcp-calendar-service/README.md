# Service to schedule meetings using MCP

The MCP service allows agents to schedule time on your calendar


## Prerequisites

1. Laptop
2. Installed software:
    - Git
    - Python
    - uv
3. An OpenAPI key from [OpenAI](https://platform.openai.com/api-keys)


## Quickstart

1. Clone this Git repository

```bash
cd <your-project-directory>
git clone git@github.com:The-AI-Alliance/ai-agent-workshop.git
cd ai-agent-workshop
cd mcp-calendar-service
```

2. Use uv to manage and set up your Python project

```bash
uv init
uv add mcp
uv add openai
```

3. Add your LLM keys

- Create an mcp_agent.secrets.yaml
- [example file](https://github.com/lastmile-ai/mcp-agent/blob/main/examples/basic/mcp_basic_agent/mcp_agent.secrets.yaml.example)

4. Start the server

```bash
uv run main.py
```
