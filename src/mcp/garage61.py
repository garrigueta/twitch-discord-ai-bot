"""
Garage61 API Model Context Protocol (MCP) provider.
This module allows the AI to query the Garage61 API for racing data.
"""
import logging
import json
import os
import re
import aiohttp
from typing import Dict, Any, List, Optional
import yaml

from src.mcp.base import MCPProvider, registry

logger = logging.getLogger(__name__)

# Path to the OpenAPI spec
GARAGE61_SPEC_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                  "spec", "garage61_v1.json")

class Garage61Provider(MCPProvider):
    """MCP provider for Garage61 API."""
    
    def __init__(self, api_key: Optional[str] = None, api_base: str = "https://garage61.net/api"):
        """
        Initialize the Garage61 provider.
        
        Args:
            api_key: API key for authentication
            api_base: Base URL for the API
        """
        self.api_key = api_key or os.environ.get("GARAGE61_API_KEY", "")
        self.api_base = api_base
        self.endpoints = {}
        self.schema_definitions = {}
        self._load_spec()
        
    def _load_spec(self):
        """Load the OpenAPI specification for Garage61."""
        try:
            with open(GARAGE61_SPEC_PATH, 'r') as f:
                spec = json.load(f)
                
            # Extract endpoint information
            self.endpoints = {}
            if 'paths' in spec:
                for path, path_info in spec['paths'].items():
                    for method, operation in path_info.items():
                        if method in ['get', 'post', 'put', 'delete']:
                            endpoint_id = operation.get('operationId', f"{method}_{path}")
                            self.endpoints[endpoint_id] = {
                                'path': path,
                                'method': method,
                                'summary': operation.get('summary', ''),
                                'description': operation.get('description', ''),
                                'tags': operation.get('tags', []),
                                'parameters': operation.get('parameters', [])
                            }
            
            # Extract schema definitions
            if 'components' in spec and 'schemas' in spec['components']:
                self.schema_definitions = spec['components']['schemas']
                
            logger.info(f"Loaded Garage61 API spec with {len(self.endpoints)} endpoints")
            
        except Exception as e:
            logger.error(f"Error loading Garage61 API spec: {e}")
            
    @property
    def name(self) -> str:
        """Return the name of this MCP provider."""
        return "Garage61"
    
    @property
    def description(self) -> str:
        """Return a description of this MCP provider's capabilities."""
        return (
            "Racing data from Garage61 platform, including teams, drivers, tracks, cars, "
            "lap data, setups, and driving statistics. Use this to answer questions about "
            "racing data, team performance, and driver stats."
        )
    
    def can_handle_query(self, query: str) -> bool:
        """
        Determine if this provider can handle the given query.
        
        Args:
            query: The query string from the LLM/user
            
        Returns:
            True if this provider can handle the query, False otherwise
        """
        # Keywords related to racing and Garage61 data
        racing_keywords = [
            'garage61', 'racing', 'race', 'driver', 'track', 'car', 'lap', 'team', 
            'iracing', 'setup', 'telemetry', 'ghost lap', 'statistics', 'driving',
            'platform', 'season', 'oval', 'road', 'rating'
        ]
        
        # Check if any racing keyword is in the query
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in racing_keywords)
    
    async def query(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Perform a query against the Garage61 API.
        
        Args:
            query: The query string from the LLM/user
            **kwargs: Additional parameters
            
        Returns:
            A dictionary containing the query results
        """
        # For now, we'll return information about our capabilities since we can't authenticate yet
        if not self.api_key:
            return {
                "message": "I can access Garage61 racing data, but no API key is configured. "
                           "Please set the GARAGE61_API_KEY environment variable to enable this functionality.",
                "available_endpoints": self._get_endpoint_summary(),
                "usage": "You can ask questions about racing data such as teams, drivers, tracks, cars, and statistics."
            }
        
        # Determine which endpoint to call based on the query
        endpoint_info = self._map_query_to_endpoint(query)
        if not endpoint_info:
            return {
                "message": "I understand you're asking about racing data, but I couldn't determine which specific "
                           "information you need. Could you be more specific?",
                "available_data": "You can ask about teams, drivers, tracks, cars, lap times, and driving statistics."
            }
            
        # Call the endpoint and return the results
        try:
            results = await self._call_api(endpoint_info, query)
            return results
        except Exception as e:
            logger.error(f"Error calling Garage61 API: {e}")
            return {
                "error": f"Error retrieving data from Garage61: {str(e)}",
                "endpoint": endpoint_info.get('path', 'unknown')
            }
    
    def _map_query_to_endpoint(self, query: str) -> Dict[str, Any]:
        """
        Map a user query to the most appropriate Garage61 API endpoint.
        
        Args:
            query: The user's query string
            
        Returns:
            A dictionary with information about the endpoint to call
        """
        query_lower = query.lower()
        
        # Endpoint mappings based on keywords in the query
        endpoint_keywords = {
            'getTeams': ['list teams', 'all teams', 'team list', 'teams'],
            'getTeam': ['team info', 'team details', 'specific team'],
            'getTracks': ['tracks', 'track list', 'available tracks'],
            'findTracks': ['find tracks', 'search tracks'],
            'getTeamStatistics': ['team statistics', 'team stats', 'driving statistics'],
            'getTeamDataPacks': ['data packs', 'setup packs', 'team data'],
            'getTeamDataPack': ['specific data pack', 'data pack details'],
            'getPlatforms': ['platforms', 'platform list', 'available platforms'],
        }
        
        # Find the best matching endpoint
        best_match = None
        for endpoint_id, keywords in endpoint_keywords.items():
            if endpoint_id in self.endpoints and any(keyword in query_lower for keyword in keywords):
                best_match = endpoint_id
                break
                
        # If we found a match, return the endpoint info
        if best_match and best_match in self.endpoints:
            return self.endpoints[best_match]
            
        # Default to team statistics if no match is found but it looks like a stats query
        if 'statistics' in query_lower or 'stats' in query_lower:
            return self.endpoints.get('getTeamStatistics', {})
            
        # Default to team list if no match is found
        return self.endpoints.get('getTeams', {})
    
    async def _call_api(self, endpoint_info: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Call the Garage61 API.
        
        Args:
            endpoint_info: Information about the endpoint to call
            query: The original query for parameter extraction
            
        Returns:
            The API response data
        """
        path = endpoint_info.get('path', '')
        method = endpoint_info.get('method', 'get')
        
        # Extract parameters from the query
        # Temporarily returning mock data for now since we can't authenticate
        return self._get_mock_data(path, method)
    
    def _get_mock_data(self, path: str, method: str) -> Dict[str, Any]:
        """
        Get mock data for demonstration purposes.
        
        Args:
            path: API path
            method: HTTP method
            
        Returns:
            Mock data for the endpoint
        """
        if path == '/teams' and method == 'get':
            return {
                "items": [
                    {"id": "team1", "name": "Racing Team Alpha", "slug": "team-alpha"},
                    {"id": "team2", "name": "Speedy Racers", "slug": "speedy-racers"},
                    {"id": "team3", "name": "Pro Circuit", "slug": "pro-circuit"}
                ],
                "note": "This is sample data. To get real data, please configure the API key."
            }
        elif path == '/tracks' and method == 'get':
            return {
                "items": [
                    {"id": 1, "name": "Spa-Francorchamps", "variant": "Grand Prix", "platform": "iracing"},
                    {"id": 2, "name": "Nürburgring", "variant": "Nordschleife", "platform": "iracing"},
                    {"id": 3, "name": "Monza", "variant": "Grand Prix", "platform": "iracing"}
                ],
                "note": "This is sample data. To get real data, please configure the API key."
            }
        elif '/statistics' in path:
            return {
                "drivingStatistics": [
                    {
                        "day": "2024-04-14",
                        "user": "driver1",
                        "car": 1234,
                        "track": 45,
                        "sessionType": 1,
                        "events": 3,
                        "timeOnTrack": 5400.5,
                        "lapsDriven": 56,
                        "cleanLapsDriven": 48
                    }
                ],
                "note": "This is sample data. To get real data, please configure the API key."
            }
        else:
            return {
                "message": f"Mock data not available for {path} {method}",
                "note": "This is a placeholder. To get real data, please configure the API key."
            }
    
    def _get_endpoint_summary(self) -> List[Dict[str, str]]:
        """Get a summary of available endpoints for informational purposes."""
        summary = []
        for endpoint_id, info in self.endpoints.items():
            summary.append({
                "id": endpoint_id,
                "path": info.get('path', ''),
                "method": info.get('method', ''),
                "summary": info.get('summary', '')
            })
        return summary

# Create and register the provider
garage61_provider = Garage61Provider()
registry.register(garage61_provider)