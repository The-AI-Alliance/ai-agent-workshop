# Makefile
# Repo layout assumptions:
# - submodules/a2a-inspector
# - submodules/mcp-context-forge
# - calendar-agent/
# Requires: git submodules, Node (npm/npx), Python3, and optionally uvx (falls back to pip)

SHELL := /bin/bash
.SUBDIRS:
.PHONY: help all install run stop \
	download-submodules \
	mcp-inspector install-mcp-inspector run-mcp-inspector \
	run-a2a-inspector \
	prepare-a2a \
	context-forge run-context-forge \
	calendar-agent install-calendar-agent run-calendar-agent \
	clean

# ---- Paths ----
SUBMODULES_DIR := submodules
A2A_DIR        := $(SUBMODULES_DIR)/a2a-inspector
FORGE_DIR      := $(SUBMODULES_DIR)/mcp-context-forge
CAL_DIR        := calendar-agent
PIDS_FILE      := .run-pids

# ---- Defaults (safe) ----
all: help

help:
	@echo ""
	@echo "Targets:"
	@echo "  install                  Prepare all assets (submodules, A2A, MCP inspector, calendar-agent)"
	@echo "  run                      Start all services (calendar-agent, context-forge, A2A inspector, MCP inspector)"
	@echo "  stop                     Stop all running services"
	@echo "  download-submodules      Init/update all git submodules"
	@echo "  install-mcp-inspector    npm install @modelcontextprotocol/inspector"
	@echo "  run-mcp-inspector        Launch MCP Inspector via npx"
	@echo "  run-a2a-inspector        chmod +x and run a2a-inspector/scripts/run.sh"
	@echo "  install-calendar-agent   Create venv and install Python deps in ./calendar-agent"
	@echo "  run-calendar-agent       Activate venv and attempt to run calendar agent"
	@echo "  run-context-forge        Create venv (if missing) and run ContextForge gateway"
	@echo "  prepare-a2a             Prepare a2a download" 
	@echo "  clean                    Remove common artifacts"
	@echo ""

# --------------------------------------------------------------------
# 0) Install All (Prepares everything)
# --------------------------------------------------------------------
install:
	@echo "🚀 Installing all dependencies and preparing assets..."
	@echo ""
	$(MAKE) download-submodules
	@echo ""
	$(MAKE) prepare-a2a
	@echo ""
	$(MAKE) install-mcp-inspector
	@echo ""
	$(MAKE) install-calendar-agent
	@echo ""
	@echo "✅ All assets prepared successfully!"
	@echo ""

