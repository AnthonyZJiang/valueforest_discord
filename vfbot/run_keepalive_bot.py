from discord_bot.keepalivebot import KeepAliveBot
from utils import setup_logging

stream_handler = setup_logging()
bot = KeepAliveBot()
bot.run(token="", log_handler=stream_handler)