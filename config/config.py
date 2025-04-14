import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Twitch Configuration
TWITCH_TOKEN = os.getenv("TWITCH_TOKEN", "")
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET", "")
TWITCH_CHANNEL = os.getenv("TWITCH_CHANNEL", "")

# Discord Configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
DISCORD_GUILD = os.getenv("DISCORD_GUILD", "")
DISCORD_CHANNELS = os.getenv("DISCORD_CHANNELS", "").split(",")

# Ollama Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama2")

# Enhanced AI Configuration
AI_PERSONAS = {
    "default": "You are a helpful assistant integrated with a Twitch and Discord bot. Keep responses concise, friendly, and appropriate for streaming platforms.",
    "streamer": "You are a charismatic and entertaining streaming personality. Your responses should be energetic, engaging, and fun.",
    "expert": "You are a knowledgeable expert providing accurate and detailed information while maintaining a professional tone.",
    "comedian": "You are a witty comedian with a lighthearted sense of humor. Your responses should be funny but appropriate for all audiences.",
    "motivator": "You are an inspirational motivator offering encouraging and supportive messages.",
}

# Language settings
LANGUAGE = os.getenv("LANGUAGE", "english").lower()
SUPPORTED_LANGUAGES = ["english", "spanish"]

# Language-specific system prompts
LANGUAGE_PROMPTS = {
    "english": "Always respond in English, regardless of the language of the input. Your responses should be in grammatically correct and natural-sounding English.",
    "spanish": "Always respond in Spanish (español), regardless of the language of the input. Your responses should be in grammatically correct and natural-sounding Spanish."
}

# Get current AI persona with default fallback
DEFAULT_PERSONA = os.getenv("DEFAULT_PERSONA", "default")
if DEFAULT_PERSONA not in AI_PERSONAS:
    DEFAULT_PERSONA = "default"

# Context awareness settings
MEMORY_SIZE = int(os.getenv("MEMORY_SIZE", "10"))  # Number of past messages to remember per conversation
CHANNEL_CONTEXT_ENABLED = os.getenv("CHANNEL_CONTEXT_ENABLED", "True").lower() == "true"
GLOBAL_CONTEXT_SIZE = int(os.getenv("GLOBAL_CONTEXT_SIZE", "5"))  # Number of recent channel messages to consider

# Bot Configuration
BOT_PREFIX = os.getenv("BOT_PREFIX", "!")
ENABLE_AI_RESPONSE = os.getenv("ENABLE_AI_RESPONSE", "True").lower() == "true"
AI_TRIGGER_PHRASE = os.getenv("AI_TRIGGER_PHRASE", "@bot")
AI_RESPONSE_PROBABILITY = float(os.getenv("AI_RESPONSE_PROBABILITY", "0.1"))  # 10% chance by default