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
   - Remember to delete all comments

## Running the Bot

### Manual Start
To start the bot manually, run:
```bash
source .venv/bin/activate
python run_bot.py
```

### Automatic Start
For automatic startup, use the provided script:
```bash
./autostart.sh
```

### Arguments
You may pass 'pull_since=' argument to pull history messages up to the defined date.

The date can be defined as `%YYYY%M%D %H%m%S` or as a time delta `-6d3h2m1s` (You may omit any component e.g. `-3h` will also work).

## License

MIT
