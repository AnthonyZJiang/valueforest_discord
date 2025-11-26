import dotenv
import os

from vfbot import selfbot, setup_logging, VFConfig

dotenv.load_dotenv()
stream_handler, library = setup_logging(os.path.join('.log', 'selbot.log'))

config = VFConfig('config.json')
bot = selfbot.Selfbot(config)
bot.run(token=config.self_token, log_handler=stream_handler)