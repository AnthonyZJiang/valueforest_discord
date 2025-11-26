import dotenv
import os
from datetime import datetime

from vfbot import selfbot, setup_logging, VFConfig

dotenv.load_dotenv()
stream_handler, library = setup_logging(os.path.join('.log', 'selbot.log'))

config = VFConfig('config.json')
bot = selfbot.Selfbot(config)
bot.forward_history_only = True
bot.forward_history_since = datetime.strptime('2025-11-24 06:29:00', '%Y-%m-%d %H:%M:%S')
bot.run(token=config.self_token, log_handler=stream_handler)