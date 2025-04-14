"""
Base Model Context Protocol (MCP) implementation.
This module provides abstract classes for MCP integrations.
"""
import logging
import abc
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class MCPProvider(abc.ABC):
    """Base abstract class for all MCP providers."""
    
    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Return the name of this MCP provider."""
        pass
    
    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Return a description of this MCP provider's capabilities."""
        pass
    
    @abc.abstractmethod
    async def query(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Perform a query against this MCP provider.
        
        Args:
            query: The query string from the LLM/user
            **kwargs: Additional provider-specific parameters
            
        Returns:
            A dictionary containing the query results
        """
        pass
    
    @abc.abstractmethod
    def can_handle_query(self, query: str) -> bool:
        """
        Determine if this provider can handle the given query.
        
        Args:
            query: The query string from the LLM/user
            
        Returns:
            True if this provider can handle the query, False otherwise
        """
        pass

class MCPRegistry:
    """Registry for MCP providers."""
    
    def __init__(self):
        self.providers: List[MCPProvider] = []
        
    def register(self, provider: MCPProvider):
        """Register a new MCP provider."""
        self.providers.append(provider)
        logger.info(f"Registered MCP provider: {provider.name}")
        
    async def query(self, query: str) -> Dict[str, Any]:
        """
        Query all registered MCP providers that can handle this query.
        
        Args:
            query: The query string from the LLM/user
            
        Returns:
            Combined results from all providers that handled the query
        """
        results = {}
        
        for provider in self.providers:
            if provider.can_handle_query(query):
                logger.info(f"Querying MCP provider: {provider.name}")
                try:
                    provider_results = await provider.query(query)
                    if provider_results:
                        results[provider.name] = provider_results
                except Exception as e:
                    logger.error(f"Error querying MCP provider {provider.name}: {e}")
        
        return results
    
    def get_capabilities_prompt(self) -> str:
        """
        Get a prompt describing the capabilities of all registered providers.
        
        Returns:
            A string describing provider capabilities for the system prompt
        """
        if not self.providers:
            return ""
            
        capabilities = ["I have access to the following data sources:"]
        
        for provider in self.providers:
            capabilities.append(f"- {provider.name}: {provider.description}")
            
        return "\n".join(capabilities)

# Create a global registry instance
registry = MCPRegistry()