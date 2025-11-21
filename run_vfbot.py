from vfbot import KeepAliveBot, VFConfig, setup_logging
import dotenv
import os
import logging

VERSION: str = 'SMK-2.4.0'

dotenv.load_dotenv()

AUTO_RESUME_TIMEOUT = int(os.getenv('AUTO_RESUME_TIMEOUT', 10))
CONFIG_FILE_HOST = os.getenv('CONFIG_FILE_HOST')

stream_handler = setup_logging(os.getenv('LOG_FILE'))
logger = logging.getLogger(__name__)


if CONFIG_FILE_HOST:
    temp_file = 'config.json.temp'
    success = False
    if CONFIG_FILE_HOST == 'gdrive':
        GDRIVE_CONFIG_UID = os.getenv('GDRIVE_CONFIG_UID')
        if not GDRIVE_CONFIG_UID:
            logger.error("GDRIVE_CONFIG_UID is not set")
        else:
            import urllib.request
            logger.info(f"Downloading config file from Google Drive...")
            file, _ = urllib.request.urlretrieve(url=f"https://drive.google.com/uc?id={GDRIVE_CONFIG_UID}", filename=temp_file)
            if os.path.exists(file) and os.path.getsize(file) > 0:
                os.rename(file, 'config.json')
                success = True
    if success:
        logger.info(f"Config file downloaded from host '{CONFIG_FILE_HOST}'")
    else:
        logger.error(f"Failed to download config file from host '{CONFIG_FILE_HOST}'")

config = VFConfig('config.json', keepalive_only=True)
bot = KeepAliveBot(config)
bot.run(token=config.bot_token, log_handler=stream_handler)