# Makefile for a2cal - Calendar Agent with A2A Support
# 
# Quick Start:
#   make install    # Install dependencies with uv
#   make run        # Run the calendar agent
#   make help       # Show all available commands

SHELL := /bin/bash
.PHONY: help install run dev clean test lint format

# Default target
.DEFAULT_GOAL := help

# ---- Help ----
help:
	@echo ""
	@echo "🚀 a2cal - Calendar Agent with A2A Support"
	@echo ""
	@echo "Available commands:"
	@echo ""
	@echo "  make install          Install all dependencies using uv"
	@echo "  make run              Run the calendar agent (MCP + A2A servers + Streamlit UI)"
	@echo "  make dev              Run in development mode with auto-reload"
	@echo "  make test             Run tests (if available)"
	@echo "  make lint             Run linter (ruff)"
	@echo "  make format           Format code (black)"
	@echo "  make clean            Clean build artifacts and cache"
	@echo ""
	@echo "Environment Setup:"
	@echo "  Set GEMINI_API_TOKEN environment variable before running"
	@echo "  Example: export GEMINI_API_TOKEN=your_token_here"
	@echo ""
	@echo "Services:"
	@echo "  • Streamlit UI: http://localhost:8501"
	@echo "  • MCP Server: http://localhost:8000/mcp"
	@echo "  • A2A Server: http://localhost:10000"
	@echo ""

# ---- Installation ----
install:
	@echo "📦 Installing dependencies with uv..."
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "❌ Error: uv is not installed."; \
		echo "   Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi
	uv sync
	@echo "✅ Dependencies installed successfully!"
	@echo ""
	@echo "⚠️  Don't forget to set GEMINI_API_TOKEN:"
	@echo "   export GEMINI_API_TOKEN=your_token_here"

# ---- Run ----
run:
	@echo "🚀 Starting a2cal Calendar Agent..."
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "❌ Error: uv is not installed."; \
		echo "   Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	fi
	@if [ -z "$$GEMINI_API_TOKEN" ]; then \
		echo "⚠️  Warning: GEMINI_API_TOKEN not set"; \
		echo "   Set it with: export GEMINI_API_TOKEN=your_token_here"; \
		echo ""; \
	fi
	@echo "📋 Starting services..."
	@echo "   • MCP Server: http://localhost:8000/mcp"
	@echo "   • A2A Server: http://localhost:10000"
	@echo "   • Streamlit UI: http://localhost:8501"
	@echo ""
	cd src && PYTHONPATH="$(CURDIR)/src:$$PYTHONPATH" uv run python main.py

# ---- Development ----
dev: run

# ---- Testing ----
test:
	@echo "🧪 Running tests..."
	@if [ -d "tests" ]; then \
		uv run pytest tests/ -v; \
	else \
		echo "ℹ️  No tests directory found"; \
	fi

# ---- Linting ----
lint:
	@echo "🔍 Running linter..."
	@if uv run ruff --version >/dev/null 2>&1; then \
		uv run ruff check src/; \
	else \
		echo "ℹ️  ruff not available, skipping lint"; \
	fi

# ---- Formatting ----
format:
	@echo "✨ Formatting code..."
	@if uv run black --version >/dev/null 2>&1; then \
		uv run black src/; \
	else \
		echo "ℹ️  black not available, skipping format"; \
	fi

# ---- Clean ----
clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf __pycache__ */__pycache__ */*/__pycache__
	rm -rf .pytest_cache .ruff_cache
	rm -rf *.egg-info build dist
	rm -rf .uv
	find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "✅ Clean complete!"

