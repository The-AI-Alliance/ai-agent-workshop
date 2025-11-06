"""Base server that aggregates all sub-servers and routers."""
import json
import traceback
import urllib.parse
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from fastmcp.utilities.logging import get_logger
from common.agentfacts import load_agentfacts
from common.server_state import get_all_agent_dids
from common.utils import is_debug

from starlette.applications import Starlette

logger = get_logger(__name__)
DEBUG = is_debug()

# Global app variable - will be recreated with lifespan when MCP is attached
app = None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all incoming requests and their routing."""
    
    async def dispatch(self, request: Request, call_next):
        # Try to match the request to a route
        # Use request.app to get the current app instance (not the global app)
        current_app = request.app
        matched_routes = []
        mount_routes = []
        for route in current_app.routes:
            route_type = type(route).__name__
            if route_type == 'Mount':
                # For Mount routes, check if the path matches
                mount_path = getattr(route, 'path', 'N/A')
                mount_routes.append({
                    "path": mount_path,
                    "type": route_type,
                    "app": type(getattr(route, 'app', None)).__name__ if hasattr(route, 'app') else 'N/A'
                })
                # Try to match
                match, scope = route.matches(request.scope)
                if match:
                    matched_routes.append({
                        "path": mount_path,
                        "type": route_type,
                        "match": match
                    })
            else:
                match, scope = route.matches(request.scope)
                if match:
                    matched_routes.append({
                        "path": getattr(route, 'path', 'N/A'),
                        "type": route_type,
                        "match": match
                    })
        
        logger.info(f"[Request] {request.method} {request.url.path}")
        logger.info(f"[Request] All Mount routes: {mount_routes if mount_routes else 'NONE'}")
        logger.info(f"[Request] Matched routes: {matched_routes if matched_routes else 'NONE'}")
        logger.info(f"[Request] Query params: {dict(request.query_params)}")
        
        response = await call_next(request)
        
        logger.info(f"[Response] {request.method} {request.url.path} -> {response.status_code}")
        return response


def _create_app(lifespan=None):
    """Create FastAPI app with optional lifespan."""
    new_app = FastAPI(
        title="A2Cal Server",
        description="Aggregated server for Calendar Agent with MCP and other services",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Add request logging middleware first (before CORS)
    new_app.add_middleware(RequestLoggingMiddleware)
    
    # Enable CORS for all origins
    new_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return new_app


# Global app variable - will be created with MCP lifespan when MCP is attached
app = None


def _register_routes(app_instance: FastAPI) -> None:
    """Register all routes on the FastAPI app instance."""
    
    @app_instance.get("/")
    async def root():
        """Root endpoint."""
        return {
            "name": "A2Cal Server",
            "version": "1.0.0",
            "status": "running",
            "endpoints": {
                "mcp": "/mcp",
                "health": "/health"
            }
        }

    @app_instance.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy"}

    @app_instance.get("/.well-known/agentfacts.json")
    async def get_agentfacts():
        """Get AgentFacts JSON endpoint."""
        try:
            facts = load_agentfacts()
            return facts
        except Exception as e:
            logger.error(f"Error loading agentfacts: {e}")
            raise HTTPException(status_code=500, detail=f"Error loading agentfacts: {str(e)}")

    @app_instance.get("/.well-known/agent-card.json")
    async def get_agent_card_default(request: Request):
        """Get the default agent card (Calendar Manager Agent) endpoint."""
        try:
            import json
            from pathlib import Path
            from common.server_state import get_server_state
            from fastapi import HTTPException
            
            # Get Calendar Manager Agent DID from server state
            server_state = get_server_state()
            calendar_admin_did = server_state.get('calendar_admin_agent_did')
            
            if not calendar_admin_did:
                # Try to find Calendar Manager Agent from registered agents
                agents = server_state.get('agents', {})
                calendar_admin_did = None
                for did, agent_info in agents.items():
                    if agent_info.get('name') == 'Calendar Manager Agent':
                        calendar_admin_did = did
                        break
                
                if not calendar_admin_did:
                    raise HTTPException(status_code=404, detail="Calendar Manager Agent not found")
            
            # Get agent info
            agents = server_state.get('agents', {})
            agent_info = agents.get(calendar_admin_did)
            
            if not agent_info:
                raise HTTPException(status_code=404, detail="Calendar Manager Agent information not found")
            
            agent_card_path = agent_info.get("agent_card_path")
            
            # Try to find agent card file
            card_path = None
            src_dir = Path(__file__).parent.parent
            agent_cards_dir = src_dir / "agent_cards"
            
            if agent_card_path:
                # Try the provided path first
                card_path = Path(agent_card_path)
                if not card_path.exists():
                    # Try relative to agent_cards directory
                    card_path = agent_cards_dir / Path(agent_card_path).name
                    if not card_path.exists():
                        card_path = None
            
            # If still not found, try calendar_admin.json
            if not card_path or not card_path.exists():
                card_path = agent_cards_dir / "calendar_admin.json"
            
            if not card_path or not card_path.exists():
                raise HTTPException(status_code=404, detail="Calendar Manager Agent card file not found")
            
            # Load agent card
            with card_path.open('r', encoding='utf-8') as f:
                agent_card = json.load(f)
            
            # Inject DID and URL into agent card
            agent_card["did"] = calendar_admin_did
            
            # Build agent URL dynamically from request (use localhost with port from request)
            request_url = request.url
            base_url = f"{request_url.scheme}://{request_url.hostname}"
            if request_url.port:
                base_url = f"{base_url}:{request_url.port}"
            agent_card["url"] = f"{base_url}/agent/"
            
            return agent_card
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error loading agent card: {e}")
            import traceback
            logger.error(traceback.format_exc())
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"Error loading agent card: {str(e)}")

    @app_instance.get("/.well-known/agents.json")
    async def get_agents():
        """Get all registered agent DIDs endpoint."""
        try:
            agents = get_all_agent_dids()
            
            # Format response as list of DIDs with metadata
            agents_list = []
            for agent_did, agent_info in agents.items():
                # URL encode the DID for the agent card URL (DIDs can contain special chars)
                encoded_did = urllib.parse.quote(agent_did, safe='')
                agents_list.append({
                    "did": agent_did,
                    "name": agent_info.get("name", "Unknown"),
                    "agent_card_url": f"/.well-known/{encoded_did}/agent.json"
                })
            
            return {
                "agents": agents_list,
                "count": len(agents_list)
            }
        except Exception as e:
            logger.error(f"Error loading agents: {e}")
            raise HTTPException(status_code=500, detail=f"Error loading agents: {str(e)}")

    @app_instance.get("/.well-known/{agent_did:path}/agent.json")
    async def get_agent_card(agent_did: str, request: Request):
        """Get agent card for a specific agent DID.
        
        Args:
            agent_did: The DID of the agent (URL-encoded if needed, supports path segments)
        """
        try:
            # URL decode the DID in case it was encoded
            agent_did = urllib.parse.unquote(agent_did)
            
            # Get all registered agents
            agents = get_all_agent_dids()
            
            if agent_did not in agents:
                raise HTTPException(status_code=404, detail=f"Agent with DID {agent_did} not found")
            
            agent_info = agents[agent_did]
            agent_card_path = agent_info.get("agent_card_path")
            
            # Try to find agent card file
            card_path = None
            # Get agent_cards directory relative to src directory
            src_dir = Path(__file__).parent.parent
            agent_cards_dir = src_dir / "agent_cards"
            
            if agent_card_path:
                # Try the provided path first
                card_path = Path(agent_card_path)
                if not card_path.exists():
                    # Try relative to agent_cards directory
                    card_path = agent_cards_dir / Path(agent_card_path).name
                    if not card_path.exists():
                        card_path = None
            
            # If still not found, try to find by agent name
            if not card_path or not card_path.exists():
                agent_name = agent_info.get("name", "")
                if agent_name:
                    # Try common agent card name patterns
                    possible_names = [
                        f"{agent_name.lower().replace(' ', '_')}.json",
                        f"{agent_name.lower().replace(' ', '-')}.json",
                        "calendar_admin.json",
                        "calendar_booking.json"
                    ]
                    
                    for name in possible_names:
                        test_path = agent_cards_dir / name
                        if test_path.exists():
                            card_path = test_path
                            break
            
            # If still not found, list all agent cards and try to match
            if not card_path or not card_path.exists():
                all_cards = list(agent_cards_dir.glob("*.json"))
                if len(all_cards) == 1:
                    # If there's only one card, use it
                    card_path = all_cards[0]
                elif len(all_cards) > 1:
                    # Try to match by agent name in the card
                    agent_name_lower = agent_info.get("name", "").lower()
                    for card_file in all_cards:
                        try:
                            with card_file.open('r', encoding='utf-8') as f:
                                card_data = json.load(f)
                                if card_data.get("name", "").lower() == agent_name_lower:
                                    card_path = card_file
                                    break
                        except Exception:
                            continue
            
            if not card_path or not card_path.exists():
                raise HTTPException(status_code=404, detail=f"Agent card file not found for DID {agent_did}")
            
            # Load agent card
            with card_path.open('r', encoding='utf-8') as f:
                agent_card = json.load(f)
            
            # Inject DID and URL into agent card
            agent_card["did"] = agent_did
            
            # Build agent URL dynamically from request (use localhost with port from request)
            request_url = request.url
            base_url = f"{request_url.scheme}://{request_url.hostname}"
            if request_url.port:
                base_url = f"{base_url}:{request_url.port}"
            agent_card["url"] = f"{base_url}/agent/"
            
            return agent_card
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error loading agent card for DID {agent_did}: {e}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"Error loading agent card: {str(e)}")


def get_app() -> FastAPI:
    """Get the FastAPI application instance."""
    if app is None:
        raise RuntimeError("App not initialized. Call attach_mcp_server() first.")
    return app


def attach_mcp_server(mcp_app, prefix: str = "/mcp") -> None:
    """Attach MCP server as a sub-application.
    
    Follows FastMCP pattern: https://gofastmcp.com/integrations/fastapi#mounting-an-mcp-server
    
    Creates the FastAPI app with MCP lifespan, then registers routes and mounts the MCP server.
    Similar to: app = FastAPI(title="...", lifespan=mcp_app.lifespan)
    
    Args:
        mcp_app: Starlette application instance from MCP server (via mcp.http_app())
        prefix: URL prefix for MCP routes (default: "/mcp")
    """
    global app
    
    logger.info(f"Attaching MCP server at prefix: {prefix}")
    
    # FastMCP requires lifespan to be passed to FastAPI
    # Create app with MCP lifespan (similar to main_simple.py pattern)
    if hasattr(mcp_app, 'lifespan') and mcp_app.lifespan is not None:
        logger.info("FastMCP lifespan found - creating FastAPI app with MCP lifespan")
        app = _create_app(lifespan=mcp_app.lifespan)
        
        # Register all routes on the new app
        _register_routes(app)
        
        logger.info("FastAPI app created with FastMCP lifespan and routes registered")
    else:
        logger.warning("FastMCP lifespan not found - MCP may not work correctly")
        # Still create app without lifespan as fallback
        app = _create_app()
        _register_routes(app)
    
    # Debug: Log MCP app routes before mounting
    logger.info("=== MCP App Routes (before mounting) ===")
    if hasattr(mcp_app, 'routes'):
        logger.info(f"MCP app has {len(mcp_app.routes)} routes:")
        for i, route in enumerate(mcp_app.routes):
            if hasattr(route, 'path'):
                methods = getattr(route, 'methods', set())
                methods_str = list(methods) if methods else 'ALL'
                logger.info(f"  MCP Route {i}: {methods_str} {route.path} ({type(route).__name__})")
            else:
                logger.info(f"  MCP Route {i}: {type(route).__name__} (no path attribute)")
    else:
        logger.info("MCP app has no 'routes' attribute")
        logger.info(f"MCP app type: {type(mcp_app)}")
        logger.info(f"MCP app attributes: {[attr for attr in dir(mcp_app) if not attr.startswith('_')]}")
    
    # Mount the MCP server (following FastMCP pattern)
    app.mount(prefix, mcp_app)
    
    # Debug: Log all registered routes after mounting
    logger.info(f"=== Main App Routes (after mounting at {prefix}) ===")
    logger.info(f"Total routes after mounting: {len(app.routes)}")
    for i, route in enumerate(app.routes):
        route_type = type(route).__name__
        if route_type == 'Mount':
            mount_path = getattr(route, 'path', 'N/A')
            mount_app = getattr(route, 'app', None)
            logger.info(f"  Route {i}: Mount at {mount_path} ({route_type})")
            if mount_app and hasattr(mount_app, 'routes'):
                logger.info(f"    Mount app has {len(mount_app.routes)} routes:")
                for j, sub_route in enumerate(mount_app.routes):
                    if hasattr(sub_route, 'path'):
                        methods = getattr(sub_route, 'methods', set())
                        methods_str = list(methods) if methods else 'ALL'
                        logger.info(f"      Sub-route {j}: {methods_str} {sub_route.path} ({type(sub_route).__name__})")
        elif hasattr(route, 'path'):
            methods = getattr(route, 'methods', set())
            methods_str = list(methods) if methods else 'ALL'
            logger.info(f"  Route {i}: {methods_str} {route.path} ({route_type})")
        else:
            logger.info(f"  Route {i}: {route_type} (no path attribute)")
    
    logger.info(f"MCP server attached successfully at {prefix}")


def attach_a2a_server(a2a_app, prefix: str = "/agent") -> None:
    """Attach A2A agent server as a sub-application.
    
    Args:
        a2a_app: Starlette application instance from A2A server
        prefix: URL prefix for A2A routes (default: "/agent")
    """
    if a2a_app is None:
        raise ValueError("A2A app cannot be None")
    
    logger.info(f"Attaching A2A agent server at prefix: {prefix}")
    
    # Log A2A app details (always log, not just in DEBUG)
    logger.info(f"A2A app type: {type(a2a_app)}")
    logger.info(f"A2A app is None: {a2a_app is None}")
    logger.info(f"A2A app has lifespan: {hasattr(a2a_app, 'lifespan')}")
    if hasattr(a2a_app, 'routes'):
        logger.info(f"A2A app has {len(a2a_app.routes)} routes")
        for i, route in enumerate(a2a_app.routes):
            route_type = type(route).__name__
            route_info = f"  Route {i}: {route_type}"
            if hasattr(route, 'path'):
                route_info += f" path={route.path}"
            if hasattr(route, 'methods'):
                route_info += f" methods={route.methods}"
            logger.info(route_info)
    else:
        logger.info("A2A app does not have 'routes' attribute")
        # Try to inspect the app structure
        logger.info(f"A2A app attributes: {[attr for attr in dir(a2a_app) if not attr.startswith('_')][:20]}")
    
    # Verify it's a Starlette-compatible app
    if not isinstance(a2a_app, Starlette):
        logger.warning(f"A2A app is not a Starlette instance, but type: {type(a2a_app)}")
        logger.warning("This might still work if it's ASGI-compatible")
    
    logger.info(f"Mounting A2A app at {prefix}...")
    # Ensure prefix has trailing slash for proper Starlette mount behavior
    mount_prefix = prefix if prefix.endswith('/') else prefix + '/'
    app.mount(mount_prefix, a2a_app)
    logger.info(f"Mounted A2A app at {mount_prefix}")
    
    # Log all mounted routes after attachment (always log)
    logger.info("=== Registered routes after A2A attachment ===")
    mount_count = 0
    for route in app.routes:
        route_type = type(route).__name__
        if route_type == 'Mount':
            mount_count += 1
            mount_path = getattr(route, 'path', 'N/A')
            mount_app = getattr(route, 'app', None)
            mount_app_type = type(mount_app).__name__ if mount_app else 'None'
            logger.info(f"  Mount {mount_count}: {mount_path} -> {mount_app_type}")
            # Check if this is our A2A mount
            if mount_path == prefix:
                logger.info(f"    ✅ Found A2A mount at {prefix}")
                if hasattr(mount_app, 'routes'):
                    logger.info(f"    Mounted app has {len(mount_app.routes)} routes")
                    for i, sub_route in enumerate(mount_app.routes):
                        sub_route_type = type(sub_route).__name__
                        sub_info = f"      Sub-route {i}: {sub_route_type}"
                        if hasattr(sub_route, 'path'):
                            sub_info += f" path={sub_route.path}"
                        if hasattr(sub_route, 'methods'):
                            sub_info += f" methods={sub_route.methods}"
                        logger.info(sub_info)
        else:
            methods_str = ', '.join(sorted(route.methods)) if hasattr(route, 'methods') and route.methods else 'N/A'
            logger.info(f"  {methods_str} {getattr(route, 'path', 'N/A')} ({route_type})")
    
    if mount_count == 0:
        logger.error("❌ No Mount routes found in app.routes! Mount may have failed.")
    
    logger.info(f"A2A agent server attached successfully at {prefix}")


def attach_router(router, prefix: str = "") -> None:
    """Attach a FastAPI router to the main application.
    
    Args:
        router: FastAPI router instance
        prefix: URL prefix for router routes (default: "")
    """
    logger.info(f"Attaching router at prefix: {prefix}")
    app.include_router(router, prefix=prefix)
    logger.info(f"Router attached successfully")



