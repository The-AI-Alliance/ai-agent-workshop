# Multi-stage build for a2cal - Agent Calendar App
FROM python:3.13-slim AS builder

# Install uv for fast dependency installation
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy dependency files and README (required by pyproject.toml)
COPY pyproject.toml uv.lock README.md ./

# Install dependencies into /app/.venv
RUN uv sync --frozen --no-dev

# Production stage
FROM python:3.13-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 a2cal && \
    mkdir -p /app /data && \
    chown -R a2cal:a2cal /app /data

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=a2cal:a2cal /app/.venv /app/.venv

# Copy application code
COPY --chown=a2cal:a2cal src/ ./src/
COPY --chown=a2cal:a2cal pyproject.toml ./

# Set Python path to include src directory
ENV PYTHONPATH=/app/src \
    PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    # Database location in mounted volume
    DATABASE_PATH=/data/calendar_agent.db

# Switch to non-root user
USER a2cal

# Expose ports
# 8000 - Main FastAPI server (MCP + A2A)
# 8501 - Streamlit UI
# 10100 - Optional standalone MCP server
EXPOSE 8000 8501 10100

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Default command - run the main application
CMD ["python", "src/main.py"]

# Alternative commands:
# - Standalone MCP server: CMD ["python", "src/main.py", "--mcp-standalone"]
# - Custom MCP port: CMD ["python", "src/main.py", "--mcp-standalone", "--mcp-port", "8080"]
