# Match conference attendees to AI Alliance members

This agent uses summarized AI Alliance member data, and attendee data
to find syngergies and then describes those synergies.


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
cd match-attendees
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

4. Provide a summary of you or your startup

- Visit [Venture Agent/Northstar Worksheet](https://example.agenticprofile.ai/agents/venture)
- Fill in as much detail as you'd like
- Scroll down to the Markdown Summary section and "Copy Markdown"
- Paste that text into the northstar.md file in this directory

5. Find your matches

```bash
uv run find-matches.py
```
