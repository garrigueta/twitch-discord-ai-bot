import asyncio
import logging
import os
from dotenv import load_dotenv
from src.twitch_bot import TwitchBot
from src.discord_bot import DiscordBot
from config.config import TWITCH_TOKEN, DISCORD_TOKEN

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def main():
    """Main function to run both Twitch and Discord bots."""
    # Create task list
    tasks = []
    
    # Initialize and run Twitch bot if token is available
    if TWITCH_TOKEN:
        logger.info("Starting Twitch bot...")
        twitch_bot = TwitchBot()
        tasks.append(twitch_bot.start())
    else:
        logger.warning("Twitch token not found. Twitch bot will not start.")
    
    # Initialize and run Discord bot if token is available
    if DISCORD_TOKEN:
        logger.info("Starting Discord bot...")
        discord_bot = DiscordBot()
        tasks.append(discord_bot.start(DISCORD_TOKEN))
    else:
        logger.warning("Discord token not found. Discord bot will not start.")
    
    # Check if we have any bots to run
    if not tasks:
        logger.error("No bot tokens found. Please configure your .env file with bot credentials.")
        return
    
    # Run all bots concurrently
    try:
        await asyncio.gather(*tasks)
    except Exception as e:
        logger.error(f"Error running bots: {e}")
    finally:
        logger.info("Bot execution complete.")

if __name__ == "__main__":
    # Run the main async function
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")