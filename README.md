# Twitch and Discord Bot with Ollama AI Integration

This project implements a dual-platform bot for both Twitch and Discord with AI capabilities powered by a local Ollama instance. The bot can automatically respond to messages, execute commands, and leverage AI to provide context-aware responses.

## Features

- **Multi-Platform Support**: Runs on both Twitch and Discord simultaneously
- **Command System**: Includes basic commands like help, ping, and ai
- **AI Integration**: Uses your local Ollama instance for generating responses
- **Multiple AI Personas**: Choose from different AI personalities to suit various contexts
- **Model Context Protocol (MCP)**: Access external data sources like racing information through a unified protocol
- **Knowledge Management**: Add custom knowledge files to enhance the bot's information base
- **Enhanced Context Awareness**: Bot remembers conversations and channel context for more relevant responses
- **Intelligent Interaction**: 
  - Responds when directly addressed with a trigger phrase
  - Can randomly respond to messages based on configured probability
  - Analyzes messages to determine if they require a response
- **Conversation Tracking**: Maintains conversation history for more contextual responses
- **Cross-Channel User Recognition**: Remembers users across different channels and platforms

## Prerequisites

- Python 3.9+
- A Twitch developer account and application (for Twitch bot)
- A Discord application and bot (for Discord bot)
- Ollama installed and running locally

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/twitch-discord-ai-bot.git
   cd twitch-discord-ai-bot
   ```

2. Install required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project root with your configuration:
   ```
   # Twitch Configuration
   TWITCH_TOKEN=your_twitch_oauth_token
   TWITCH_CLIENT_ID=your_twitch_client_id
   TWITCH_CLIENT_SECRET=your_twitch_client_secret
   TWITCH_CHANNEL=your_twitch_channel_name

   # Discord Configuration
   DISCORD_TOKEN=your_discord_bot_token
   DISCORD_GUILD=your_discord_server_name
   DISCORD_CHANNELS=general,bot-chat

   # Ollama Configuration
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=llama2  # or any other model you have in Ollama

   # Enhanced AI Configuration
   DEFAULT_PERSONA=default
   MEMORY_SIZE=10
   CHANNEL_CONTEXT_ENABLED=True
   GLOBAL_CONTEXT_SIZE=5

   # Bot Configuration
   BOT_PREFIX=!
   ENABLE_AI_RESPONSE=True
   AI_TRIGGER_PHRASE=@bot
   AI_RESPONSE_PROBABILITY=0.1
   ```

## Usage

1. Make sure your Ollama instance is running:
   ```
   ollama run llama2  # or whatever model you want to use
   ```

2. Start the bot:
   ```
   python main.py
   ```

3. The bot will connect to both Twitch and Discord (if configured) and start responding to messages.

### Available Commands

#### Basic Commands
- `!help` - Show available commands
- `!ping` - Check if the bot is online
- `!ai <message>` - Ask the AI a direct question

#### Persona Commands
- `!persona <name>` - Switch the bot's active personality (default, streamer, expert, comedian, motivator)
- `!personas` - List all available AI personas with descriptions
- `!ask <persona> <message>` - Ask a question to a specific persona without changing the current one

#### Language Commands
- `!language <language>` - Change the bot's language (english, spanish, etc.)
- `!languages` - List all available languages

#### Knowledge Management Commands
- `!knowledge list` - List all available knowledge files
- `!knowledge activate <name>` - Activate a knowledge file for AI to use
- `!knowledge deactivate <name>` - Deactivate a knowledge file
- `!knowledge status` - Show active knowledge files
- `!knowledges` - List all available knowledge files

#### Model Context Protocol (MCP) Commands
- `!racing <query>` - Query racing data from Garage61 API (teams, tracks, statistics, etc.)
- `!mcp` - Get information about available data providers

### AI Personas

The bot comes with several pre-configured AI personas that can be selected:

- **default** - A helpful assistant that provides balanced and informative responses
- **streamer** - A charismatic and entertaining personality with energetic responses
- **expert** - A knowledgeable professional that provides detailed and accurate information
- **comedian** - A witty and humorous character that focuses on being funny
- **motivator** - An inspirational guide providing encouraging and supportive messages

### Interacting with the AI

There are multiple ways to get AI responses:

1. Direct command: `!ai What's the weather like?`
2. Mention trigger: `Hey @bot, what's the weather like?`
3. Random chance: The bot has a configurable chance to respond to any message
4. Persona-specific: `!ask comedian Tell me a joke about programming`

## Enhanced Context Awareness

The bot now uses several sources of context to provide more relevant responses:

- **Conversation History**: Remembers the conversation with each user
- **Channel Context**: Aware of recent messages in the channel for better contextual responses
- **Global Memory**: Tracks users across different channels and platforms
- **Time Awareness**: Includes current time information in AI prompts
- **External Data Sources**: Queries MCP providers for domain-specific information

## Model Context Protocol (MCP)

The Model Context Protocol (MCP) enables the bot to access external data sources and inject relevant context into AI responses:

### Key Features
- **Extensible Provider Framework**: Add new data sources through a simple interface
- **Query Routing**: Automatically routes queries to appropriate data providers
- **Context Enrichment**: Enhances AI responses with real-time data
- **Direct Command Access**: Query specific data sources directly with commands

### Available Providers
- **Garage61**: Racing data including teams, drivers, tracks, cars, lap data, and statistics

### Custom Providers
You can add your own MCP providers by creating a new class that inherits from `MCPProvider` in the `src/mcp` directory. See the Garage61 provider for an example implementation.

## Knowledge Management

The bot can use custom knowledge files to enhance its responses:

- Create `.txt`, `.md`, or `.json` files in the `knowledge` directory
- Activate knowledge files with `!knowledge activate <name>`
- The bot will use the information when responding to relevant questions
- View active and available knowledge files with `!knowledge status` and `!knowledge list`

## Architecture

- `main.py`: Entry point that starts both bots concurrently
- `src/twitch_bot.py`: Implementation of the Twitch bot
- `src/discord_bot.py`: Implementation of the Discord bot
- `src/ollama_integration.py`: Integration with Ollama for AI capabilities
- `src/mcp/`: Model Context Protocol implementation
  - `base.py`: Core MCP framework and provider interface
  - `garage61.py`: Garage61 API provider for racing data
- `config/config.py`: Configuration loading and management
- `utils/message_handler.py`: Shared message handling logic
- `knowledge/`: Directory for custom knowledge files

## Getting API Keys

### Twitch
1. Go to the [Twitch Developer Console](https://dev.twitch.tv/console/apps)
2. Register a new application
3. Generate a client secret
4. Use an OAuth generator to get a token with the required scopes (`chat:read`, `chat:edit`)

### Discord
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Add a bot to the application
4. Under the "Bot" tab, generate a token
5. Enable necessary intents (Message Content, Server Members)
6. Use the OAuth2 URL generator to invite the bot to your server

## Customization

You can customize the bot's behavior by modifying:

- The configuration settings in `.env`
- The message handling logic in `utils/message_handler.py`
- System prompts and AI personas in `config/config.py`
- Adding new commands to both bot implementations

### Customizing AI Personas

You can modify existing personas or add new ones by editing the `AI_PERSONAS` dictionary in `config/config.py`. Each persona consists of a name and a system prompt that guides the AI's behavior and tone.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
