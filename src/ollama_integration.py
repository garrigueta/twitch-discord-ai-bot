"""
Ollama API integration for the AI bot.
"""
import os
import json
import logging
import glob
import aiohttp
import asyncio
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
        
        # Auto-activate all knowledge files at startup
        self._activate_all_knowledge_files()
        
    def _activate_all_knowledge_files(self):
        """Automatically activate all knowledge files at startup."""
        knowledge_files = self._scan_knowledge_files()
        
        if not knowledge_files:
            logger.info("No knowledge files found to activate at startup.")
            return
            
        # Activate each knowledge file
        for knowledge_name in knowledge_files:
            success, message = self.activate_knowledge(knowledge_name)
            if success:
                logger.info("Auto-activated knowledge file at startup: %s", knowledge_name)
            else:
                logger.warning("Failed to activate knowledge file at startup: %s (%s)", knowledge_name, message)

    async def generate_response(self, message: str, username: str = "", platform: str = "", 
                          channel_id: str = "", conversation_history: List[Dict[str, str]] = None,
                          memory_context: str = None) -> str:
        """
        Generate a response from the Ollama API.
        
        Args:
            message: The message to respond to
            username: The username of the sender
            platform: The platform (twitch, discord)
            channel_id: The channel ID where the message was sent
            conversation_history: List of previous messages in the conversation
            memory_context: Context retrieved from vector memory database
            
        Returns:
            The generated response
        """
        # Ensure knowledge files are activated
        if not self.active_knowledge:
            # Auto-activate knowledge files if none are active
            knowledge_files = self._scan_knowledge_files()
            for knowledge_name in knowledge_files:
                success, _ = self.activate_knowledge(knowledge_name)
                if success:
                    logger.info("Auto-activated knowledge file: %s", knowledge_name)
        
        system_prompt = self.get_current_persona_prompt()
        
        # Add platform-specific context to the system prompt
        platform_context = f"The user {username} is chatting on {platform}."
        system_prompt = f"{system_prompt}\n\n{platform_context}"
        
        # Add vector memory context if available
        if memory_context:
            memory_prompt = (
                "\n\nA continuación hay información relevante de la base de datos vectorial "
                "que puede ser útil para responder a la consulta del usuario. Esta información "
                "proviene tanto de conversaciones pasadas como de la base de conocimientos.\n\n"
                f"{memory_context}"
            )
            system_prompt = f"{system_prompt}\n\n{memory_prompt}"
            logger.info("Added vector memory context to prompt")
        
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
        
        # Define increased timeout and max retries
        timeout = aiohttp.ClientTimeout(total=45)  # Increased to 45 seconds
        max_retries = 2
        retry_delay = 1  # Seconds to wait between retries
        
        for attempt in range(max_retries + 1):
            try:
                # Use aiohttp for async HTTP requests
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.api_url}/api/chat", 
                        json=payload,
                        timeout=timeout
                    ) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error("Ollama API error (attempt %d/%d): %s - %s", 
                                         attempt + 1, max_retries + 1, response.status, error_text)
                            
                            # If this was the last attempt, return error message
                            if attempt == max_retries:
                                return "Lo siento, estoy teniendo problemas para conectarme a mi cerebro en este momento."
                        
                        data = await response.json()
                        
                        # Extract the response text
                        if "message" in data and "content" in data["message"]:
                            result = data["message"]["content"]
                            return result.strip()
                        
                        # If we got here without a proper response, try again
                        logger.warning("No valid response in Ollama API result (attempt %d/%d)", 
                                       attempt + 1, max_retries + 1)
                        
                        # If this was our last attempt, return a fallback message
                        if attempt == max_retries:
                            return "No estoy seguro de cómo responder a eso."
                
            except asyncio.TimeoutError:
                logger.error("Timeout calling Ollama API (attempt %d/%d, timeout=%d seconds)",
                             attempt + 1, max_retries + 1, timeout.total)
                
                # If this was the last attempt, return specific timeout message
                if attempt == max_retries:
                    return ("Lo siento, me está tomando demasiado tiempo procesar tu mensaje. " 
                            "El modelo podría estar ocupado o la consulta es demasiado compleja. " 
                            "¿Podrías intentar con una pregunta más simple?")
            
            except aiohttp.ClientError as e:
                logger.error("Error calling Ollama API (attempt %d/%d): %s", 
                             attempt + 1, max_retries + 1, e)
                
                # If this was the last attempt, return error message
                if attempt == max_retries:
                    return "Lo siento, estoy teniendo problemas técnicos. Intentémoslo de nuevo más tarde."
            
            # Wait before retrying
            if attempt < max_retries:
                await asyncio.sleep(retry_delay)
                # Increase delay for next attempt
                retry_delay *= 2  # Exponential backoff

    async def generate_response_stream(self, message: str, username: str = "", platform: str = "", 
                                channel_id: str = "", conversation_history: List[Dict[str, str]] = None,
                                memory_context: str = None):
        """
        Generate a streaming response from the Ollama API.
        
        Args:
            message: The message to respond to
            username: The username of the sender
            platform: The platform (twitch, discord)
            channel_id: The channel ID where the message was sent
            conversation_history: List of previous messages in the conversation
            memory_context: Context retrieved from vector memory database
            
        Returns:
            An async generator that yields response chunks as they are generated
        """
        # Ensure knowledge files are activated
        if not self.active_knowledge:
            # Auto-activate knowledge files if none are active
            knowledge_files = self._scan_knowledge_files()
            for knowledge_name in knowledge_files:
                success, _ = self.activate_knowledge(knowledge_name)
                if success:
                    logger.info("Auto-activated knowledge file: %s", knowledge_name)
        
        system_prompt = self.get_current_persona_prompt()
        
        # Add platform-specific context to the system prompt
        platform_context = f"The user {username} is chatting on {platform}."
        system_prompt = f"{system_prompt}\n\n{platform_context}"
        
        # Add vector memory context if available
        if memory_context:
            memory_prompt = (
                "\n\nA continuación hay información relevante de la base de datos vectorial "
                "que puede ser útil para responder a la consulta del usuario. Esta información "
                "proviene tanto de conversaciones pasadas como de la base de conocimientos.\n\n"
                f"{memory_context}"
            )
            system_prompt = f"{system_prompt}\n\n{memory_prompt}"
            logger.info("Added vector memory context to prompt")
        
        # Call the API
        payload = {
            "model": self.model,
            "prompt": message,
            "system": system_prompt,
            "stream": True,  # Enable streaming
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
        
        # Define timeout
        timeout = aiohttp.ClientTimeout(total=60)  # Longer timeout for streaming
        
        # For error tracking
        error_occurred = False
        full_response = ""
        
        try:
            # Use aiohttp for async HTTP requests with streaming
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/api/chat", 
                    json=payload,
                    timeout=timeout
                ) as response:
                    if response.status != 200:
                        logger.error("Ollama API error: %s - %s", response.status, await response.text())
                        yield "Lo siento, estoy teniendo problemas para conectarme a mi cerebro en este momento."
                        error_occurred = True
                        
                    if not error_occurred:
                        # Process the streaming response
                        buffer = ""
                        
                        async for line in response.content:
                            if not line:
                                continue
                                
                            line_text = line.decode('utf-8').strip()
                            if not line_text:
                                continue
                                
                            try:
                                # Parse JSON response chunk
                                data = json.loads(line_text)
                                
                                if "message" in data and "content" in data["message"]:
                                    # Get the new content chunk
                                    chunk = data["message"]["content"]
                                    if chunk:
                                        # Append to the full response
                                        full_response += chunk
                                        buffer += chunk
                                        
                                        # Yield the buffer when we have a decent chunk or at end
                                        if len(buffer) >= 4 or "done" in data:
                                            yield buffer
                                            buffer = ""
                                            
                                # Check if we're done
                                if "done" in data and data["done"]:
                                    if buffer:  # Yield any remaining buffer
                                        yield buffer
                                    break
                                    
                            except json.JSONDecodeError:
                                logger.warning("Failed to parse streaming response chunk: %s", line_text)
                                continue
                                
                        # If we didn't get any response, yield a fallback message
                        if not full_response:
                            yield "No estoy seguro de cómo responder a eso."
                    
        except asyncio.TimeoutError:
            logger.error("Timeout in streaming response from Ollama API")
            yield "Lo siento, me está tomando demasiado tiempo procesar tu mensaje. ¿Podrías intentar con una pregunta más simple?"
            full_response = "Lo siento, me está tomando demasiado tiempo procesar tu mensaje."
            
        except aiohttp.ClientError as e:
            logger.error("Error in streaming response from Ollama API: %s", e)
            yield "Lo siento, estoy teniendo problemas técnicos. Intentémoslo de nuevo más tarde."
            full_response = "Lo siento, estoy teniendo problemas técnicos."
            
        # Store the completed response as an attribute that can be accessed after the generator completes
        # This is a common pattern to return values from async generators
        self._last_stream_response = full_response.strip()

    async def generate_persona_response(self, message: str, persona: str, username: str = "", 
                                platform: str = "", channel_id: str = "", 
                                conversation_history: List[Dict[str, str]] = None,
                                memory_context: str = None) -> str:
        """
        Generate a response from a specific persona without changing the current one.
        
        Args:
            message: The message to respond to
            persona: The persona to use for this response
            username: The username of the sender
            platform: The platform (twitch, discord)
            channel_id: The channel ID where the message was sent
            conversation_history: List of previous messages in the conversation
            memory_context: Context retrieved from vector memory database
            
        Returns:
            The generated response
        """
        # Store current persona
        original_persona = self.current_persona
        
        # Temporarily switch to requested persona
        self.current_persona = persona
        
        # Generate response with the temporary persona
        response = await self.generate_response(
            message, 
            username=username, 
            platform=platform,
            channel_id=channel_id,
            conversation_history=conversation_history,
            memory_context=memory_context
        )
        
        # Restore original persona
        self.current_persona = original_persona
        
        return response
        
    async def analyze_message(self, message: str, username: str = "", platform: str = "",
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
            "Eres un asistente útil que decide si un mensaje en un chat requiere una respuesta. "
            "Si el mensaje es una pregunta, un saludo o parece esperar una respuesta, "
            "devuelve 'RESPOND: [tu respuesta]'. Si no requiere respuesta, devuelve 'IGNORE'."
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
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/api/generate", 
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)  # 10 second timeout
                ) as response:
                    if response.status != 200:
                        logger.error("Error de API Ollama: %s - %s", response.status, await response.text())
                        return False, None
                    
                    data = await response.json()
                    
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
            
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.error("Error al llamar a la API de Ollama para análisis: %s", e)
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
            return True, f"Personalidad cambiada a {persona}"
        else:
            available = ", ".join(AI_PERSONAS.keys())
            return False, f"Personalidad '{persona}' desconocida. Personalidades disponibles: {available}"
            
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
            return True, f"Idioma cambiado a {language}"
        else:
            available = ", ".join(SUPPORTED_LANGUAGES)
            return False, f"Idioma '{language}' desconocido. Idiomas disponibles: {available}"
        
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
                "\n\nTienes acceso a la siguiente base de conocimientos. Usa esta información al responder preguntas:\n\n"
                f"{knowledge_content}"
                "\n\nCuando respondas preguntas que se relacionen directamente con la base de conocimientos, asegúrate de usar SOLO la información proporcionada."
            )
        
        # Add additional context awareness guidance (language instructions first and last for emphasis)
        context_prompt = (
            f"{language_prompt}\n\n" 
            f"{base_prompt}\n\n"  
            "Presta atención al historial de conversación y al contexto proporcionado. "
            "Tus respuestas deben ser concisas (1-3 oraciones) y adaptadas a la plataforma. "
            "Evita cualquier tema controvertido y contenido potencialmente dañino."
            f"{knowledge_prompt}\n\n"
            f"INSTRUCCIÓN FINAL IMPORTANTE: {language_prompt}"  # Emphasized as final instruction for higher adherence
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
            return False, f"Archivo de conocimiento '{knowledge_name}' no encontrado"
            
        if knowledge_name in self.active_knowledge:
            return True, f"Archivo de conocimiento '{knowledge_name}' ya está activo"
            
        self.active_knowledge.append(knowledge_name)
        logger.info(f"Activated knowledge file: {knowledge_name}")
        return True, f"Archivo de conocimiento '{knowledge_name}' activado"
        
    def deactivate_knowledge(self, knowledge_name):
        """Deactivate a knowledge file."""
        if knowledge_name not in self.active_knowledge:
            return False, f"Archivo de conocimiento '{knowledge_name}' no está activo"
            
        self.active_knowledge.remove(knowledge_name)
        logger.info(f"Deactivated knowledge file: {knowledge_name}")
        return True, f"Archivo de conocimiento '{knowledge_name}' desactivado"
        
    def list_knowledge_files(self):
        """List all available knowledge files."""
        knowledge_files = self._scan_knowledge_files()
        result = "Archivos de conocimiento disponibles:\n\n"
        
        if not knowledge_files:
            return result + "No se encontraron archivos de conocimiento. Añade archivos .txt, .md o .json al directorio 'knowledge'."
            
        for name, info in knowledge_files.items():
            status = "[ACTIVO]" if name in self.active_knowledge else ""
            size_kb = info['size'] / 1024
            result += f"• {name} ({info['type']}, {size_kb:.1f} KB) {status}\n"
            
        return result

    async def health_check(self) -> Tuple[bool, str]:
        """
        Perform a health check on the Ollama API to ensure it's responsive.
        
        Returns:
            A tuple of (is_healthy, message)
        """
        try:
            # Use a short timeout for the health check
            timeout = aiohttp.ClientTimeout(total=10)
            
            # Create a simple query to test API responsiveness
            payload = {
                "model": self.model,
                "prompt": "Hello",
                "system": "You are a helpful assistant. Respond with 'OK' only.",
                "stream": False,
                "options": {
                    "temperature": 0.0,  # Use deterministic output
                    "num_predict": 10   # Keep response very short
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/api/chat", 
                    json=payload,
                    timeout=timeout
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error("Health check failed: %s - %s", response.status, error_text)
                        return False, f"API error: {response.status}"
                    
                    data = await response.json()
                    
                    # Verify we got a valid response structure
                    if "message" in data and "content" in data["message"]:
                        logger.info("Health check successful: Ollama API is responsive")
                        return True, "Ollama API is responsive"
                    else:
                        logger.error("Health check failed: Unexpected response format")
                        return False, "Unexpected response format from API"
            
        except asyncio.TimeoutError:
            logger.error("Health check failed: Timeout connecting to Ollama API")
            return False, "Timeout connecting to Ollama API"
            
        except aiohttp.ClientError as e:
            logger.error("Health check failed: %s", e)
            return False, f"Connection error: {e}"
            
        except Exception as e:
            logger.error("Health check failed with unexpected error: %s", e)
            return False, f"Unexpected error: {e}"