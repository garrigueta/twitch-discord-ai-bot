import logging
import random
import asyncio
from config.config import (
    ENABLE_AI_RESPONSE, 
    AI_TRIGGER_PHRASE, 
    AI_RESPONSE_PROBABILITY,
    BOT_PREFIX,
    AI_PERSONAS,
    SUPPORTED_LANGUAGES
)
from src.ollama_integration import OllamaClient
from src.mcp import registry as mcp_registry

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self):
        self.ollama_client = OllamaClient()
        self.conversation_history = {}  # Store conversation history per user/channel
        self.commands = {
            'help': self.command_help,
            'ping': self.command_ping,
            'ai': self.command_ai,
            'persona': self.command_persona,
            'personas': self.command_list_personas,
            'ask': self.command_ask_as_persona,
            'language': self.command_language,
            'languages': self.command_list_languages,
            'knowledge': self.command_manage_knowledge,
            'knowledges': self.command_list_knowledge,
            'racing': self.command_racing_data,
            'mcp': self.command_mcp_info,
        }
        
    def get_conversation_key(self, username, channel_id):
        """Create a unique key for storing conversation history."""
        return f"{username}:{channel_id}"
        
    def store_message(self, username, channel_id, role, content):
        """Store message in conversation history."""
        conv_key = self.get_conversation_key(username, channel_id)
        
        if conv_key not in self.conversation_history:
            self.conversation_history[conv_key] = []
            
        self.conversation_history[conv_key].append({
            'role': role,
            'content': content
        })
        
        # Limit history to last 20 messages
        if len(self.conversation_history[conv_key]) > 20:
            self.conversation_history[conv_key] = self.conversation_history[conv_key][-20:]
    
    def get_conversation_history(self, username, channel_id):
        """Get conversation history for a user/channel."""
        conv_key = self.get_conversation_key(username, channel_id)
        return self.conversation_history.get(conv_key, [])
    
    async def process_message(self, message, username, channel_id, platform):
        """
        Process an incoming message from Twitch or Discord.
        
        Args:
            message (str): The message content
            username (str): The username of the sender
            channel_id (str): The channel ID where the message was sent
            platform (str): 'twitch' or 'discord'
            
        Returns:
            str or None: Response message if any
        """
        # Store user message in history
        self.store_message(username, channel_id, 'User', message)
        
        # Check if message is a command
        if message.startswith(BOT_PREFIX):
            return await self.handle_command(message[len(BOT_PREFIX):], username, channel_id, platform)
            
        # Enhanced bot name detection - more robust check for AI trigger phrase
        if ENABLE_AI_RESPONSE:
            trigger_phrase = AI_TRIGGER_PHRASE.lower()
            message_lower = message.lower()
            
            # Check for different variations of the trigger
            is_triggered = (
                trigger_phrase in message_lower or
                trigger_phrase.replace('@', '') in message_lower or  # Without @ symbol
                trigger_phrase.replace(' ', '') in message_lower.replace(' ', '')  # Without spaces
            )
            
            # Handle Discord-specific mentions (like <@123456789>)
            if platform == 'discord' and '<@' in message_lower and '>' in message_lower:
                is_triggered = True
                
            if is_triggered:
                logger.info(f"Bot name trigger detected in: '{message}'")
                response = await self.handle_ai_request(message, username, channel_id, platform)
                return response
            
        # Random chance to respond with AI
        if ENABLE_AI_RESPONSE and random.random() < AI_RESPONSE_PROBABILITY:
            # Analyze message to see if AI should respond
            should_respond, ai_response = self.ollama_client.analyze_message(
                message, 
                username=username, 
                platform=platform,
                channel_id=channel_id  # Pass channel_id for improved context awareness
            )
            
            if should_respond and ai_response:
                self.store_message(username, channel_id, 'Assistant', ai_response)
                return ai_response
                
        return None
        
    async def handle_command(self, command_text, username, channel_id, platform):
        """Handle bot commands."""
        # Split command and arguments
        parts = command_text.strip().split(' ', 1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if command in self.commands:
            return await self.commands[command](args, username, channel_id, platform)
        
        return f"Unknown command: {command}. Type {BOT_PREFIX}help for a list of commands."
    
    async def handle_ai_request(self, message, username, channel_id, platform):
        """Handle a direct request to the AI."""
        # Remove the trigger phrase from the message
        clean_message = message.lower().replace(AI_TRIGGER_PHRASE.lower(), "").strip()
        if not clean_message:
            clean_message = "Hello!"
            
        response = self.ollama_client.generate_response(
            clean_message,
            username=username,
            platform=platform,
            channel_id=channel_id,  # Pass channel_id for improved context awareness
            conversation_history=self.get_conversation_history(username, channel_id)
        )
        
        # Store AI response in history
        self.store_message(username, channel_id, 'Assistant', response)
        return response
        
    # Command handlers
    async def command_help(self, args, username, channel_id, platform):
        """Help command handler."""
        help_text = (
            f"Available commands:\n"
            f"{BOT_PREFIX}help - Show this help message\n"
            f"{BOT_PREFIX}ping - Check if bot is online\n"
            f"{BOT_PREFIX}ai <message> - Ask the AI a question\n"
            f"{BOT_PREFIX}persona <name> - Switch AI personality (default, streamer, expert, comedian, motivator)\n"
            f"{BOT_PREFIX}personas - List available AI personas\n"
            f"{BOT_PREFIX}ask <persona> <message> - Ask a one-time question to a specific persona\n"
            f"{BOT_PREFIX}language <language> - Switch the bot's language (english, spanish)\n"
            f"{BOT_PREFIX}languages - List available languages\n"
            f"{BOT_PREFIX}knowledge - Manage custom knowledge files\n"
            f"{BOT_PREFIX}knowledges - List available knowledge files\n"
            f"{BOT_PREFIX}racing - Get racing data\n"
            f"{BOT_PREFIX}mcp - Get MCP registry information\n\n"
            f"You can also mention the bot using '{AI_TRIGGER_PHRASE}' to get AI responses."
        )
        return help_text
        
    async def command_ping(self, args, username, channel_id, platform):
        """Ping command handler."""
        return f"Pong! Bot is online. Platform: {platform}"
        
    async def command_ai(self, args, username, channel_id, platform):
        """AI command handler."""
        if not args:
            return f"Please provide a message after {BOT_PREFIX}ai"
            
        response = self.ollama_client.generate_response(
            args,
            username=username,
            platform=platform,
            channel_id=channel_id,  # Pass channel_id for improved context awareness
            conversation_history=self.get_conversation_history(username, channel_id)
        )
        
        # Store AI response in history
        self.store_message(username, channel_id, 'Assistant', response)
        return response
        
    async def command_persona(self, args, username, channel_id, platform):
        """Change the bot's active persona."""
        if not args:
            current_persona = self.ollama_client.current_persona
            available_personas = ", ".join(AI_PERSONAS.keys())
            return f"Current persona: {current_persona}\nAvailable personas: {available_personas}"
            
        # Try to set the requested persona
        success, message = self.ollama_client.set_persona(args.strip().lower())
        return message
        
    async def command_list_personas(self, args, username, channel_id, platform):
        """List available personas with descriptions."""
        response = "Available AI personas:\n\n"
        current = self.ollama_client.current_persona
        
        for name, description in AI_PERSONAS.items():
            # Truncate description if too long
            short_desc = description[:100] + "..." if len(description) > 100 else description
            current_marker = " [ACTIVE]" if name == current else ""
            response += f"• {name}{current_marker}: {short_desc}\n"
            
        return response
        
    async def command_ask_as_persona(self, args, username, channel_id, platform):
        """Ask a question to a specific persona without changing the current one."""
        if not args:
            return f"Usage: {BOT_PREFIX}ask <persona> <message>"
            
        parts = args.split(' ', 1)
        if len(parts) < 2:
            return f"Please provide both a persona name and a message."
            
        persona, message = parts
        
        if persona.lower() not in AI_PERSONAS:
            available = ", ".join(AI_PERSONAS.keys())
            return f"Unknown persona '{persona}'. Available personas: {available}"
            
        # Generate a response with the specified persona
        response = self.ollama_client.generate_persona_response(
            message,
            persona=persona.lower(),
            username=username,
            platform=platform,
            channel_id=channel_id,
            conversation_history=self.get_conversation_history(username, channel_id)
        )
        
        # Store response in conversation history
        prefix = f"[{persona.upper()}] "
        self.store_message(username, channel_id, 'Assistant', prefix + response)
        
        return prefix + response

    async def command_language(self, args, username, channel_id, platform):
        """Change the bot's active language."""
        if not args:
            current_language = self.ollama_client.current_language
            available_languages = ", ".join(SUPPORTED_LANGUAGES)
            return f"Current language: {current_language}\nAvailable languages: {available_languages}"
            
        # Try to set the requested language
        success, message = self.ollama_client.set_language(args.strip().lower())
        return message
        
    async def command_list_languages(self, args, username, channel_id, platform):
        """List available languages."""
        response = "Available languages:\n\n"
        current = self.ollama_client.current_language
        
        for language in SUPPORTED_LANGUAGES:
            current_marker = " [ACTIVE]" if language == current else ""
            if language == "english":
                description = "English - Default language"
            elif language == "spanish":
                description = "Spanish (Español) - El bot responderá en español"
            else:
                description = language.capitalize()
                
            response += f"• {language}{current_marker}: {description}\n"
            
        return response

    async def command_manage_knowledge(self, args, username, channel_id, platform):
        """Manage knowledge files for the AI."""
        if not args:
            return (
                f"Usage:\n"
                f"{BOT_PREFIX}knowledge list - List all knowledge files\n"
                f"{BOT_PREFIX}knowledge activate <name> - Activate a knowledge file\n"
                f"{BOT_PREFIX}knowledge deactivate <name> - Deactivate a knowledge file\n"
                f"{BOT_PREFIX}knowledge status - Show active knowledge files"
            )
            
        parts = args.split(' ', 1)
        action = parts[0].lower()
        
        if action == "list":
            # List all available knowledge files
            return self.ollama_client.list_knowledge_files()
            
        elif action == "status":
            # Show currently active knowledge files
            active_files = self.ollama_client.active_knowledge
            if not active_files:
                return "No knowledge files are currently active."
            return f"Active knowledge files: {', '.join(active_files)}"
            
        elif action == "activate" and len(parts) > 1:
            # Activate a knowledge file
            knowledge_name = parts[1].strip()
            success, message = self.ollama_client.activate_knowledge(knowledge_name)
            return message
            
        elif action == "deactivate" and len(parts) > 1:
            # Deactivate a knowledge file
            knowledge_name = parts[1].strip()
            success, message = self.ollama_client.deactivate_knowledge(knowledge_name)
            return message
            
        else:
            return f"Invalid knowledge command. Type {BOT_PREFIX}knowledge for usage information."
    
    async def command_list_knowledge(self, args, username, channel_id, platform):
        """List all available knowledge files."""
        return self.ollama_client.list_knowledge_files()

    async def command_racing_data(self, args, username, channel_id, platform):
        """Query racing data from Garage61 API."""
        if not args:
            return (
                f"Usage: {BOT_PREFIX}racing <query>\n\n"
                f"Examples:\n"
                f"{BOT_PREFIX}racing list teams\n"
                f"{BOT_PREFIX}racing tracks available\n"
                f"{BOT_PREFIX}racing team statistics\n"
                f"{BOT_PREFIX}racing data packs"
            )
            
        # This command directly queries the Garage61 provider
        for provider in mcp_registry.providers:
            if provider.name == "Garage61":
                # Check if provider can handle this query
                if provider.can_handle_query(args):
                    try:
                        # Create or get the event loop
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            
                        # Query the provider
                        results = await provider.query(args)
                        
                        # Format the results
                        if isinstance(results, dict):
                            if "message" in results:
                                response = results["message"] + "\n\n"
                            else:
                                response = "Racing data from Garage61:\n\n"
                                
                            # Handle items lists
                            if "items" in results and isinstance(results["items"], list):
                                items = results["items"]
                                response += f"Found {len(items)} items:\n"
                                
                                for item in items:
                                    if isinstance(item, dict):
                                        # Format each item as a bullet point with key-value pairs
                                        item_str = ", ".join([f"{k}: {v}" for k, v in item.items()])
                                        response += f"• {item_str}\n"
                                    else:
                                        response += f"• {item}\n"
                            
                            # Add any other relevant data
                            for key, value in results.items():
                                if key not in ["message", "items", "note", "error"]:
                                    if isinstance(value, list):
                                        if value and isinstance(value[0], dict):
                                            response += f"\n{key}:\n"
                                            for item in value[:5]:  # Limit to 5 items to avoid too long messages
                                                response += f"• {item}\n"
                                            if len(value) > 5:
                                                response += f"... and {len(value) - 5} more items\n"
                                        else:
                                            response += f"\n{key}: {', '.join(map(str, value[:10]))}"
                                            if len(value) > 10:
                                                response += f" ... and {len(value) - 10} more"
                                    else:
                                        response += f"\n{key}: {value}"
                            
                            # Add error message if present
                            if "error" in results:
                                response += f"\nError: {results['error']}"
                                
                            return response
                        else:
                            return f"Racing data from Garage61:\n\n{results}"
                            
                    except Exception as e:
                        logger.error(f"Error querying Garage61 provider: {e}")
                        return f"An error occurred while retrieving racing data: {str(e)}"
                else:
                    return (
                        "Your query doesn't seem to be related to racing data. Try again with keywords like "
                        "'teams', 'drivers', 'tracks', 'cars', 'statistics', etc."
                    )
        
        return "The Garage61 racing data provider is not available."
        
    async def command_mcp_info(self, args, username, channel_id, platform):
        """Get information about available MCP providers."""
        if not args:
            # List all registered providers
            providers_info = []
            
            for provider in mcp_registry.providers:
                providers_info.append(f"• {provider.name}: {provider.description}")
                
            if not providers_info:
                return "No MCP providers are currently registered."
                
            return "Available Model Context Protocol (MCP) providers:\n\n" + "\n\n".join(providers_info)
            
        # Check for specific provider info
        provider_name = args.strip().lower()
        
        for provider in mcp_registry.providers:
            if provider.name.lower() == provider_name:
                return f"MCP Provider: {provider.name}\n\nDescription: {provider.description}"
                
        return f"No MCP provider found with name '{args}'. Use '{BOT_PREFIX}mcp' to see available providers."