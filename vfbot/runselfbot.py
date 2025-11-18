from concurrent.futures import ThreadPoolExecutor
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from threading import Thread
import asyncio
import random
import dotenv
import os

from .utils import setup_logging
from .sender import MessageSender
from .receiver import MessageReceiver
from .vfconfig import VFConfig
from .keepaliveagent import KeepAliveAgent


dotenv.load_dotenv()

VERSION: str = 'SMK-2.4.0'
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


def print_help():
    """Print comprehensive help information for all available arguments"""
    help_text = f"""
Value Forest Discord Bot v{VERSION} - Command Line Arguments

USAGE:
    python run_bot.py [ARGUMENT=VALUE] [ARGUMENT=VALUE] ...
    python run_bot.py help                    # Show this help message
    python run_bot.py --help                  # Show this help message
    python run_bot.py -h                      # Show this help message

AVAILABLE ARGUMENTS:

    pull_since=TIME
        Start forwarding messages from this time onwards.
        
        TIME formats:
        - Relative time: -XdYhZmWs (e.g., -1d2h3m4s for 1 day, 2 hours, 3 minutes, 4 seconds ago)
        - Absolute time: YYYY-MM-DD HH:MM:SS (e.g., 2024-01-15 14:30:00)
        
        Examples:
        - pull_since=-1d          # Messages from 1 day ago
        - pull_since=-2h30m       # Messages from 2 hours 30 minutes ago
        - pull_since=2024-01-15 14:30:00  # Messages from specific date/time

    pull_until=TIME
        Stop forwarding messages at this time.
        
        TIME formats: Same as pull_since
        Examples:
        - pull_until=-1h          # Messages until 1 hour ago
        - pull_until=2024-01-16 00:00:00  # Messages until specific date/time

    pull_channels=CHANNEL_LIST
        Comma-separated list of channel IDs to pull messages from.
        
        Examples:
        - pull_channels=moonmarket_ace_education
        - pull_channels=moonmarket_ace_education,moonmarket_ace_alerts

    pull_only=BOOLEAN
        If true, only pull historical messages without starting the live bot.
        
        Examples:
        - pull_only=1

EXAMPLES:

1. Pull messages from the last 24 hours:
   python run_bot.py pull_since=-1d

2. Pull messages from specific channels in the last 2 hours:
   python run_bot.py pull_since=-2h pull_channels=123456789,987654321

3. Pull messages between specific dates:
   python run_bot.py pull_since=2024-01-15 00:00:00 pull_until=2024-01-16 00:00:00

4. Pull-only mode (no live bot):
   python run_bot.py pull_since=-1d pull_only=true

5. Pull from specific channels in the last 30 minutes:
   python run_bot.py pull_since=-30m pull_channels=123456789

NOTES:
- All times are in UTC
- Relative time format: -XdYhZmWs where X=days, Y=hours, Z=minutes, W=seconds
- Channel IDs can be found by right-clicking on a Discord channel and selecting "Copy ID"
- If no arguments are provided, the bot runs normally in live mode
- Configuration is loaded from 'config.json' in the same directory
- The bot automatically monitors all channels specified in the configuration file
"""
    print(help_text)

