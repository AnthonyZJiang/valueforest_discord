import dotenv
import os
import sys
from datetime import datetime

from vfbot import selfbot, setup_logging, VFConfig

if len(sys.argv) < 2:
    print("Usage: python run_selfbot_pull.py <selfbot_id>")
    sys.exit(1)

selfbot_id = sys.argv[1]

dotenv.load_dotenv()
log_file = os.path.join(".log", f"selfbot_{selfbot_id}.log")
stream_handler, library = setup_logging(log_file)

config = VFConfig("config.json", selfbot_id=selfbot_id)
bot = selfbot.Selfbot(config)
bot.forward_history_only = True
bot.forward_history_since = datetime.strptime('2025-11-26 16:05:35', '%Y-%m-%d %H:%M:%S')
# bot.forward_history_from_channels = []
bot.run(token=config.self_token, log_handler=stream_handler)
