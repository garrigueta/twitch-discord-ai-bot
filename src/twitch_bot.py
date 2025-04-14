import logging
import twitchio
from twitchio.ext import commands
from config.config import (
    TWITCH_TOKEN, 
    TWITCH_CLIENT_ID,
    TWITCH_CHANNEL,
    BOT_PREFIX
)
from utils.message_handler import MessageHandler

logger = logging.getLogger(__name__)

class TwitchBot(commands.Bot):
    def __init__(self):
        # Initialize the message handler
        self.message_handler = MessageHandler()
        
        # Validate configuration
        if not TWITCH_TOKEN:
            logger.error("Twitch token not found in configuration!")
            raise ValueError("Twitch token is required")
            
        if not TWITCH_CHANNEL:
            logger.error("Twitch channel not found in configuration!")
            raise ValueError("Twitch channel is required")
        
        # Initialize the Twitch bot
        super().__init__(
            token=TWITCH_TOKEN,
            prefix=BOT_PREFIX,
            initial_channels=[TWITCH_CHANNEL],
            client_id=TWITCH_CLIENT_ID
        )
        
    async def event_ready(self):
        """Called once when the bot goes online."""
        logger.info(f"Twitch Bot is online! Username: {self.nick}")
        
    async def event_message(self, message):
        """Called for every message received from Twitch."""
        # Ignore messages from the bot itself
        if message.echo:
            return
            
        # Get message details
        username = message.author.name
        channel_id = message.channel.name
        content = message.content
        
        # Process command if it is one
        if content.startswith(BOT_PREFIX):
            await self.handle_commands(message)
            return
            
        # Process the message through the message handler
        response = await self.message_handler.process_message(
            message=content,
            username=username,
            channel_id=channel_id,
            platform="twitch"
        )
        
        # Send a response if one was generated
        if response:
            await message.channel.send(response)
            
    # Basic commands
    @commands.command(name="help")
    async def help_command(self, ctx):
        response = await self.message_handler.command_help("", ctx.author.name, ctx.channel.name, "twitch")
        await ctx.send(response)
        
    @commands.command(name="ping")
    async def ping_command(self, ctx):
        response = await self.message_handler.command_ping("", ctx.author.name, ctx.channel.name, "twitch")
        await ctx.send(response)
        
    @commands.command(name="ai")
    async def ai_command(self, ctx, *, message=""):
        response = await self.message_handler.command_ai(message, ctx.author.name, ctx.channel.name, "twitch")
        await ctx.send(response)
        
    # New persona-related commands
    @commands.command(name="persona")
    async def persona_command(self, ctx, *, persona_name=""):
        response = await self.message_handler.command_persona(persona_name, ctx.author.name, ctx.channel.name, "twitch")
        await ctx.send(response)
        
    @commands.command(name="personas")
    async def personas_command(self, ctx):
        response = await self.message_handler.command_list_personas("", ctx.author.name, ctx.channel.name, "twitch")
        await ctx.send(response)
        
    @commands.command(name="ask")
    async def ask_command(self, ctx, persona_name="", *, message=""):
        if not persona_name or not message:
            await ctx.send(f"Usage: {BOT_PREFIX}ask <persona> <message>")
            return
            
        args = f"{persona_name} {message}"
        response = await self.message_handler.command_ask_as_persona(args, ctx.author.name, ctx.channel.name, "twitch")
        await ctx.send(response)
        
    # Language commands
    @commands.command(name="language")
    async def language_command(self, ctx, *, language_name=""):
        response = await self.message_handler.command_language(language_name, ctx.author.name, ctx.channel.name, "twitch")
        await ctx.send(response)
        
    @commands.command(name="languages")
    async def languages_command(self, ctx):
        response = await self.message_handler.command_list_languages("", ctx.author.name, ctx.channel.name, "twitch")
        await ctx.send(response)