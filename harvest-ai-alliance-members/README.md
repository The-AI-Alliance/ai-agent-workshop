# Harvest Agent to create a summary for each company in the AI Alliance

This agent uses a master list of AI Alliance company URLs and then scrapes
each website to summarize what they do.

The summaries are stored in the local filesystem.


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
git clone git@github.com:agentic-profile/ai-summit-2025-nov-workshops.git
cd ai-summit-2025-nov-workshops
cd harvest-ai-alliance-members
```

2. Use uv to manage and set up your Python project

```bash
uv init
uv add mcp-agent
uv add openai
```

3. Add your LLM keys

- Create an mcp_agent.secrets.yaml
- [example file](https://github.com/lastmile-ai/mcp-agent/blob/main/examples/basic/mcp_basic_agent/mcp_agent.secrets.yaml.example)

4. Run harvest

```bash
uv run harvest.py
```
