"""
Model Context Protocol (MCP) package initialization.
This module ensures all MCP providers are properly registered.
"""
import logging

# Import the registry to make it available from the mcp package
from src.mcp.base import registry

# Import all providers to ensure they register themselves
from src.mcp.garage61 import garage61_provider

# Initialize package-level logger
logger = logging.getLogger(__name__)
logger.info(f"MCP initialized with {len(registry.providers)} providers registered")

# Export the main interface
__all__ = ['registry']