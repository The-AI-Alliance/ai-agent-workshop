# Allycat Workshop

Allycat repo is here : https://github.com/The-AI-Alliance/allycat

## Prerequisites

1. **Laptop** with modern operating system (macOS, Linux, or Windows)
2. **Installed software:**
   - Git
   - Python 3.11+
   - [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver
3. NEBIUS_API_KEY for Allycat workshop.  Get it [here](https://tokenfactory.nebius.com/).

Get the code

```bash
git   clone    https://github.com/The-AI-Alliance/allycat
cd allycat
```

## Workshop 1

We will start with **RAG-remote** scenario.  It runs LLMs on a cloud inference service.  We will need API keys for the service we will use (e.g. NEBIUS)

[Full details](https://github.com/The-AI-Alliance/allycat/blob/main/rag-remote/README.md)

## Workshop 2

Here we will run **RAG-local** scenario.  Every thing is running on your machine - even the LLMs.  No API Keys required.  But this requires a powerful machine.

[Full details](https://github.com/The-AI-Alliance/allycat/blob/main/rag-local-milvus-ollama/README.md)