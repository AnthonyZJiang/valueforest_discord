from vfbot import KeepAliveBot, VFConfig, setup_logging
import dotenv

dotenv.load_dotenv()
stream_handler = setup_logging()

config = VFConfig('config.json', keepalive_only=True)
bot = KeepAliveBot(config)
bot.run(token=config.bot_token, log_handler=stream_handler)