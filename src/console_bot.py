"""
Console interface for interacting with the bot directly from the terminal.
"""
import asyncio
import logging
import os
import sys
import readline  # Enables command history and editing capabilities
import socket
import getpass
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from utils.message_handler import MessageHandler
from config.config import BOT_PREFIX, AI_PERSONAS, SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

class ConsoleBot:
    """A console interface for interacting with the bot directly."""
    
    def __init__(self):
        """Initialize the console bot with a message handler."""
        self.message_handler = MessageHandler()
        self.running = False
        self.console_id = "console"  # Channel ID for the console
        self.username = self._get_username()
        
        # Set up command completion
        self.commands = list(self.message_handler.commands.keys())
        self.command_completer = WordCompleter(
            [f"{BOT_PREFIX}{cmd}" for cmd in self.commands] + ["exit", "quit", "clear"],
            ignore_case=True
        )
        
        # Set up persona completion
        self.personas = list(AI_PERSONAS.keys())
        
        # Set up history file
        history_dir = os.path.join(os.path.expanduser("~"), ".bo7")
        os.makedirs(history_dir, exist_ok=True)
        self.history_file = os.path.join(history_dir, "console_history")
        
        # Initialize prompt session with history
        self.session = PromptSession(
            history=FileHistory(self.history_file),
            auto_suggest=AutoSuggestFromHistory(),
            completer=self.command_completer
        )
        
    def _get_username(self):
        """Get the username for the console session."""
        try:
            username = getpass.getuser()
            hostname = socket.gethostname()
            return f"{username}@{hostname}"
        except:
            return "console_user"
    
    async def start(self):
        """Start the console bot interface."""
        self.running = True
        
        # Print welcome message
        print("\n" + "="*70)
        print(f"Welcome to BO7 Console Interface!")
        print(f"Type commands with the prefix '{BOT_PREFIX}' or just chat with the bot.")
        print(f"Use '{BOT_PREFIX}help' to see available commands.")
        print(f"Type 'exit' or 'quit' to exit the console.")
        print("="*70 + "\n")
        
        while self.running:
            try:
                # Get user input with autocomplete and history
                user_input = await self.session.prompt_async(f"{self.username}> ")
                
                # Process special console commands
                if user_input.lower() in ["exit", "quit"]:
                    self.running = False
                    print("Exiting console...")
                    break
                elif user_input.lower() == "clear":
                    os.system("cls" if os.name == "nt" else "clear")
                    continue
                
                # Process the message and get a response
                response = await self.message_handler.process_message(
                    message=user_input,
                    username=self.username,
                    channel_id=self.console_id,
                    platform="console"
                )
                
                # Print the response if there is one
                if response:
                    print(f"\nBO7> {response}\n")
                else:
                    # No response was generated, but if it was a command it should have been handled
                    if not user_input.startswith(BOT_PREFIX):
                        # If it wasn't a command and no response was generated, tell the user
                        print(f"\nBO7> (No response generated. Try using {BOT_PREFIX}ai to ask a question directly.)\n")
                
            except KeyboardInterrupt:
                print("\nExiting console...")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in console: {e}")
                print(f"\nError: {e}\n")
                
    async def stop(self):
        """Stop the console bot."""
        self.running = False
        
# Command-line execution
if __name__ == "__main__":
    # Configure basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run the console bot
    console_bot = ConsoleBot()
    
    try:
        asyncio.run(console_bot.start())
    except KeyboardInterrupt:
        print("\nConsole bot stopped by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")