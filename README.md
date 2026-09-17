# Value Forest Discord Bot

The Value Forest Discord Bot is built for my own server to fulfill the need of collecting discord messages across multiple servers and channels, filtered by authors, and archive them into different channels on my own server. In short, this is a message forwarding bot. You will need a server to host this bot.

## Prerequisites

- Python 3.10 or higher

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/value_forest_discord_bot.git
cd valueforest_discord
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows, use: .venv\Scripts\activate
```

3. Install the required dependencies:
```bash
pip install -r requirements.txt
```

4. Set up your configuration:
   - Copy `config.example.json` to `config.json`
   - Edit `config.json` with your specific settings
   - Shared mappings (`channels`, `users`, `webhooks`, `telegram`) live at the root
   - Each selfbot profile lives under `selfbots.<id>` with its own `self_token`, `keepalive`, `repost_settings`, and optional `llm_config`

## Running the Bot

### Supervisor (recommended)

One official Discord bot supervises all configured selfbots (keepalive handshakes, auto-restart, pull-only recovery):

```bash
source .venv/bin/activate
python run_vfbot.py
```

Or use automatic startup:

```bash
./autostart.sh
```

### Manual selfbot

Run a single selfbot without the supervisor:

```bash
python run_selfbot.py bot_1
```

History pull for a specific selfbot:

```bash
python run_selfbot_pull.py bot_1
```

## Multi-selfbot configuration

Define multiple entries under `selfbots` in `config.json`. Each selfbot needs:

- Its own `self_token`
- Its own `repost_settings`
- Its own `keepalive.handshake` with **unique** `name` and `response_webhook` (separate channel and status message IDs are recommended)

Shared at the root: `bot_token`, `channels`, `users`, `webhooks`, `test_mode`, `telegram`.

### Migration from single-bot config

Move root-level `self_token`, `keepalive`, `repost_settings`, and `llm_config` into a `selfbots` entry (e.g. `selfbots.bot_1`). Add additional selfbots as sibling entries under `selfbots`.

## License

MIT
