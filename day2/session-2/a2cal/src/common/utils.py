# type: ignore
import logging
import os

import google.generativeai as genai

from common.types import ServerConfig


logger = logging.getLogger(__name__)


def init_api_key():
    """Initialize the API token for Gemini SDK.
    
    Supports both GEMINI_API_TOKEN and GOOGLE_API_KEY for backward compatibility.
    Also sets GEMINI_API_KEY for LiteLLM compatibility.
    """
    api_token = os.getenv('GEMINI_API_TOKEN') or os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
    if not api_token:
        logger.error('GEMINI_API_TOKEN is not set')
        raise ValueError('GEMINI_API_TOKEN is not set. Please set GEMINI_API_TOKEN environment variable.')
    
    # Configure google.generativeai SDK
    genai.configure(api_key=api_token)
    
    # Set for LiteLLM compatibility (LiteLLM uses GEMINI_API_KEY or GOOGLE_API_KEY)
    if not os.getenv('GEMINI_API_KEY') and not os.getenv('GOOGLE_API_KEY'):
        os.environ['GEMINI_API_KEY'] = api_token
        os.environ['GOOGLE_API_KEY'] = api_token


def config_logging():
    """Configure basic logging."""
    log_level = (
        os.getenv('A2A_LOG_LEVEL') or os.getenv('FASTMCP_LOG_LEVEL') or 'INFO'
    ).upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))


def config_logger(logger):
    """Logger specific config, avoiding clutter in enabling all loggging."""
    # TODO: replace with env
    logger.setLevel(logging.INFO)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def get_mcp_server_config() -> ServerConfig:
    """Get the MCP server configuration."""
    return ServerConfig(
        host='localhost',
        port=10100,
        transport='sse',
        url='http://localhost:10100/sse',
    )
