# Homo Ludens

A personal AI game companion that learns your tastes, remembers your play history, and helps you choose the right game for the right moment.

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

Set the following environment variables:

### Steam API
- `STEAM_API_KEY` - Get from https://steamcommunity.com/dev/apikey
- `STEAM_ID` - Your Steam ID64, find at https://steamid.io

### LLM (choose one)

**OpenAI:**
- `OPENAI_API_KEY`

**Azure OpenAI:**
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT` (optional, defaults to gpt-4o-mini)

## Usage

```bash
# Sync your Steam library
homo-ludens sync

# Start chatting with your game companion
homo-ludens chat

# View library stats
homo-ludens status

# Clear all data
homo-ludens clear
```

## License

MIT