def parse_date_arg(arg: str) -> datetime:
    """
    Parse a relative time argument in the format '-XdYhZmWs' where:
    - X is days (optional)
    - Y is hours (optional)
    - Z is minutes (optional)
    - W is seconds (optional)
    Example: '-1d2h3m4s' means 1 day, 2 hours, 3 minutes, and 4 seconds ago
    """
    if not arg.startswith('-'):
        try:
            return datetime.strptime(arg, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            logger.warning(f"Invalid date format: {arg}")
            return None
    
    days, hours, minutes, seconds = 0, 0, 0, 0
    
    pattern = r'(\d+)d|(\d+)h|(\d+)m|(\d+)s'
    matches = re.finditer(pattern, arg[1:])
    
    for match in matches:
        if match.group(1):
            days = int(match.group(1))
        elif match.group(2):
            hours = int(match.group(2))
        elif match.group(3):
            minutes = int(match.group(3))
        elif match.group(4): 
            seconds = int(match.group(4))
    
    return datetime.now(timezone.utc) - timedelta(
        days=days,
        hours=hours,
        minutes=minutes,
        seconds=seconds
    )


class Bot:
    def __init__(self, debug: bool = False):
        self.pull_since = None
        self.pull_until = None
        self.pull_channels = None
        self.pull_only = False
        
        self.sender = None
        self.receiver = None
        self.keep_alive_agent = None
        self.executor = None
        self.do_report_online = True
        logger.info("Bot version: %s", VERSION)
    
        self.config = VFConfig('config.json', debug=debug)
        logger.info("Config loaded. Version: %s.\n%d channels to monitor.", 
                    self.config.config['config_version'], 
                    len(self.config.channel_list))
        
    @property
    def do_report_status(self):
        return not self.config._test_mode['enabled'] and not self.pull_only
    
    def show_help(self):
        """Display help information for the bot"""
        print_help()
    
    def run(self, **kwargs):
        # Check for help argument first
        if 'help' in kwargs or 'h' in kwargs:
            print_help()
            return
        
        # Validate and process arguments
        self._validate_arguments(kwargs)
        
        if 'pull_since' in kwargs:
            date = parse_date_arg(kwargs['pull_since'])
            if date:
                logger.info("Forwarding history messages since %s", date)
                self.pull_since = date
            else:
                logger.error("Invalid pull_since date format: %s", kwargs['pull_since'])
                logger.info("Use 'help' for date format examples")
                return
        
        if 'pull_until' in kwargs:
            date = parse_date_arg(kwargs['pull_until'])
            if date:
                logger.info("Forwarding history messages until %s", date)
                self.pull_until = date
            else:
                logger.error("Invalid pull_until date format: %s", kwargs['pull_until'])
                logger.info("Use 'help' for date format examples")
                return
        
        if 'pull_channels' in kwargs:
            self.pull_channels = kwargs['pull_channels'].split(',')
            logger.info("Pull history messages from channels: %s", self.pull_channels)
        
        if 'pull_only' in kwargs:
            self.pull_only = kwargs['pull_only'].lower() in ['true', '1', 'yes', 'on']
            logger.info("Pull history messages only: %s", self.pull_only)
        
        self.discord_thread = Thread(target=self.start_discord)
        self.discord_thread.start()
        self.start_monitor()
    
    def _validate_arguments(self, kwargs):
        """Validate command line arguments and provide helpful error messages"""
        valid_args = {'pull_since', 'pull_until', 'pull_channels', 'pull_only', 'help', 'h', 'debug'}
        invalid_args = set(kwargs.keys()) - valid_args
        
        if invalid_args:
            logger.warning("Unknown arguments: %s", ', '.join(invalid_args))
            logger.info("Use 'help' to see all available arguments")
        
        # Validate pull_only is a boolean if provided
        if 'pull_only' in kwargs:
            value = kwargs['pull_only'].lower()
            if value not in ['true', 'false', '1', '0', 'yes', 'no', 'on', 'off']:
                logger.warning("pull_only should be a boolean value (true/false, 1/0, yes/no, on/off)")
                logger.info("Defaulting to false")
                kwargs['pull_only'] = 'false'
            
    def start_monitor(self):
        r = random.Random(1)
        def wait_for_discord():
            while True:
                if self.keep_alive_agent and self.keep_alive_agent.bot_ready and self.keep_alive_agent.ready:
                    if self.do_report_online and self.do_report_status:
                        self.keep_alive_agent.report_online(r.random())
                        self.do_report_online = False
                    break
                time.sleep(1)
        
        def wait_for_resume():
            resume_timer = time.time()
            logger.warning("Discord bot is offline, waiting for it to auto-resume...")
            while True:
                if time.time() - resume_timer > AUTO_RESUME_TIMEOUT:
                    logger.warning("Auto-resume timeout, restarting...")
                    if self.do_report_status:
                        self.keep_alive_agent.report_offline(r.random())
                        self.do_report_online = True
                    self.restart_discord_thread()
                    logger.info("Waiting for discord bots to start...")
                    time.sleep(5)
                    return
                if self.keep_alive_agent.receiver_ok:
                    logger.info("Discord reconnected.")
                    return
                time.sleep(1)
        
        logger_interval = 30
        logger_count = 1
        while True:
            try:
                wait_for_discord()
                if not self.keep_alive_agent.receiver_ok:
                    wait_for_resume()
            except KeyboardInterrupt:
                logger.info("Ctrl+C again to shut down...")
                return
            except Exception as e:
                logger.error("Error in monitor thread: %s", e, exc_info=True)
                time.sleep(1)
            time.sleep(1)
            logger_count += 1
            if logger_count == logger_interval:
                logger.debug(f"Has been good for {logger_count} seconds...")
                logger_count = 1
            
    def restart_discord_thread(self):
        self.close()
        self.discord_thread.join(timeout=5)
        if self.discord_thread.is_alive():
            logger.warning("Discord thread is still alive...")
        self.discord_thread = Thread(target=self.start_discord)
        self.discord_thread.start()
        logger.info("Discord thread restart requested.")
    
    def close(self):
        asyncio.run_coroutine_threadsafe(self.keep_alive_agent.close(), self.sender.loop)
        logger.info("Closing sender...")
        asyncio.run_coroutine_threadsafe(self.sender.close(), self.sender.loop)
        logger.info("Closing receiver...")
        asyncio.run_coroutine_threadsafe(self.receiver.close(), self.receiver.loop)
        self.receiver_future.cancel()
        self.sender_future.cancel()
        
    def start_discord(self):
        logger.info("> Building discord bots...")
        self.sender = MessageSender()
        self.receiver = MessageReceiver(config=self.config, sender=self.sender)
        self.keep_alive_agent = KeepAliveAgent(sender=self.sender, receiver=self.receiver)
        
        self.receiver.forward_history_since = self.pull_since
        self.receiver.forward_history_before = self.pull_until
        self.receiver.forward_history_only = self.pull_only
        self.receiver.forward_history_from_channels = self.pull_channels
        self.pull_since = None
        self.pull_until = None
        self.pull_channels = None
        
        with ThreadPoolExecutor(max_workers=2) as executor:
        
            self.sender_future = executor.submit(self.sender.run, self.config.bot_token, log_handler=stream_handler)
            self.receiver_future = executor.submit(self.receiver.run, self.config.self_token, log_handler=stream_handler)
            
            logger.info("> Commissioning discord bots...")
            try:
                # Wait for sender to be ready before scheduling keep-alive agent
                if not self.pull_only:
                    while not self.sender.is_ready():
                        time.sleep(0.1)
                    asyncio.run_coroutine_threadsafe(self.keep_alive_agent.start(), self.sender.loop)
                
                self.sender_future.result()
                logger.info("Sender is closed.")
                self.receiver_future.result()
                logger.info("Receiver is closed.")
            except KeyboardInterrupt:
                logger.info("Ctrl+C again to shut down...")
            except asyncio.CancelledError:
                logger.error("Bot cancelled.")
                pass
