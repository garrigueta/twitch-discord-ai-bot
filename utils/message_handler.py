import logging
import random
import asyncio
import os
import glob
from config.config import (
    ENABLE_AI_RESPONSE, 
    AI_TRIGGER_PHRASE, 
    AI_RESPONSE_PROBABILITY,
    BOT_PREFIX,
    AI_PERSONAS,
    SUPPORTED_LANGUAGES,
    DISCORD_TOKEN,
    DISCORD_MASTER_USER,
    TWITCH_MASTER_USER,
    ENABLE_VECTOR_MEMORY,
    MEMORY_DATABASE_PATH,
    ENABLE_INTENT_DETECTION
)
from src.ollama_integration import OllamaClient
from utils.memory_manager import MemoryManager
from utils.nlp.intent_detection import IntentDetector

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self):
        self.ollama_client = OllamaClient()
        self.conversation_history = {}  # Store conversation history per user/channel
        
        # Initialize the memory manager for vector-based memory
        self.memory_manager = MemoryManager()
        
        # Initialize the intent detector for NLP-based intent detection
        self.intent_detector = IntentDetector()
        
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
            'memory': self.command_manage_memory,
            'intent': self.command_manage_intent,
        }
        
        # Extract Discord bot ID from token for mention detection
        self.discord_bot_id = None
        if DISCORD_TOKEN:
            try:
                # Discord tokens have the bot ID encoded in them
                token_parts = DISCORD_TOKEN.split('.')
                if len(token_parts) >= 1:
                    self.discord_bot_id = token_parts[0]
                    logger.info("Extracted Discord bot ID: %s", self.discord_bot_id)
            except Exception as e:
                logger.error("Failed to extract Discord bot ID: %s", e)
        
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
        
        # Log received message
        logger.info("Processing message from %s on %s: '%s'", username, platform, message)
        
        # Get channel name from channel_id (for Discord)
        channel_name = channel_id
        if platform == 'discord':
            # Extract channel name from the end of the ID if possible
            # This is just a heuristic - channel names are useful for intent matching
            parts = channel_id.split('-')
            if len(parts) > 1:
                channel_name = parts[-1]  # Use the last part as the channel name
            
        # Check if message is a command
        if message.startswith(BOT_PREFIX):
            logger.info("Message is a command, handling separately")
            return await self.handle_command(message[len(BOT_PREFIX):], username, channel_id, platform)
            
        # Check for intent-based responses (for Discord only)
        if platform == 'discord' and ENABLE_INTENT_DETECTION:
            should_respond, intent_response, intents = self.intent_detector.analyze_message(message, channel_name)
            
            if intents:
                # Log detected intents for debugging
                intent_str = ", ".join([f"{i}:{c:.2f}" for i, c in intents.items()])
                logger.info(f"Detected intents: {intent_str}")
                
            if should_respond and intent_response:
                logger.info(f"Responding based on intent detection with: {intent_response[:30]}...")
                self.store_message(username, channel_id, 'Assistant', intent_response)
                return intent_response
            
        # Explicitly handle Discord messages - ALWAYS process Discord messages for testing
        if platform == 'discord':
            logger.info("Received Discord message, generating forced response for testing")
            response = await self.handle_ai_request(message, username, channel_id, platform)
            return response
            
        # Below handling for non-Discord platforms
        # Enhanced bot name detection for AI trigger
        if ENABLE_AI_RESPONSE:
            trigger_phrase = AI_TRIGGER_PHRASE.lower()
            message_lower = message.lower()
            
            # Debug message content
            logger.info("Checking message for triggers: '%s'", message)
            
            # Set default triggering to false
            is_triggered = False
            
            # Check for different variations of the trigger
            if (trigger_phrase in message_lower or 
                trigger_phrase.replace('@', '') in message_lower or  # Without @ symbol
                trigger_phrase.replace(' ', '') in message_lower.replace(' ', '')):  # Without spaces
                is_triggered = True
                logger.info("Triggered by phrase match: '%s'", trigger_phrase)
            
            # Handle mention with bot ID (like <@123456789>)
            if '<@' in message and '>' in message:
                # If we have the bot ID, check specifically for this bot's mention
                if self.discord_bot_id and f"<@{self.discord_bot_id}>" in message:
                    logger.info("Triggered by direct mention")
                    is_triggered = True
                # Otherwise fallback to any mention if no bot ID is available
                elif not self.discord_bot_id:
                    logger.info("Triggered by generic mention")
                    is_triggered = True
            
            if is_triggered:
                logger.info("Bot trigger detected, generating response")
                response = await self.handle_ai_request(message, username, channel_id, platform)
                return response
            
        # Random chance to respond with AI
        if ENABLE_AI_RESPONSE and random.random() < AI_RESPONSE_PROBABILITY:
            # Analyze message to see if AI should respond
            should_respond, ai_response = await self.ollama_client.analyze_message(
                message, 
                username=username, 
                platform=platform,
                channel_id=channel_id
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
        
        # Define admin-only commands
        admin_commands = ['persona', 'language', 'languages', 'knowledge', 'knowledges', 'memory', 'intent']
        
        # Check if this is an admin command and if the user is authorized
        if command in admin_commands:
            is_authorized = False
            
            # Check if the user is a master user for their platform
            if platform == 'discord' and username == DISCORD_MASTER_USER:
                is_authorized = True
                logger.info("Discord master user %s authorized for admin command: %s", username, command)
            elif platform == 'twitch' and username == TWITCH_MASTER_USER:
                is_authorized = True
                logger.info("Twitch master user %s authorized for admin command: %s", username, command)
                
            # If not authorized, return an error message
            if not is_authorized:
                logger.warning("Unauthorized user %s attempted admin command: %s on %s", username, command, platform)
                return f"Lo siento, solo los usuarios administradores pueden ejecutar el comando '{command}'."
        
        # Execute the command if it exists
        if command in self.commands:
            # Add a double-check for knowledge commands to ensure they're admin-only
            if command in ['knowledge', 'knowledges']:
                # Verify admin status again as an extra security measure
                is_admin = (platform == 'discord' and username == DISCORD_MASTER_USER) or \
                          (platform == 'twitch' and username == TWITCH_MASTER_USER)
                if not is_admin:
                    logger.warning("Non-admin user %s attempted to use knowledge command: %s", username, command)
                    return "Lo siento, los comandos de conocimiento son exclusivos para administradores."
            
            return await self.commands[command](args, username, channel_id, platform)
        
        return f"Unknown command: {command}. Type {BOT_PREFIX}help for a list of commands."
    
    async def command_manage_intent(self, args, username, channel_id, platform):
        """Manage intent detection settings and channel-specific guidelines."""
        if not ENABLE_INTENT_DETECTION:
            return "Intent detection is disabled in config. Set ENABLE_INTENT_DETECTION = True to use this feature."
            
        if not args:
            return (
                f"Usage:\n"
                f"{BOT_PREFIX}intent list - List all available intents\n"
                f"{BOT_PREFIX}intent analyze <text> - Analyze text to detect intents\n"
                f"{BOT_PREFIX}intent channels - List channels with custom guidelines\n"
                f"{BOT_PREFIX}intent add <channel> <intent> <priority> <response> - Add a channel guideline\n"
                f"{BOT_PREFIX}intent test <channel> <message> - Test how a message would be handled in a channel"
            )
            
        parts = args.split(' ', 1)
        action = parts[0].lower()
        
        if action == "list":
            # List all available intents
            response = "Available intents for detection:\n\n"
            
            for intent in self.intent_detector.intent_patterns.keys():
                # Try to get a sample response for this intent
                sample = self.intent_detector.get_response_for_intent(intent, "default") or "No default response"
                if len(sample) > 50:
                    sample = sample[:47] + "..."
                    
                response += f"• {intent}: {sample}\n"
                
            return response
            
        elif action == "analyze" and len(parts) > 1:
            # Analyze text for intents
            text = parts[1].strip()
            
            if not text:
                return "Please provide text to analyze."
                
            intents = self.intent_detector.detect_intent(text)
            
            if not intents:
                return "No intents detected in the provided text."
                
            response = f"Intent analysis for: '{text}'\n\n"
            
            for intent, confidence in intents:
                response += f"• {intent}: {confidence:.2f}\n"
                
            # Add explanation of top intent
            if intents:
                top_intent, top_confidence = intents[0]
                response += f"\nTop intent: {top_intent} ({top_confidence:.2f})\n"
                
                # Show what response would be generated
                should_respond = self.intent_detector.should_respond(top_intent, "default", top_confidence)
                intent_response = self.intent_detector.get_response_for_intent(top_intent, "default")
                
                if should_respond and intent_response:
                    response += f"\nWould respond with: '{intent_response}'"
                else:
                    response += "\nWould not respond automatically based on this intent."
                    
            return response
            
        elif action == "channels":
            # List channels with custom guidelines
            if not self.intent_detector.channel_guidelines:
                return "No channel-specific guidelines configured."
                
            response = "Channels with custom intent guidelines:\n\n"
            
            for channel, intents in self.intent_detector.channel_guidelines.items():
                response += f"• {channel}: {', '.join(intents.keys())}\n"
                
            return response
            
        elif action == "add" and len(parts) > 1:
            # Add a channel guideline
            try:
                # Format: add <channel> <intent> <priority> <response>
                subparts = parts[1].strip().split(' ', 3)
                
                if len(subparts) < 4:
                    return "Usage: intent add <channel> <intent> <priority> <response>"
                    
                channel, intent, priority, response = subparts
                
                # Validate intent
                if intent not in self.intent_detector.intent_patterns:
                    valid_intents = ", ".join(self.intent_detector.intent_patterns.keys())
                    return f"Invalid intent '{intent}'. Valid intents: {valid_intents}"
                    
                # Validate priority
                if priority not in ["high", "medium", "low"]:
                    return "Invalid priority. Must be 'high', 'medium', or 'low'."
                    
                # Add the guideline
                success = self.intent_detector.add_or_update_channel_guideline(
                    channel_name=channel,
                    intent=intent,
                    response_templates=[response],
                    priority=priority
                )
                
                if success:
                    return f"Successfully added guideline for {intent} in #{channel} with {priority} priority."
                else:
                    return "Failed to save guideline. Check logs for details."
            except Exception as e:
                logger.error(f"Error adding intent guideline: {e}")
                return f"Error: {str(e)}"
                
        elif action == "test" and len(parts) > 1:
            # Test how a message would be handled in a channel
            try:
                subparts = parts[1].strip().split(' ', 1)
                
                if len(subparts) < 2:
                    return "Usage: intent test <channel> <message>"
                    
                channel, test_message = subparts
                
                # Analyze the message
                should_respond, intent_response, intents = self.intent_detector.analyze_message(test_message, channel)
                
                response = f"Intent analysis for '{test_message}' in #{channel}:\n\n"
                
                if intents:
                    # Show detected intents
                    for intent, confidence in sorted(intents.items(), key=lambda x: x[1], reverse=True):
                        threshold = "✓" if confidence >= self.intent_detector.confidence_thresholds["medium"] else "✗"
                        response += f"• {intent}: {confidence:.2f} {threshold}\n"
                        
                    # Show what would happen
                    if should_respond and intent_response:
                        response += f"\nWould respond with: '{intent_response}'"
                    else:
                        response += "\nWould not respond automatically based on intent detection."
                else:
                    response += "No intents detected in the message."
                    
                return response
            except Exception as e:
                logger.error(f"Error testing intent detection: {e}")
                return f"Error: {str(e)}"
        else:
            return f"Invalid intent command. Type {BOT_PREFIX}intent for usage information."

    async def command_language(self, args, username, channel_id, platform):
        """Change the bot's active language."""
        if not args:
            current_language = self.ollama_client.current_language
            available_languages = ", ".join(SUPPORTED_LANGUAGES)
            return f"Current language: {current_language}\nAvailable languages: {available_languages}"
            
        # Try to set the requested language
        success, message = self.ollama_client.set_language(args.strip().lower())
        
        # If language changed successfully, reload the intent detection guidelines
        if success:
            # Update intent detector's language
            if hasattr(self, 'intent_detector'):
                language = args.strip().lower()
                self.intent_detector.reload_guidelines_for_language(language)
                logger.info(f"Reloaded intent detection guidelines for language: {language}")
        
        return message

    async def handle_ai_request(self, message, username, channel_id, platform):
        """Handle a direct request to the AI."""
        # Remove the trigger phrase from the message
        clean_message = message.lower().replace(AI_TRIGGER_PHRASE.lower(), "").strip()
        if not clean_message:
            clean_message = "Hello!"
        
        # Store the user message in vector memory if enabled
        if self.memory_manager.enabled:
            self.memory_manager.store_conversation(
                content=clean_message,
                username=username,
                platform=platform, 
                channel_id=channel_id,
                role="user"
            )
            
        # Get relevant context from memory if available
        memory_context = ""
        if self.memory_manager.enabled:
            memory_context = self.memory_manager.get_relevant_context(
                query=clean_message,
                username=username,
                channel_id=channel_id,
                platform=platform
            )
            
            if memory_context:
                logger.info("Found relevant context from memory for query: %s", clean_message[:30])
                
        # Generate response with memory-enhanced context
        response = await self.ollama_client.generate_response(
            clean_message,
            username=username,
            platform=platform,
            channel_id=channel_id,
            conversation_history=self.get_conversation_history(username, channel_id),
            memory_context=memory_context
        )
        
        # Store AI response in history
        self.store_message(username, channel_id, 'Assistant', response)
        
        # Store the AI response in vector memory if enabled
        if self.memory_manager.enabled:
            self.memory_manager.store_conversation(
                content=response,
                username=username, 
                platform=platform,
                channel_id=channel_id,
                role="assistant"
            )
            
        return response

    async def handle_ai_request_stream(self, message, username, channel_id, platform):
        """Handle a direct request to the AI with streaming response."""
        # Remove the trigger phrase from the message
        clean_message = message.lower().replace(AI_TRIGGER_PHRASE.lower(), "").strip()
        if not clean_message:
            clean_message = "Hello!"
        
        # Store the user message in vector memory if enabled
        if self.memory_manager.enabled:
            self.memory_manager.store_conversation(
                content=clean_message,
                username=username,
                platform=platform, 
                channel_id=channel_id,
                role="user"
            )
            
        # Get relevant context from memory if available
        memory_context = ""
        if self.memory_manager.enabled:
            memory_context = self.memory_manager.get_relevant_context(
                query=clean_message,
                username=username,
                channel_id=channel_id,
                platform=platform
            )
            
            if memory_context:
                logger.info("Found relevant context from memory for query: %s", clean_message[:30])
                
        # Generate streaming response with memory-enhanced context
        response_generator = self.ollama_client.generate_response_stream(
            clean_message,
            username=username,
            platform=platform,
            channel_id=channel_id,
            conversation_history=self.get_conversation_history(username, channel_id),
            memory_context=memory_context
        )
        
        # Track the full response to store in history
        full_response = ""
        
        async for chunk in response_generator:
            full_response += chunk
            yield chunk
        
        # If we got a complete response back (not just chunks)
        if hasattr(response_generator, 'cr_running') and isinstance(response_generator.cr_running, bool) and not response_generator.cr_running:
            try:
                final_response = await response_generator.cr_await()
                if final_response and isinstance(final_response, str):
                    full_response = final_response
            except (StopAsyncIteration, StopIteration, RuntimeError):
                pass
        
        # Store AI response in history
        if full_response:
            self.store_message(username, channel_id, 'Assistant', full_response)
            
            # Store the AI response in vector memory if enabled
            if self.memory_manager.enabled:
                self.memory_manager.store_conversation(
                    content=full_response,
                    username=username, 
                    platform=platform,
                    channel_id=channel_id,
                    role="assistant"
                )

    # Command handlers
    async def command_help(self, args, username, channel_id, platform):
        """Help command handler."""
        # Define admin-only commands for displaying in help
        admin_commands = ['persona', 'language', 'languages', 'knowledge', 'knowledges', 'memory', 'intent']
        
        # Check if user is admin
        is_admin = False
        if platform == 'discord' and username == DISCORD_MASTER_USER:
            is_admin = True
        elif platform == 'twitch' and username == TWITCH_MASTER_USER:
            is_admin = True
            
        help_text = (
            f"Comandos disponibles:\n"
            f"{BOT_PREFIX}help - Mostrar este mensaje de ayuda\n"
            f"{BOT_PREFIX}ping - Comprobar si el bot está en línea\n"
            f"{BOT_PREFIX}ai <mensaje> - Hacer una pregunta a la IA\n"
            f"{BOT_PREFIX}personas - Listar las personalidades disponibles\n"
            f"{BOT_PREFIX}ask <persona> <mensaje> - Hacer una pregunta a una personalidad específica\n"
        )
        
        # Add admin commands section if user is admin
        if is_admin:
            admin_help_text = (
                f"\nComandos de administrador:\n"
                f"{BOT_PREFIX}persona <n> - Cambiar la personalidad de la IA (default, streamer, expert, comedian, motivator)\n"
                f"{BOT_PREFIX}language <idioma> - Cambiar el idioma del bot (english, spanish)\n"
                f"{BOT_PREFIX}languages - Listar los idiomas disponibles\n"
                f"{BOT_PREFIX}knowledge - Gestionar archivos de conocimiento personalizados\n"
                f"{BOT_PREFIX}knowledges - Listar archivos de conocimiento disponibles\n"
                f"{BOT_PREFIX}memory - Gestionar la memoria vectorial del bot\n"
                f"{BOT_PREFIX}intent - Gestionar las respuestas automáticas basadas en intenciones\n"
            )
            help_text += admin_help_text
        else:
            # Let non-admin users know there are admin commands
            help_text += "\nAlgunos comandos adicionales están disponibles solo para administradores."
            
        help_text += f"\n\nTambién puedes mencionar al bot usando '{AI_TRIGGER_PHRASE}' para obtener respuestas de la IA."
        return help_text
        
    async def command_ping(self, args, username, channel_id, platform):
        """Ping command handler."""
        return f"Pong! Bot is online. Platform: {platform}"
        
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

    async def command_list_knowledge(self, args, username, channel_id, platform):
        """List all available knowledge files."""
        return self.ollama_client.list_knowledge_files()

    async def command_ai(self, args, username, channel_id, platform):
        """AI command handler."""
        if not args:
            return f"Please provide a message after {BOT_PREFIX}ai"
            
        response = await self.ollama_client.generate_response(
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
        response = await self.ollama_client.generate_persona_response(
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
        
    async def command_manage_knowledge(self, args, username, channel_id, platform):
        """Manage knowledge files for the AI."""
        if not args:
            return (
                f"Usage:\n"
                f"{BOT_PREFIX}knowledge list - List all knowledge files\n"
                f"{BOT_PREFIX}knowledge activate <n> - Activate a knowledge file\n"
                f"{BOT_PREFIX}knowledge deactivate <n> - Deactivate a knowledge file\n"
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
            
    async def command_manage_memory(self, args, username, channel_id, platform):
        """Manage vector memory for the AI."""
        if not self.memory_manager.enabled:
            return "La memoria vectorial no está disponible. Asegúrate de instalar las dependencias necesarias con: pip install chromadb sentence-transformers"
            
        if not args:
            return (
                f"Uso del comando memoria:\n"
                f"{BOT_PREFIX}memory status - Mostrar estado de la memoria vectorial\n"
                f"{BOT_PREFIX}memory import <archivo> - Importar un archivo a la memoria\n"
                f"{BOT_PREFIX}memory importall - Importar todos los archivos de conocimiento\n"
                f"{BOT_PREFIX}memory search <consulta> - Buscar en la memoria vectorial\n"
                f"{BOT_PREFIX}memory stats - Ver estadísticas de la memoria"
            )
            
        parts = args.split(' ', 1)
        action = parts[0].lower()
        
        if action == "status":
            # Show status of vector memory
            db_path = self.memory_manager.db_path
            model = self.memory_manager.embedding_model_name
            
            # Count items in each collection
            conv_count = 0
            know_count = 0
            
            try:
                conv_count = self.memory_manager.conversations.count()
                know_count = self.memory_manager.knowledge.count()
            except:
                pass
                
            return (
                f"Estado de la memoria vectorial:\n"
                f"- Base de datos: {db_path}\n"
                f"- Modelo de embeddings: {model}\n"
                f"- Elementos en conversaciones: {conv_count}\n"
                f"- Elementos en conocimiento: {know_count}\n"
                f"- Umbral de similitud: {self.memory_manager.similarity_threshold}"
            )
            
        elif action == "import" and len(parts) > 1:
            # Import a file into memory
            file_name = parts[1].strip()
            knowledge_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge")
            file_path = os.path.join(knowledge_dir, file_name)
            
            if not os.path.exists(file_path):
                return f"Archivo no encontrado: {file_name}"
                
            # Import the file
            success_count, total_chunks = self.memory_manager.import_knowledge_from_file(file_path)
            
            if success_count > 0:
                return f"Importados {success_count} de {total_chunks} fragmentos de {file_name} a la memoria vectorial."
            else:
                return f"No se pudo importar el archivo {file_name}."
                
        elif action == "importall":
            # Import all knowledge files
            knowledge_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge")
            file_patterns = ['*.txt', '*.md', '*.json']
            
            total_files = 0
            total_success = 0
            total_chunks = 0
            
            for pattern in file_patterns:
                for file_path in glob.glob(os.path.join(knowledge_dir, pattern)):
                    file_name = os.path.basename(file_path)
                    total_files += 1
                    
                    success_count, chunk_count = self.memory_manager.import_knowledge_from_file(file_path)
                    total_success += success_count
                    total_chunks += chunk_count
                    
            if total_files > 0:
                return f"Importados {total_success} de {total_chunks} fragmentos de {total_files} archivos a la memoria vectorial."
            else:
                return "No se encontraron archivos de conocimiento para importar."
                
        elif action == "search" and len(parts) > 1:
            # Search vector memory
            query = parts[1].strip()
            
            results = self.memory_manager.search_memory(query, limit=5)
            
            if not results:
                return "No se encontraron resultados para tu búsqueda."
                
            response = f"Resultados para: '{query}'\n\n"
            
            for i, result in enumerate(results):
                collection = result["collection"]
                similarity = result["similarity"] * 100
                content = result["content"]
                
                # Truncate content if too long
                if len(content) > 100:
                    content = content[:97] + "..."
                    
                # Format based on collection type
                if "knowledge" in collection:
                    source = result["metadata"].get("source", "desconocido")
                    response += f"{i+1}. [{similarity:.1f}%] {content} (Fuente: {source})\n\n"
                else:
                    username = result["metadata"].get("username", "desconocido")
                    role = "Usuario" if result["metadata"].get("role") == "user" else "Asistente"
                    response += f"{i+1}. [{similarity:.1f}%] {role} {username}: {content}\n\n"
                    
            return response
            
        elif action == "stats":
            # Show memory statistics
            db_path = self.memory_manager.db_path
            db_size = 0
            
            # Calculate database size
            for root, dirs, files in os.walk(db_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    db_size += os.path.getsize(file_path)
                    
            # Convert to MB
            db_size_mb = db_size / (1024 * 1024)
            
            try:
                conv_count = self.memory_manager.conversations.count()
                know_count = self.memory_manager.knowledge.count()
                
                return (
                    f"Estadísticas de la memoria vectorial:\n"
                    f"- Tamaño de la base de datos: {db_size_mb:.2f} MB\n"
                    f"- Total de elementos: {conv_count + know_count}\n"
                    f"  - Conversaciones: {conv_count}\n"
                    f"  - Conocimiento: {know_count}\n"
                    f"- Ubicación: {db_path}"
                )
            except:
                return (
                    f"Estadísticas de la memoria vectorial:\n"
                    f"- Tamaño de la base de datos: {db_size_mb:.2f} MB\n"
                    f"- Ubicación: {db_path}"
                )
        else:
            return f"Comando de memoria no válido. Escribe {BOT_PREFIX}memory para ver las opciones disponibles."