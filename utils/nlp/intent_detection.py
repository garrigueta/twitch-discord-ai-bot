import logging
import re
import json
import os
from typing import Dict, List, Optional, Tuple, Any
import random

logger = logging.getLogger(__name__)

class IntentDetector:
    """
    Advanced NLP-based intent detection for Discord messages.
    Helps the bot understand the context and intent of messages to provide appropriate responses.
    """
    
    def __init__(self):
        self.channel_guidelines: Dict[str, Dict[str, Any]] = {}
        self.default_guidelines: Dict[str, Any] = {}
        self.knowledge_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "knowledge")
        self.loaded = False
        self.current_language = None  # Will be set when guidelines are loaded
        
        # Intent categories and their patterns/keywords - English and Spanish patterns
        self.intent_patterns = {
            "greeting": [
                # English patterns
                r"\b(hi|hello|hey|greetings|howdy|what's up|sup)\b",
                r"^(good\s+(morning|afternoon|evening|day))$",
                # Spanish patterns
                r"\b(hola|saludos|qué tal|qué hay|buenas)\b",
                r"^(buen(os|as)\s+(días|tardes|noches))$"
            ],
            "question": [
                # Universal
                r"\?\s*$",
                # English patterns
                r"\b(what|how|why|when|where|who|which|whose|whom|can|could|would|should|is|are|am|was|were)\b.+\?",
                r"\b(explain|tell me|share|describe)\b",
                # Spanish patterns
                r"\b(qué|cómo|por qué|cuándo|dónde|quién|cuál|cuáles|puedo|podría|debería|es|son|soy|fue|fueron)\b.+\?",
                r"\b(explica|dime|comparte|describe)\b"
            ],
            "help_request": [
                # English patterns
                r"\b(help|assist|support|guide|how\s+to|how\s+do\s+i)\b",
                r"\b(stuck|confused|lost|don't\s+understand|cant\s+figure\s+out|having\s+trouble)\b",
                # Spanish patterns
                r"\b(ayuda|asistencia|apoyo|guía|cómo\s+puedo|cómo\s+se\s+hace)\b",
                r"\b(atascado|confundido|perdido|no\s+entiendo|no\s+puedo\s+entender|tengo\s+problemas)\b"
            ],
            "gratitude": [
                # English patterns
                r"\b(thanks|thank\s+you|thx|appreciate|grateful)\b",
                # Spanish patterns
                r"\b(gracias|agradecido|agradezco|te\s+lo\s+agradezco)\b"
            ],
            "frustration": [
                # English patterns
                r"\b(annoyed|annoying|frustrated|frustrating|upset|angry|mad|irritated)\b",
                r"\b(doesn'?t\s+work|not\s+working|broken|useless|stupid|dumb)\b",
                r"(wtf|wth|bs|bullshit|fuck|damn|shit)",
                # Spanish patterns
                r"\b(molesto|frustrante|frustrado|enfadado|enojado|irritado)\b",
                r"\b(no\s+funciona|roto|inútil|estúpido|tonto)\b",
                r"(wtf|no\s+jodas|mierda|carajo|joder)"
            ],
            "feedback": [
                # English patterns
                r"\b(feedback|suggest|suggestion|improve|improvement|feature\s+request)\b",
                # Spanish patterns
                r"\b(retroalimentación|comentario|sugerencia|sugerir|mejorar|mejora|función\s+solicitada)\b"
            ],
            "error_report": [
                # English patterns
                r"\b(error|bug|issue|problem|crash|exception|failed|failing|fails)\b",
                r"\b(not\s+working|doesn'?t\s+work|stopped\s+working)\b",
                # Spanish patterns
                r"\b(error|fallo|problema|crashea|excepción|falló|fallando|falla)\b",
                r"\b(no\s+funciona|dejó\s+de\s+funcionar)\b"
            ],
            "feature_request": [
                # English patterns
                r"\b(feature\s+request|suggestion|would\s+be\s+nice|could\s+you\s+add|please\s+add|should\s+add)\b",
                r"\b(it\s+would\s+be\s+(great|nice|helpful|awesome)\s+if)\b",
                # Spanish patterns
                r"\b(solicitud\s+de\s+función|solicitud\s+de\s+característica|sugerencia|sería\s+bueno|podrías\s+añadir|por\s+favor\s+añade|deberías\s+añadir)\b",
                r"\b(sería\s+(genial|bueno|útil|increíble)\s+si)\b"
            ],
            "introduction": [
                # English patterns
                r"\b(new\s+here|first\s+time|just\s+joined|introduce\s+myself)\b",
                r"^(hi|hello|hey),?\s+I'?m\s+[a-z0-9_-]+",
                r"^(hi|hello|hey)\s+everyone",
                # Spanish patterns
                r"\b(nuevo\s+aquí|nuevo\s+por\s+aquí|primera\s+vez|recién\s+me\s+uní|me\s+presento)\b",
                r"^(hola|saludos),?\s+soy\s+[a-z0-9_-]+",
                r"^(hola|saludos)\s+a\s+todos"
            ],
            "farewell": [
                # English patterns
                r"\b(bye|goodbye|see\s+you|catch\s+you\s+later|talk\s+later|going\s+to\s+bed|heading\s+out)\b",
                # Spanish patterns
                r"\b(adiós|hasta\s+luego|nos\s+vemos|hablamos\s+luego|me\s+voy\s+a\s+dormir|me\s+tengo\s+que\s+ir)\b"
            ]
        }
        
        # Intent confidence thresholds - can be adjusted
        self.confidence_thresholds = {
            "high": 0.8,
            "medium": 0.5,
            "low": 0.3
        }
        
        # Available languages and their guideline filenames
        self.language_files = {
            "english": "discord_guidelines.json",
            "spanish": "discord_guidelines_spanish.json"
        }
        
        # Load guidelines from file
        self.load_guidelines()
        
    def load_guidelines(self, language=None):
        """
        Load channel-specific guidelines from the appropriate language file.
        
        Args:
            language: Optional language to load. If None, uses the language from config.
        """
        # Import here to avoid circular imports
        from config.config import LANGUAGE, SUPPORTED_LANGUAGES
        
        # Determine which language to use
        use_language = language or LANGUAGE
        
        # Debug log to see what language is being requested
        logger.info(f"Requested to load guidelines for language: '{use_language}'")
        
        # Normalize language name to lowercase
        use_language = use_language.lower().strip()
        
        # Check if it's in supported languages
        if use_language not in SUPPORTED_LANGUAGES:
            logger.warning(f"Language '{use_language}' not in supported languages: {SUPPORTED_LANGUAGES}")
            use_language = "english"  # Default to English
            
        # Check if it's in our language files dictionary
        if use_language not in self.language_files:
            logger.warning(f"Language '{use_language}' not supported for guidelines (options: {', '.join(self.language_files.keys())}), falling back to english")
            use_language = "english"
            
        self.current_language = use_language
        guidelines_filename = self.language_files[use_language]
        guidelines_path = os.path.join(self.knowledge_dir, guidelines_filename)
        
        logger.info(f"Loading {use_language} guidelines from {guidelines_path}")
        
        if not os.path.exists(guidelines_path):
            logger.info(f"No {guidelines_filename} found in knowledge directory. Creating default template.")
            self._create_default_guidelines(guidelines_path, use_language)
            self.loaded = True
            return
            
        try:
            with open(guidelines_path, 'r', encoding='utf-8') as f:
                guidelines_data = json.load(f)
                
            # Process channel guidelines
            if 'channels' in guidelines_data:
                self.channel_guidelines = guidelines_data['channels']
                logger.info(f"Loaded {use_language} guidelines for {len(self.channel_guidelines)} channels")
                
            # Process default guidelines
            if 'default' in guidelines_data:
                self.default_guidelines = guidelines_data['default']
                logger.info(f"Loaded {use_language} default guidelines")
                
            self.loaded = True
            logger.info(f"Successfully loaded {use_language} intent detection guidelines")
        except Exception as e:
            logger.error(f"Error loading {use_language} guidelines: {e}")
            self.loaded = False
            
    def _create_default_guidelines(self, guidelines_path, language):
        """
        Create default guidelines template file for the specified language.
        """
        # Create default English guidelines
        if language == "english":
            default_guidelines = {
                "default": {
                    "greeting": {
                        "response_templates": [
                            "Hello there! How can I help you today?",
                            "Hi! What can I assist you with?",
                            "Hey! I'm here if you need any help."
                        ],
                        "priority": "medium"
                    },
                    "help_request": {
                        "response_templates": [
                            "I'd be happy to help. What specifically are you having trouble with?",
                            "I can definitely assist with that. Could you provide more details about what you need help with?"
                        ],
                        "priority": "high"
                    },
                    "error_report": {
                        "response_templates": [
                            "I'm sorry to hear you're experiencing issues. To help troubleshoot, could you please provide:\n- Steps to reproduce the issue\n- Any error messages you're seeing\n- What you expected to happen",
                            "Let's figure out what's going wrong. Can you share what steps led to this error and any error messages you received?"
                        ],
                        "priority": "high"
                    }
                },
                "channels": {
                    "support": {
                        "error_report": {
                            "response_templates": [
                                "Thank you for reporting this issue. To help our team investigate, please provide:\n- Steps to reproduce\n- Expected behavior\n- Actual behavior\n- Screenshots if possible",
                                "I've noted your error report. Could you please provide more details including exact steps to reproduce and any error messages you see?"
                            ],
                            "priority": "high"
                        },
                        "feature_request": {
                            "response_templates": [
                                "Thanks for your suggestion! Please describe:\n- The problem this solves\n- How you envision it working\n- Why it would be valuable",
                                "We appreciate feature ideas! Could you elaborate on the use case and how this would improve your experience?"
                            ],
                            "priority": "medium"
                        }
                    },
                    "welcome": {
                        "introduction": {
                            "response_templates": [
                                "Welcome to our community! 👋 Feel free to introduce yourself and check out our rules channel.",
                                "Great to have you join us! Take a moment to read our community guidelines and make yourself at home."
                            ],
                            "priority": "high"
                        }
                    }
                }
            }
        # Create default Spanish guidelines
        else:
            default_guidelines = {
                "default": {
                    "greeting": {
                        "response_templates": [
                            "¡Hola! ¿En qué puedo ayudarte hoy?",
                            "¡Hola! ¿Cómo puedo asistirte?",
                            "¡Hey! Estoy aquí si necesitas ayuda."
                        ],
                        "priority": "medium"
                    },
                    "help_request": {
                        "response_templates": [
                            "Estaré encantado de ayudar. ¿Con qué específicamente estás teniendo problemas?",
                            "Definitivamente puedo ayudarte con eso. ¿Podrías proporcionar más detalles sobre lo que necesitas?"
                        ],
                        "priority": "high"
                    },
                    "error_report": {
                        "response_templates": [
                            "Lamento que estés experimentando problemas. Para ayudar a solucionar, ¿podrías proporcionar:\n- Pasos para reproducir el problema\n- Cualquier mensaje de error que estés viendo\n- Lo que esperabas que sucediera",
                            "Vamos a averiguar qué está fallando. ¿Puedes compartir qué pasos llevaron a este error y qué mensajes de error recibiste?"
                        ],
                        "priority": "high"
                    }
                },
                "channels": {
                    "support": {
                        "error_report": {
                            "response_templates": [
                                "Gracias por reportar este problema. Para ayudar a nuestro equipo a investigar, por favor proporciona:\n- Pasos para reproducir\n- Comportamiento esperado\n- Comportamiento actual\n- Capturas de pantalla si es posible",
                                "He tomado nota de tu reporte de error. ¿Podrías proporcionar más detalles incluyendo pasos exactos para reproducir y cualquier mensaje de error que veas?"
                            ],
                            "priority": "high"
                        },
                        "feature_request": {
                            "response_templates": [
                                "¡Gracias por tu sugerencia! Por favor describe:\n- El problema que esto resuelve\n- Cómo imaginas que funcionaría\n- Por qué sería valioso",
                                "¡Apreciamos las ideas para nuevas funciones! ¿Podrías elaborar sobre el caso de uso y cómo esto mejoraría tu experiencia?"
                            ],
                            "priority": "medium"
                        }
                    },
                    "welcome": {
                        "introduction": {
                            "response_templates": [
                                "¡Bienvenido a nuestra comunidad! 👋 Siéntete libre de presentarte y echa un vistazo a nuestro canal de reglas.",
                                "¡Genial tenerte con nosotros! Tómate un momento para leer nuestras pautas comunitarias y ponte cómodo."
                            ],
                            "priority": "high"
                        }
                    }
                }
            }
        
        try:
            # Create knowledge directory if it doesn't exist
            os.makedirs(self.knowledge_dir, exist_ok=True)
            
            # Write default guidelines to file
            with open(guidelines_path, 'w', encoding='utf-8') as f:
                json.dump(default_guidelines, f, indent=4)
                
            # Set as current guidelines
            self.default_guidelines = default_guidelines['default']
            self.channel_guidelines = default_guidelines['channels']
            
            logger.info(f"Created default {language} guidelines template at {guidelines_path}")
        except Exception as e:
            logger.error(f"Error creating default {language} guidelines: {e}")

    def reload_guidelines_for_language(self, language):
        """
        Reload guidelines when language changes.
        
        Args:
            language: The language to load guidelines for ("english" or "spanish")
        
        Returns:
            bool: Success status
        """
        if language not in self.language_files:
            logger.error(f"Unsupported language: {language}")
            return False
            
        self.load_guidelines(language)
        return self.loaded
        
    def _save_guidelines(self):
        """Save current guidelines to file."""
        # Import here to avoid circular imports
        from config.config import LANGUAGE
        
        # Determine which file to save to based on current language
        language = self.current_language or LANGUAGE
        if language not in self.language_files:
            language = "english"  # Default fallback
            
        guidelines_filename = self.language_files[language]
        guidelines_path = os.path.join(self.knowledge_dir, guidelines_filename)
        
        try:
            # Create full guidelines object
            guidelines_data = {
                "default": self.default_guidelines,
                "channels": self.channel_guidelines
            }
            
            # Create knowledge directory if it doesn't exist
            os.makedirs(self.knowledge_dir, exist_ok=True)
            
            # Write to file
            with open(guidelines_path, 'w', encoding='utf-8') as f:
                json.dump(guidelines_data, f, indent=4)
                
            logger.info(f"Successfully saved {language} intent detection guidelines to {guidelines_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving {language} guidelines: {e}")
            return False