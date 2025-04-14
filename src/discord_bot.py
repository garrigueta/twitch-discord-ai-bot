import logging
import discord
from discord.ext import commands
from config.config import (
    DISCORD_TOKEN,
    DISCORD_GUILD,
    BOT_PREFIX
)
from utils.message_handler import MessageHandler

logger = logging.getLogger(__name__)

class DiscordBot(commands.Bot):
    def __init__(self):
        # Initialize message handler
        self.message_handler = MessageHandler()
        
        # Initialize Discord.py bot with all intents
        intents = discord.Intents.default()
        intents.message_content = True  # Enable message content intent
        intents.members = True  # Enable members intent
        
        super().__init__(
            command_prefix=BOT_PREFIX,
            intents=intents,
            help_command=None  # Disable default help command
        )
        
        # Register commands using decorators
        @self.command(name="help")
        async def help_command(ctx):
            """Show help information"""
            response = await self.message_handler.command_help("", ctx.author.name, str(ctx.channel.id), "discord")
            await ctx.send(response)
            
        @self.command(name="ping")
        async def ping_command(ctx):
            """Check if the bot is online"""
            response = await self.message_handler.command_ping("", ctx.author.name, str(ctx.channel.id), "discord")
            await ctx.send(response)
            
        @self.command(name="ai")
        async def ai_command(ctx, *, message=""):
            """Ask the AI a question"""
            response = await self.message_handler.command_ai(message, ctx.author.name, str(ctx.channel.id), "discord")
            await ctx.send(response)
            
        @self.command(name="persona")
        async def persona_command(ctx, *, persona_name=""):
            """Change the bot's persona"""
            response = await self.message_handler.command_persona(persona_name, ctx.author.name, str(ctx.channel.id), "discord")
            await ctx.send(response)
            
        @self.command(name="personas")
        async def personas_command(ctx):
            """List available personas"""
            response = await self.message_handler.command_list_personas("", ctx.author.name, str(ctx.channel.id), "discord")
            await ctx.send(response)
            
        @self.command(name="ask")
        async def ask_command(ctx, persona_name, *, message):
            """Ask a question to a specific persona"""
            args = f"{persona_name} {message}"
            response = await self.message_handler.command_ask_as_persona(args, ctx.author.name, str(ctx.channel.id), "discord")
            await ctx.send(response)
            
        @self.command(name="language")
        async def language_command(ctx, *, language_name=""):
            """Change the bot's language"""
            response = await self.message_handler.command_language(language_name, ctx.author.name, str(ctx.channel.id), "discord")
            await ctx.send(response)
            
        @self.command(name="languages")
        async def languages_command(ctx):
            """List available languages"""
            response = await self.message_handler.command_list_languages("", ctx.author.name, str(ctx.channel.id), "discord")
            await ctx.send(response)
    
    async def on_ready(self):
        """Event triggered when the bot is connected and ready."""
        logger.info(f"Discord Bot is connected as {self.user.name} (ID: {self.user.id})")
        
        # Set bot activity status
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{BOT_PREFIX}help"
        ))
        
        # Log connected guilds
        guild_names = [guild.name for guild in self.guilds]
        logger.info(f"Connected to {len(guild_names)} guilds: {', '.join(guild_names)}")
    
    async def on_message(self, message):
        """Event triggered for every message in channels the bot can see."""
        # Ignore messages from the bot itself
        if message.author == self.user:
            return
            
        # Let the command system process commands
        await self.process_commands(message)
        
        # If it's not a command, process it through the message handler
        if not message.content.startswith(BOT_PREFIX):
            username = message.author.name
            channel_id = str(message.channel.id)
            content = message.content
            
            response = await self.message_handler.process_message(
                message=content,
                username=username,
                channel_id=channel_id,
                platform="discord"
            )
            
            # Send a response if one was generated
            if response:
                await message.channel.send(response)