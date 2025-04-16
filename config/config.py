import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Twitch Configuration
TWITCH_TOKEN = os.getenv("TWITCH_TOKEN", "")
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET", "")
TWITCH_CHANNEL = os.getenv("TWITCH_CHANNEL", "")
TWITCH_MASTER_USER = os.getenv("TWITCH_MASTER_USER", "")

# Discord Configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
DISCORD_GUILD = os.getenv("DISCORD_GUILD", "")
DISCORD_CHANNELS = os.getenv("DISCORD_CHANNELS", "").split(",")
DISCORD_MASTER_USER = os.getenv("DISCORD_MASTER_USER", "")

# Ollama Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama2")

# Enhanced AI Configuration
AI_PERSONAS = {
    "default": "Eres un asistente útil integrado con un bot de Twitch y Discord. Mantén tus respuestas concisas, amigables y apropiadas para plataformas de streaming.",
    "streamer": "Eres una personalidad de streaming carismática y entretenida. Tus respuestas deben ser enérgicas, atractivas y divertidas.",
    "expert": "Eres un experto con conocimientos que proporciona información precisa y detallada mientras mantiene un tono profesional.",
    "comedian": "Eres un comediante ingenioso con un sentido del humor desenfadado. Tus respuestas deben ser divertidas pero apropiadas para todo tipo de público.",
    "motivator": "Eres un motivador inspirador que ofrece mensajes alentadores y de apoyo.",
}

# Language settings
LANGUAGE = os.getenv("LANGUAGE", "spanish").lower()
SUPPORTED_LANGUAGES = ["english", "spanish"]

# Language-specific system prompts with stronger instructions
LANGUAGE_PROMPTS = {
    "english": "IMPORTANT: You must ALWAYS respond in English, regardless of the language of the input. Do NOT translate your responses to any other language. Your responses should be in grammatically correct and natural-sounding English.",
    "spanish": "IMPORTANTE: Debes SIEMPRE responder en español, sin importar el idioma de la entrada. NO traduzcas tus respuestas a ningún otro idioma. Tus respuestas deben estar en español gramaticalmente correcto y natural."
}

# Get current AI persona with default fallback
DEFAULT_PERSONA = os.getenv("DEFAULT_PERSONA", "default")
if DEFAULT_PERSONA not in AI_PERSONAS:
    DEFAULT_PERSONA = "default"

# Memory and Vector Database Configuration
ENABLE_VECTOR_MEMORY = os.getenv("ENABLE_VECTOR_MEMORY", "True").lower() == "true"
MEMORY_DATABASE_PATH = os.getenv("MEMORY_DATABASE_PATH", "data/memory")
MEMORY_COLLECTION_CONVERSATIONS = "conversations"
MEMORY_COLLECTION_KNOWLEDGE = "knowledge"
MEMORY_EMBEDDING_MODEL = os.getenv("MEMORY_EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
MEMORY_SIMILARITY_THRESHOLD = float(os.getenv("MEMORY_SIMILARITY_THRESHOLD", "0.75"))  # Threshold for considering content similar
MEMORY_MAX_RESULTS = int(os.getenv("MEMORY_MAX_RESULTS", "5"))  # Max results to return from memory search

# Context awareness settings
MEMORY_SIZE = int(os.getenv("MEMORY_SIZE", "10"))  # Number of past messages to remember per conversation
CHANNEL_CONTEXT_ENABLED = os.getenv("CHANNEL_CONTEXT_ENABLED", "True").lower() == "true"
GLOBAL_CONTEXT_SIZE = int(os.getenv("GLOBAL_CONTEXT_SIZE", "5"))  # Number of recent channel messages to consider

# Bot Configuration
BOT_PREFIX = os.getenv("BOT_PREFIX", "!")
ENABLE_AI_RESPONSE = os.getenv("ENABLE_AI_RESPONSE", "True").lower() == "true"
AI_TRIGGER_PHRASE = os.getenv("AI_TRIGGER_PHRASE", "@bot")
AI_RESPONSE_PROBABILITY = float(os.getenv("AI_RESPONSE_PROBABILITY", "0.1"))  # 10% chance by default

# NLP and Intent Detection Configuration
ENABLE_INTENT_DETECTION = os.getenv("ENABLE_INTENT_DETECTION", "True").lower() == "true"  # Enable advanced NLP intent detection