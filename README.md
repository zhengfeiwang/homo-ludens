# Homo Ludens

A personal AI game companion that learns your tastes, remembers your play history, and helps you choose the right game for the right moment.

## Features

- **Multi-platform support**: Steam, PlayStation Network, and Xbox
- **Game library sync**: Fetch owned games, playtime, achievements/trophies
- **Steam wishlist**: Track wishlist with prices and sale alerts
- **AI companion**: Chat with an AI that knows your gaming preferences
- **Web UI**: Browse your library and chat through a modern web interface
- **CLI**: Full command-line interface for all features

## Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install
pip install -e .
```

## Configuration

Configuration is stored in `~/.homo_ludens/.env`. You can set it up interactively using the `config` command or manually.

### Steam
```bash
homo-ludens config --steam
```
Or set manually:
- `STEAM_API_KEY` - Get from https://steamcommunity.com/dev/apikey
- `STEAM_ID` - Your Steam ID64, find at https://steamid.io

### PlayStation Network
```bash
homo-ludens config --psn
```
Or set manually:
- `PSN_NPSSO_TOKEN` - Get from https://ca.account.sony.com/api/v1/ssocookie (must be logged in first)

### Xbox
```bash
homo-ludens config --xbox
```
Or set manually:
- `OPENXBL_API_KEY` - Get from https://xbl.io

### LLM (choose one)

**OpenAI:**
- `OPENAI_API_KEY`

**Azure OpenAI:**
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT` (optional, defaults to gpt-4o-mini)

## Usage

### CLI Commands

```bash
# Sync game libraries
homo-ludens sync              # Sync Steam library
homo-ludens sync-psn          # Sync PlayStation library
homo-ludens sync-xbox         # Sync Xbox library

# View library status
homo-ludens status            # Overview of all platforms
homo-ludens status --steam    # Detailed Steam stats
homo-ludens status --psn      # Detailed PlayStation stats
homo-ludens status --xbox     # Detailed Xbox stats

# Chat with AI companion
homo-ludens chat

# Configuration
homo-ludens config --show     # View current config
homo-ludens config --steam    # Configure Steam
homo-ludens config --psn      # Configure PlayStation
homo-ludens config --xbox     # Configure Xbox

# Web UI
homo-ludens web               # Start web server at http://127.0.0.1:8000
homo-ludens web --port 8080   # Use different port
homo-ludens web --reload      # Auto-reload for development

# Clear data
homo-ludens clear             # Clear all stored data
```

### Chat Commands

While in the chat interface, you can use:
- `quit` or `exit` - End the conversation
- `clear` - Clear conversation history
- `/refresh` - Sync latest Steam data
- `/status` - View library stats

### Web UI

Start the web server and open http://127.0.0.1:8000 in your browser:

```bash
homo-ludens web
```

The web UI includes:
- **Dashboard** (`/`) - Overview with platform stats and recent activity
- **Library** (`/library`) - Browse games with filtering and sorting
- **Chat** (`/chat`) - AI companion interface
- **Settings** (`/settings`) - Platform configuration

## Project Structure

```
src/homo_ludens/
├── cli.py              # CLI commands
├── models/             # Data models (Game, Profile, etc.)
├── steam/              # Steam API client
├── psn/                # PlayStation Network client
├── xbox/               # Xbox/OpenXBL client
├── recommender/        # AI/LLM integration
├── storage/            # Local data persistence
└── web/                # Web UI (FastAPI + HTMX)
    ├── app.py          # FastAPI application
    ├── routes/         # Route handlers
    └── templates/      # Jinja2 templates
```

## Data Storage

All data is stored locally in `~/.homo_ludens/`:
- `profile.json` - Game library and platform connections
- `conversation.json` - Chat history
- `.env` - Configuration (API keys)

## License

MIT
