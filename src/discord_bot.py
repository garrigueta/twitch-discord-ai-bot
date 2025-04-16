import logging
import discord
from discord.ext import commands
import traceback
import sys
from config.config import (
    DISCORD_TOKEN,
    DISCORD_GUILD,
    BOT_PREFIX,
    AI_TRIGGER_PHRASE
)
from utils.message_handler import MessageHandler

logger = logging.getLogger(__name__)

class DiscordBot(commands.Bot):
    def __init__(self):
        # Initialize message handler
        self.message_handler = MessageHandler()
        
        # Initialize Discord.py bot with all intents
        intents = discord.Intents.default()
        intents.message_content = True  # Explicitly enable message content intent
        intents.guilds = True
        intents.guild_messages = True
        intents.members = True
        
        logger.info("Initializing Discord bot with prefix '%s' and AI trigger '%s'", 
                   BOT_PREFIX, AI_TRIGGER_PHRASE)
        
        super().__init__(
            command_prefix=BOT_PREFIX,
            intents=intents,
            help_command=None  # Disable default help command
        )
        
        # Add error handler
        self.on_command_error = self.handle_command_error
        
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
    
    async def handle_command_error(self, ctx, error):
        """Handle command errors and log them."""
        logger.error("Command error: %s", error)
        logger.error(''.join(traceback.format_exception(type(error), error, error.__traceback__)))
        await ctx.send(f"Error al ejecutar el comando: {error}")
    
    async def setup_hook(self):
        """Called when the bot is setting up."""
        logger.info("Bot setup hook running...")
        # Log that we're listening for events
        logger.info("Event listeners are now registered and active")
        
    async def on_ready(self):
        """Event triggered when the bot is connected and ready."""
        logger.info("Discord Bot is connected as %s (ID: %s)", self.user.name, self.user.id)
        
        # Set bot activity status
        await self.change_presence(activity=discord.Activity(
            type=discord.ActivityType.listening,
            name=f"{BOT_PREFIX}help"
        ))
        
        # Log connected guilds
        guild_names = [guild.name for guild in self.guilds]
        logger.info("Connected to %d guilds: %s", len(guild_names), ', '.join(guild_names))
        
        # Log channels the bot can see
        for guild in self.guilds:
            logger.info("Guild: %s (ID: %s)", guild.name, guild.id)
            text_channels = [channel for channel in guild.channels if isinstance(channel, discord.TextChannel)]
            logger.info("Text channels in %s: %s", guild.name, 
                       ', '.join([f"#{channel.name} (ID: {channel.id})" for channel in text_channels]))
            
            # Check for channels where the bot has permission to send messages
            authorized_channels = []
            for channel in text_channels:
                permissions = channel.permissions_for(guild.me)
                if permissions.send_messages:
                    authorized_channels.append(channel)
                    logger.info("Bot has permission to send messages in #%s", channel.name)
                else:
                    logger.warning("Bot lacks permission to send messages in #%s", channel.name)
            
            # No longer sending test messages when bot connects
            if not authorized_channels:
                logger.warning("Bot doesn't have permission to send messages in any channel in %s", guild.name)
                logger.warning("Please update the bot's permissions in the Discord server settings")
        
    async def on_message(self, message):
        """Event triggered for every message in channels the bot can see."""
        try:
            # More detailed logging for received messages
            channel_name = getattr(message.channel, 'name', 'DM')
            logger.info("RECEIVED MESSAGE: Author: %s, Channel: #%s, Content: '%s'", 
                       message.author.name, channel_name, message.content)
            
            # Ignore messages from the bot itself
            if message.author == self.user:
                logger.info("Ignoring message from self")
                return
            
            # Check if this is a direct message (DM)
            is_dm = isinstance(message.channel, discord.DMChannel)
            
            # For guild messages, check if bot has permission to send messages
            if not is_dm:
                permissions = message.channel.permissions_for(message.guild.me)
                if not permissions.send_messages:
                    logger.warning("Received message in #%s but bot lacks permission to respond", channel_name)
                    return
            
            # Process commands first
            ctx = await self.get_context(message)
            if ctx.valid:
                logger.info("Processing as command: %s", message.content)
                await self.invoke(ctx)
                return
            
            # Only process non-command messages
            if not message.content.startswith(BOT_PREFIX):
                username = message.author.name
                channel_id = str(message.channel.id)
                content = message.content
                
                logger.info("Processing non-command message from %s in #%s", username, channel_name)
                
                # Process the message through the message handler
                if len(content.strip()) > 0:
                    logger.info("Handling message: '%s'", content)
                    
                    # Use streaming response instead of waiting for the full response
                    typing_status = False
                    bot_message = None
                    collected_response = ""
                    
                    # Get streaming response generator
                    async for chunk in self.message_handler.handle_ai_request_stream(
                        message=content,
                        username=username,
                        channel_id=channel_id,
                        platform="discord"
                    ):
                        # Start typing indicator if not already started
                        if not typing_status:
                            await message.channel.typing()
                            typing_status = True
                        
                        # Append the new chunk to our collected response
                        collected_response += chunk
                        
                        # If we don't have a message yet, create one
                        if not bot_message and len(collected_response) >= 10:
                            try:
                                bot_message = await message.channel.send(collected_response)
                            except discord.errors.Forbidden:
                                logger.error("Cannot send response in #%s due to permission issues", channel_name)
                                return
                            except Exception as e:
                                logger.error("Error sending initial response: %s", e)
                                return
                                
                        # If we already have a message, edit it with the updated content
                        elif bot_message and len(collected_response) >= len(bot_message.content) + 5:
                            try:
                                # Only edit if we have meaningful new content to add
                                await bot_message.edit(content=collected_response)
                            except Exception as e:
                                logger.error("Error editing response: %s", e)
                    
                    # If we collected a response but never sent it (too short)
                    if collected_response and not bot_message:
                        try:
                            await message.channel.send(collected_response)
                        except discord.errors.Forbidden:
                            logger.error("Cannot send final response in #%s due to permission issues", channel_name)
                        except Exception as e:
                            logger.error("Error sending final response: %s", e)
                            
                    logger.info("Sent streaming response with final length: %d characters", len(collected_response))
                else:
                    logger.info("Message was empty, not processing")
        except discord.errors.Forbidden as e:
            logger.error("Permission error in on_message: %s", e)
        except Exception as e:
            logger.error("Error in on_message: %s", e)
            logger.error(''.join(traceback.format_exception(type(e), e, e.__traceback__)))
            try:
                await message.channel.send("Lo siento, he encontrado un error al procesar tu mensaje.")
            except:
                pass
            
    async def on_guild_join(self, guild):
        """Log when the bot joins a new guild."""
        logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
        
    async def on_disconnect(self):
        """Log when the bot disconnects from Discord."""
        logger.warning("Bot disconnected from Discord")