import dotenv
import os
import sys

from vfbot import selfbot, setup_logging, VFConfig

if len(sys.argv) < 2:
    print("Usage: python run_selfbot.py <selfbot_id>")
    sys.exit(1)

selfbot_id = sys.argv[1]

dotenv.load_dotenv()
log_file = os.path.join(".log", f"selfbot_{selfbot_id}.log")
stream_handler, library = setup_logging(log_file)

config = VFConfig("config.json", selfbot_id=selfbot_id)
bot = selfbot.Selfbot(config)
bot.run(token=config.self_token, log_handler=stream_handler)
