from vfbot import Selfbot, DiscordBot, VFConfig, setup_logging
import dotenv
import os
import logging

VERSION: str = "SMK-3.0.1"

dotenv.load_dotenv()

AUTO_RESUME_TIMEOUT = int(os.getenv("AUTO_RESUME_TIMEOUT", "10"))
CONFIG_FILE_HOST = os.getenv("CONFIG_FILE_HOST")

stream_handler, library = setup_logging(os.getenv("LOG_FILE"))
logger = logging.getLogger(library)


if CONFIG_FILE_HOST:
    temp_file = "config.json.temp"
    success = False
    if CONFIG_FILE_HOST == "gdrive":
        GDRIVE_CONFIG_UID = os.getenv("GDRIVE_CONFIG_UID")
        if not GDRIVE_CONFIG_UID:
            logger.error("GDRIVE_CONFIG_UID is not set")
        else:
            import urllib.request

            logger.info("Downloading config file from Google Drive...")
            file, _ = urllib.request.urlretrieve(
                url=f"https://drive.google.com/uc?id={GDRIVE_CONFIG_UID}", filename=temp_file
            )
            if os.path.exists(file) and os.path.getsize(file) > 0:
                os.rename(file, "config.json")
                success = True
    if success:
        logger.info("Config file downloaded from host '%s'", CONFIG_FILE_HOST)
    else:
        logger.error("Failed to download config file from host '%s'", CONFIG_FILE_HOST)
else:
    logger.warning("No config file host provided")

logger.info("Bot version %s...", VERSION)
config = VFConfig("config.json", keepalive_only=True)

if config.keepalive.enabled:
    bot = DiscordBot(config)
    try:
        bot.run(token=config.bot_token, log_handler=stream_handler)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
        bot.stop()
    except Exception as e:
        logger.error("Error starting bot", exc_info=True)
else:
    config.read_selfbot_config()
    bot = Selfbot(config)
    try:
        bot.run(token=config.self_token, log_handler=stream_handler)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
        bot.stop()
    except Exception as e:
        logger.error("Error starting bot", exc_info=True)
