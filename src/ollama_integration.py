"""
Ollama API integration for the AI bot.
"""
import os
import requests
import json
import logging
import glob
from collections import deque
from typing import Dict, List, Any, Optional, Tuple

from config.config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    AI_PERSONAS,
    LANGUAGE_PROMPTS,
    MEMORY_SIZE,
    CHANNEL_CONTEXT_ENABLED,
    GLOBAL_CONTEXT_SIZE,
    LANGUAGE,
    SUPPORTED_LANGUAGES
)
from src.mcp.base import registry as mcp_registry

logger = logging.getLogger(__name__)

class OllamaClient:
    """Client for the Ollama API."""
    
    def __init__(self):
        """Initialize the Ollama client."""
        self.api_url = OLLAMA_BASE_URL
        self.model = OLLAMA_MODEL
        self.current_persona = "default"
        self.current_language = LANGUAGE if LANGUAGE in SUPPORTED_LANGUAGES else "english"
        self.active_knowledge = []
        self.conversation_contexts = {}  # Store conversation context by user/channel
        self.channel_contexts = {}  # Store recent messages in each channel for ambient context
        self.global_memory = deque(maxlen=GLOBAL_CONTEXT_SIZE*10)  # Store some global interactions for cross-channel learning
        
        # Initialize the knowledge directory if it doesn't exist
        self.knowledge_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge")
        os.makedirs(self.knowledge_dir, exist_ok=True)
        
    def generate_response(self, message: str, username: str = "", platform: str = "", 
                          channel_id: str = "", conversation_history: List[Dict[str, str]] = None) -> str:
        """
        Generate a response from the Ollama API.
        
        Args:
            message: The message to respond to
            username: The username of the sender
            platform: The platform (twitch, discord)
            channel_id: The channel ID where the message was sent
            conversation_history: List of previous messages in the conversation
            
        Returns:
            The generated response
        """
        system_prompt = self.get_current_persona_prompt()
        
        # Add platform-specific context to the system prompt
        platform_context = f"The user {username} is chatting on {platform}."
        system_prompt = f"{system_prompt}\n\n{platform_context}"
        
        # Call the API
        payload = {
            "model": self.model,
            "prompt": message,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 1024
            }
        }
        
        # Add conversation history if provided
        if conversation_history and len(conversation_history) > 0:
            formatted_history = []
            for entry in conversation_history:
                role = "user" if entry["role"] == "User" else "assistant"
                formatted_history.append({"role": role, "content": entry["content"]})
                
            # Add the current message
            formatted_history.append({"role": "user", "content": message})
            payload["messages"] = formatted_history
        
        try:
            # Check if we need to query MCP providers for additional context
            mcp_context = self._get_mcp_context(message)
            if mcp_context:
                system_prompt = f"{system_prompt}\n\nRelevant context from data sources:\n{mcp_context}"
                payload["system"] = system_prompt
            
            # Make the API call
            response = requests.post(f"{self.api_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            
            # Extract the response text
            if "message" in data and "content" in data["message"]:
                result = data["message"]["content"]
                return result.strip()
                
            return "I'm not sure how to respond to that."
            
        except requests.RequestException as e:
            logger.error(f"Error calling Ollama API: {e}")
            return "Sorry, I'm having trouble connecting to my brain right now."
            
    async def _query_mcp_providers(self, query: str) -> Dict[str, Any]:
        """
        Query MCP providers for additional context.
        
        Args:
            query: The user's query
            
        Returns:
            Combined results from all MCP providers
        """
        return await mcp_registry.query(query)
        
    def _get_mcp_context(self, query: str) -> str:
        """
        Get additional context from MCP providers for the given query.
        
        Args:
            query: The user's query
            
        Returns:
            Formatted context string or empty string if no context available
        """
        # For synchronous use, we need to run the async query in an event loop
        import asyncio
        
        try:
            # Create or get the event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # If no event loop exists in this thread, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            # Run the async query in the event loop
            results = loop.run_until_complete(self._query_mcp_providers(query))
            
            # If we have results, format them for inclusion in the prompt
            if results:
                context_parts = []
                context_parts.append("I have retrieved the following information to help answer your question:")
                
                for provider, data in results.items():
                    context_parts.append(f"\n--- Information from {provider} ---")
                    
                    # Format the data based on content
                    if isinstance(data, dict):
                        # Handle specific provider data formats
                        if provider == "Garage61" and "items" in data:
                            # Format list of items
                            items = data["items"]
                            context_parts.append(f"Found {len(items)} items:")
                            for item in items:
                                item_str = ", ".join([f"{k}: {v}" for k, v in item.items()])
                                context_parts.append(f"• {item_str}")
                        elif "message" in data:
                            # If there's a message field, display it prominently
                            context_parts.append(data["message"])
                            
                            # Add any other data as additional details
                            for key, value in data.items():
                                if key != "message" and key != "note":
                                    if isinstance(value, list):
                                        context_parts.append(f"\n{key}:")
                                        for item in value:
                                            if isinstance(item, dict):
                                                context_parts.append(f"• {json.dumps(item)}")
                                            else:
                                                context_parts.append(f"• {item}")
                                    else:
                                        context_parts.append(f"\n{key}: {value}")
                        else:
                            # Generic dictionary formatting
                            for key, value in data.items():
                                if key == "note":
                                    continue  # Skip notes in the formatted output
                                if isinstance(value, list) and value and isinstance(value[0], dict):
                                    context_parts.append(f"\n{key}:")
                                    for item in value:
                                        context_parts.append(f"• {json.dumps(item)}")
                                else:
                                    context_parts.append(f"\n{key}: {value}")
                    else:
                        # For non-dictionary results, just add as string
                        context_parts.append(str(data))
                
                context_parts.append("\n--- End of retrieved information ---")
                return "\n".join(context_parts)
                
            # If no results, return just the capabilities
            return mcp_registry.get_capabilities_prompt()
            
        except Exception as e:
            logger.error(f"Error getting MCP context: {e}")
            return mcp_registry.get_capabilities_prompt()
        
    def generate_persona_response(self, message: str, persona: str, username: str = "", 
                                platform: str = "", channel_id: str = "", 
                                conversation_history: List[Dict[str, str]] = None) -> str:
        """
        Generate a response from a specific persona without changing the current one.
        
        Args:
            message: The message to respond to
            persona: The persona to use for this response
            username: The username of the sender
            platform: The platform (twitch, discord)
            channel_id: The channel ID where the message was sent
            conversation_history: List of previous messages in the conversation
            
        Returns:
            The generated response
        """
        # Store current persona
        original_persona = self.current_persona
        
        # Temporarily switch to requested persona
        self.current_persona = persona
        
        # Generate response with the temporary persona
        response = self.generate_response(
            message, 
            username=username, 
            platform=platform,
            channel_id=channel_id,
            conversation_history=conversation_history
        )
        
        # Restore original persona
        self.current_persona = original_persona
        
        return response
        
    def analyze_message(self, message: str, username: str = "", platform: str = "",
                     channel_id: str = "") -> Tuple[bool, Optional[str]]:
        """
        Analyze a message to decide if the AI should respond.
        
        Args:
            message: The message to analyze
            username: The username of the sender
            platform: The platform (twitch, discord)
            channel_id: The channel ID where the message was sent
            
        Returns:
            A tuple of (should_respond, response_text)
        """
        # Construct a query to the AI
        system_prompt = (
            "You are a helpful assistant deciding whether a message in a chat requires a response. "
            "If the message is a question, greeting, or otherwise seems to expect a response, "
            "return 'RESPOND: [your response]'. If it does not require a response, return 'IGNORE'."
        )
        
        try:
            payload = {
                "model": self.model,
                "prompt": message,
                "system": system_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,  # Lower temperature for more deterministic decision
                }
            }
            
            response = requests.post(f"{self.api_url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            
            # Extract the decision
            if "response" in data:
                result = data["response"].strip()
                
                if result.startswith("RESPOND:"):
                    # Extract the suggested response
                    ai_response = result[8:].strip()  # Remove "RESPOND: " prefix
                    return True, ai_response
                else:
                    return False, None
                    
            return False, None
            
        except requests.RequestException as e:
            logger.error(f"Error calling Ollama API for analysis: {e}")
            return False, None
            
    def set_persona(self, persona: str) -> Tuple[bool, str]:
        """
        Set the current persona.
        
        Args:
            persona: The persona to set
            
        Returns:
            A tuple of (success, message)
        """
        if persona in AI_PERSONAS:
            self.current_persona = persona
            return True, f"Persona set to {persona}"
        else:
            available = ", ".join(AI_PERSONAS.keys())
            return False, f"Unknown persona '{persona}'. Available personas: {available}"
            
    def set_language(self, language: str) -> Tuple[bool, str]:
        """
        Set the current language.
        
        Args:
            language: The language to set
            
        Returns:
            A tuple of (success, message)
        """
        if language in SUPPORTED_LANGUAGES:
            self.current_language = language
            return True, f"Language set to {language}"
        else:
            available = ", ".join(SUPPORTED_LANGUAGES)
            return False, f"Unknown language '{language}'. Available languages: {available}"
        
    def get_current_persona_prompt(self):
        """Get the system prompt for the current persona with language instructions and knowledge files."""
        base_prompt = AI_PERSONAS.get(self.current_persona, AI_PERSONAS["default"])
        
        # Add language-specific instructions - make this a top priority
        language_prompt = LANGUAGE_PROMPTS.get(self.current_language, "")
        
        # Add knowledge files if any are active
        knowledge_content = self._get_active_knowledge_content()
        knowledge_prompt = ""
        if knowledge_content:
            knowledge_prompt = (
                "\n\nYou have access to the following knowledge base. Use this information when responding to questions:\n\n"
                f"{knowledge_content}"
                "\n\nWhen responding to questions related to this knowledge, cite it as your source."
            )
        
        # Add additional context awareness guidance
        context_prompt = (
            f"{language_prompt}\n\n"  # Language instructions first for higher priority
            f"{base_prompt}\n\n"  
            "Pay attention to the conversation history and context provided. "
            "Your answers should be concise (1-3 sentences) and tailored to the platform. "
            "Avoid any controversial topics and potential harmful content."
            f"{knowledge_prompt}\n\n"  # Add knowledge base content
            f"Remember: {language_prompt}"  # Repeat language instruction at the end for emphasis
        )
        return context_prompt
        
    def _get_active_knowledge_content(self):
        """Get the content of all active knowledge files, combined into a single string."""
        if not self.active_knowledge:
            return ""
            
        content_parts = []
        for knowledge_name in self.active_knowledge:
            content = self.load_knowledge_content(knowledge_name)
            if content:
                content_parts.append(f"--- BEGIN {knowledge_name.upper()} ---\n{content}\n--- END {knowledge_name.upper()} ---")
        
        if not content_parts:
            return ""
            
        return "\n\n".join(content_parts)

    def _scan_knowledge_files(self):
        """Scan the knowledge directory for available knowledge files."""
        knowledge_files = {}
        
        # Ensure the knowledge directory exists
        if not os.path.exists(self.knowledge_dir):
            os.makedirs(self.knowledge_dir, exist_ok=True)
            logger.info(f"Created knowledge directory at {self.knowledge_dir}")
            return knowledge_files
            
        # Look for text, markdown, and JSON files
        file_patterns = ['*.txt', '*.md', '*.json']
        for pattern in file_patterns:
            for file_path in glob.glob(os.path.join(self.knowledge_dir, pattern)):
                file_name = os.path.basename(file_path)
                knowledge_name = os.path.splitext(file_name)[0]
                knowledge_files[knowledge_name] = {
                    'name': knowledge_name,
                    'path': file_path,
                    'type': os.path.splitext(file_name)[1][1:],  # Get extension without dot
                    'size': os.path.getsize(file_path)
                }
                
        logger.info(f"Found {len(knowledge_files)} knowledge files in {self.knowledge_dir}")
        return knowledge_files
        
    def load_knowledge_content(self, knowledge_name):
        """Load the content of a specific knowledge file."""
        knowledge_files = self._scan_knowledge_files()
        
        if knowledge_name not in knowledge_files:
            return None
            
        file_info = knowledge_files[knowledge_name]
        file_path = file_info['path']
        file_type = file_info['type']
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # If it's a JSON file, parse it and return a formatted string
            if file_type == 'json':
                try:
                    data = json.loads(content)
                    # Convert JSON to a formatted string representation
                    return json.dumps(data, indent=2)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse JSON file: {file_path}")
                    return content
                    
            return content
        except Exception as e:
            logger.error(f"Error loading knowledge file {file_path}: {e}")
            return None
            
    def activate_knowledge(self, knowledge_name):
        """Activate a knowledge file for use in responses."""
        knowledge_files = self._scan_knowledge_files()
        
        if knowledge_name not in knowledge_files:
            return False, f"Knowledge file '{knowledge_name}' not found"
            
        if knowledge_name in self.active_knowledge:
            return True, f"Knowledge file '{knowledge_name}' is already active"
            
        self.active_knowledge.append(knowledge_name)
        logger.info(f"Activated knowledge file: {knowledge_name}")
        return True, f"Activated knowledge file: {knowledge_name}"
        
    def deactivate_knowledge(self, knowledge_name):
        """Deactivate a knowledge file."""
        if knowledge_name not in self.active_knowledge:
            return False, f"Knowledge file '{knowledge_name}' is not active"
            
        self.active_knowledge.remove(knowledge_name)
        logger.info(f"Deactivated knowledge file: {knowledge_name}")
        return True, f"Deactivated knowledge file: {knowledge_name}"
        
    def list_knowledge_files(self):
        """List all available knowledge files."""
        knowledge_files = self._scan_knowledge_files()
        result = "Available knowledge files:\n\n"
        
        if not knowledge_files:
            return result + "No knowledge files found. Add .txt, .md or .json files to the 'knowledge' directory."
            
        for name, info in knowledge_files.items():
            status = "[ACTIVE]" if name in self.active_knowledge else ""
            size_kb = info['size'] / 1024
            result += f"• {name} ({info['type']}, {size_kb:.1f} KB) {status}\n"
            
        return result