"""Base server that aggregates all sub-servers and routers."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastmcp.utilities.logging import get_logger

logger = get_logger(__name__)

# Create the main FastAPI application
app = FastAPI(
    title="A2Cal Server",
    description="Aggregated server for Calendar Agent with MCP and other services",
    version="1.0.0"
)

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_app() -> FastAPI:
    """Get the FastAPI application instance."""
    return app


def attach_mcp_server(mcp_app, prefix: str = "/mcp") -> None:
    """Attach MCP server as a sub-application.
    
    Args:
        mcp_app: Starlette application instance from MCP server (via mcp.http_app())
        prefix: URL prefix for MCP routes (default: "/mcp")
    """
    logger.info(f"Attaching MCP server at prefix: {prefix}")
    app.mount(prefix, mcp_app)
    logger.info(f"MCP server attached successfully")


def attach_a2a_server(a2a_app, prefix: str = "/agent") -> None:
    """Attach A2A agent server as a sub-application.
    
    Args:
        a2a_app: Starlette application instance from A2A server
        prefix: URL prefix for A2A routes (default: "/agent")
    """
    logger.info(f"Attaching A2A agent server at prefix: {prefix}")
    app.mount(prefix, a2a_app)
    logger.info(f"A2A agent server attached successfully")


def attach_router(router, prefix: str = "") -> None:
    """Attach a FastAPI router to the main application.
    
    Args:
        router: FastAPI router instance
        prefix: URL prefix for router routes (default: "")
    """
    logger.info(f"Attaching router at prefix: {prefix}")
    app.include_router(router, prefix=prefix)
    logger.info(f"Router attached successfully")


@app.get("/")
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


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