# --------------------------------------------------------------------
# Run All Services
# --------------------------------------------------------------------
run:
	@echo "🚀 Starting all services..."
	@echo ""
	@rm -f $(PIDS_FILE)
	@touch $(PIDS_FILE)
	@echo "📝 Service PIDs will be stored in $(PIDS_FILE)"
	@echo ""
	@echo "▶️  Starting Calendar Agent..."
	@cd "$(CAL_DIR)" && { \
		if [ ! -d ".venv" ]; then \
			echo "   ⚠️  .venv missing; running install-calendar-agent first..."; \
			$(MAKE) -s install-calendar-agent; \
		fi; \
		source .venv/bin/activate; \
		if [ -f "main.py" ]; then \
			python main.py > /tmp/calendar-agent.log 2>&1 & \
			echo $$! >> ../$(PIDS_FILE); \
			echo "   ✅ Calendar Agent started (PID: $$!)"; \
		elif [ -f "app.py" ]; then \
			python app.py > /tmp/calendar-agent.log 2>&1 & \
			echo $$! >> ../$(PIDS_FILE); \
			echo "   ✅ Calendar Agent started (PID: $$!)"; \
		else \
			echo "   ❌ No main.py or app.py found"; \
		fi; \
	} || true
	@echo ""
	@echo "▶️  Starting Context Forge Gateway..."
	@cd "$(FORGE_DIR)" && { \
		[ -d ".venv" ] || python3 -m venv .venv; \
		source .venv/bin/activate; \
		if command -v uvx >/dev/null 2>&1; then \
			BASIC_AUTH_PASSWORD=pass \
			MCPGATEWAY_UI_ENABLED=true \
			MCPGATEWAY_ADMIN_API_ENABLED=true \
			PLATFORM_ADMIN_EMAIL=admin@example.com \
			PLATFORM_ADMIN_PASSWORD=changeme \
			PLATFORM_ADMIN_FULL_NAME="Platform Administrator" \
			uvx --from mcp-contextforge-gateway mcpgateway --host 0.0.0.0 --port 4444 > /tmp/context-forge.log 2>&1 & \
			echo $$! >> ../$(PIDS_FILE); \
			echo "   ✅ Context Forge started (PID: $$!)"; \
		else \
			pip install --upgrade pip >/dev/null 2>&1; \
			pip install mcp-contextforge-gateway >/dev/null 2>&1; \
			BASIC_AUTH_PASSWORD=pass \
			MCPGATEWAY_UI_ENABLED=true \
			MCPGATEWAY_ADMIN_API_ENABLED=true \
			PLATFORM_ADMIN_EMAIL=admin@example.com \
			PLATFORM_ADMIN_PASSWORD=changeme \
			PLATFORM_ADMIN_FULL_NAME="Platform Administrator" \
			mcpgateway --host 0.0.0.0 --port 4444 > /tmp/context-forge.log 2>&1 & \
			echo $$! >> ../$(PIDS_FILE); \
			echo "   ✅ Context Forge started (PID: $$!)"; \
		fi; \
	} || true
	@echo ""
	@echo "▶️  Starting A2A Inspector..."
	@echo "   Starting frontend build (watch mode)..."
	@cd $(A2A_DIR)/frontend && npm run build -- --watch=forever > /tmp/a2a-inspector-frontend.log 2>&1 & \
		echo $$! >> ../../$(PIDS_FILE); \
		echo "   ✅ A2A Inspector Frontend started (PID: $$!)"
	@sleep 2
	@echo "   Starting backend server..."
	@cd $(A2A_DIR)/backend && uv run app.py > /tmp/a2a-inspector-backend.log 2>&1 & \
		echo $$! >> ../../$(PIDS_FILE); \
		echo "   ✅ A2A Inspector Backend started (PID: $$!)"
	@echo ""
	@echo "▶️  Starting MCP Inspector..."
	@npx @modelcontextprotocol/inspector > /tmp/mcp-inspector.log 2>&1 & \
		echo $$! >> $(PIDS_FILE); \
		echo "   ✅ MCP Inspector started (PID: $$!)"
	@echo ""
	@echo "✅ All services started!"
	@echo ""
	@echo "📊 Services running:"
	@echo "   • Calendar Agent: http://localhost:8000"
	@echo "   • Context Forge: http://localhost:4444"
	@echo "   • A2A Inspector: http://127.0.0.1:5001"
	@echo "   • MCP Inspector: (check logs at /tmp/mcp-inspector.log)"
	@echo ""
	@echo "📝 Logs:"
	@echo "   • Calendar Agent: /tmp/calendar-agent.log"
	@echo "   • Context Forge: /tmp/context-forge.log"
	@echo "   • A2A Inspector Frontend: /tmp/a2a-inspector-frontend.log"
	@echo "   • A2A Inspector Backend: /tmp/a2a-inspector-backend.log"
	@echo "   • MCP Inspector: /tmp/mcp-inspector.log"
	@echo ""
	@echo "🛑 To stop all services, run: make stop"
	@echo ""

stop:
	@echo "🛑 Stopping all services..."
	@if [ -f $(PIDS_FILE) ]; then \
		echo "   Sending SIGTERM to processes..."; \
		while read pid; do \
			[ -z "$$pid" ] && continue; \
			if ps -p $$pid > /dev/null 2>&1; then \
				echo "   Stopping process $$pid (and children)..."; \
				kill -TERM $$pid 2>/dev/null || true; \
				pkill -TERM -P $$pid 2>/dev/null || true; \
			fi; \
		done < $(PIDS_FILE); \
		echo "   Waiting for graceful shutdown..."; \
		sleep 2; \
		echo "   Sending SIGKILL to any remaining processes..."; \
		while read pid; do \
			[ -z "$$pid" ] && continue; \
			if ps -p $$pid > /dev/null 2>&1; then \
				echo "   Force killing process $$pid..."; \
				kill -KILL $$pid 2>/dev/null || true; \
				pkill -KILL -P $$pid 2>/dev/null || true; \
			fi; \
		done < $(PIDS_FILE); \
		rm -f $(PIDS_FILE); \
		echo "✅ All services stopped."; \
	else \
		echo "ℹ️  No PIDs file found. Services may not be running."; \
		echo "   Attempting to find and kill processes by name..."; \
		pkill -f "calendar.*main.py" 2>/dev/null || true; \
		pkill -f "mcpgateway" 2>/dev/null || true; \
		pkill -f "a2a-inspector" 2>/dev/null || true; \
		pkill -f "npm.*build.*watch" 2>/dev/null || true; \
		pkill -f "uv run app.py" 2>/dev/null || true; \
		pkill -f "@modelcontextprotocol/inspector" 2>/dev/null || true; \
		echo "✅ Cleanup attempted."; \
	fi
	@echo ""

# --------------------------------------------------------------------
# 1) Submodules
# --------------------------------------------------------------------
download-submodules:
	@echo "📥 Initializing/updating git submodules..."
	git submodule update --init --recursive

prepare-a2a:
	@echo "🔧 Preparing A2A Inspector..."
	cd $(A2A_DIR) && uv sync && cd frontend && npm install 


# --------------------------------------------------------------------
# 2) MCP Inspector (Node)
# --------------------------------------------------------------------
install-mcp-inspector mcp-inspector:
	@echo "📦 Installing @modelcontextprotocol/inspector..."
	npm install @modelcontextprotocol/inspector

run-mcp-inspector:
	@echo "🧭 Launching MCP Inspector..."
	npx @modelcontextprotocol/inspector

# --------------------------------------------------------------------
# 3) A2A Inspector (submodule script)
# --------------------------------------------------------------------
run-a2a-inspector:
	@echo "🔧 Making run script executable..."
	chmod +x "$(A2A_DIR)/scripts/run.sh"
	@echo "🚀 Running A2A Inspector..."
	cd $(A2A_DIR) && bash "./scripts/run.sh"

# --------------------------------------------------------------------
# 4) MCP Context Forge Gateway (Python)
# --------------------------------------------------------------------
# Creates .venv inside the submodule (first run) and then:
# - If 'uvx' exists, uses it to run the gateway
# - Otherwise falls back to pip installing the gateway and running the entrypoint
run-context-forge context-forge:
	@echo "🐍 Preparing venv for Context Forge (if needed)..."
	cd "$(FORGE_DIR)" && { \
		[ -d ".venv" ] || python3 -m venv .venv; \
		source .venv/bin/activate; \
		if command -v uvx >/dev/null 2>&1; then \
			echo '🚀 Starting ContextForge via uvx...'; \
			BASIC_AUTH_PASSWORD=pass \
			MCPGATEWAY_UI_ENABLED=true \
			MCPGATEWAY_ADMIN_API_ENABLED=true \
			PLATFORM_ADMIN_EMAIL=admin@example.com \
			PLATFORM_ADMIN_PASSWORD=changeme \
			PLUGINS_ENABLED=true \
			PLATFORM_ADMIN_FULL_NAME="Platform Administrator" \
			uvx --from mcp-contextforge-gateway mcpgateway --host 0.0.0.0 --port 4444; \
		else \
			echo 'ℹ️ uvx not found; falling back to pip installation...'; \
			pip install --upgrade pip >/dev/null; \
			pip install mcp-contextforge-gateway >/dev/null; \
			echo '🚀 Starting ContextForge via installed entrypoint...'; \
			BASIC_AUTH_PASSWORD=pass \
			MCPGATEWAY_UI_ENABLED=true \
			MCPGATEWAY_ADMIN_API_ENABLED=true \
			PLATFORM_ADMIN_EMAIL=admin@example.com \
			PLUGINS_ENABLED=true \
			PLATFORM_ADMIN_PASSWORD=changeme \
			PLATFORM_ADMIN_FULL_NAME="Platform Administrator" \
			mcpgateway --host 0.0.0.0 --port 4444; \
		fi; \
	}

# --------------------------------------------------------------------
# 5) Calendar Agent (Python)
# --------------------------------------------------------------------
# Creates venv and installs deps from poetry.lock, requirements.txt, or pyproject.toml
install-calendar-agent calendar-agent:
	@echo "🐍 Setting up calendar-agent environment..."
	cd "$(CAL_DIR)" && { \
		python3 -m venv .venv; \
		source .venv/bin/activate; \
		if [ -f "poetry.lock" ]; then \
			echo "📦 Installing with Poetry..."; \
			pip install --upgrade pip >/dev/null; \
			pip install poetry >/dev/null; \
			poetry install; \
		elif [ -f "requirements.txt" ]; then \
			echo "📦 Installing from requirements.txt..."; \
			pip install --upgrade pip >/dev/null; \
			pip install -r requirements.txt; \
		elif [ -f "pyproject.toml" ]; then \
			echo "📦 Installing from pyproject.toml (PEP 517/518 build)..."; \
			pip install --upgrade pip build >/dev/null; \
			pip install -e .; \
		else \
			echo "⚠️  No recognized dependency file found."; \
		fi; \
	}

# Tries a few common entry points; adjust to your app as needed
run-calendar-agent:
	@echo "▶️ Running calendar-agent..."
	cd "$(CAL_DIR)" && { \
		if [ ! -d ".venv" ]; then \
			echo "ℹ️ .venv missing; running install-calendar-agent first..."; \
			$(MAKE) -s install-calendar-agent; \
		fi; \
		source .venv/bin/activate; \
		if [ -f "main.py" ]; then \
			python main.py; \
		elif [ -f "app.py" ]; then \
			python app.py; \
		elif [ -d "src" ]; then \
			python -m src || { echo '❓ Please customize run-calendar-agent target for your app.'; exit 1; }; \
		else \
			echo '❓ Please customize run-calendar-agent target for your app.'; exit 1; \
		fi; \
	}

# --------------------------------------------------------------------
# Clean
# --------------------------------------------------------------------
clean:
	@echo "🧹 Cleaning common artifacts..."
	rm -rf node_modules
	[ -d "$(CAL_DIR)" ]  && (cd "$(CAL_DIR)"  && rm -rf .venv __pycache__ *.egg-info build dist) || true
	[ -d "$(FORGE_DIR)" ] && (cd "$(FORGE_DIR)" && rm -rf .venv __pycache__ *.egg-info build dist) || true
