"""
Action Layer Module
~~~~~~~~~~~~~~~~~~~~

The action layer is responsible for:
- Start the bot
- Kill and restart the bot
"""

from __future__ import annotations
from typing import TYPE_CHECKING
import logging
import subprocess
import asyncio
import threading
import time
from datetime import datetime
import os

if TYPE_CHECKING:
    from ...keepalivebot import KeepAliveBot

# ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# RUN_SELF_BOT_SCRIPT = os.path.join(ROOT_DIR, 'run_selfbot.py')

RUN_SELF_BOT_SCRIPT = """
import dotenv
import os

from vfbot import selfbot, setup_logging, VFConfig

dotenv.load_dotenv()
stream_handler, _ = setup_logging(os.path.join('.log', 'selfbot.log'))

config = VFConfig('config.json')
bot = selfbot.Selfbot(config)
bot.run(token=config.self_token, log_handler=stream_handler)
"""

def get_pull_only_script(pull_since: datetime, pull_until: datetime):
    return f"""
import dotenv
import os

from vfbot import selfbot, setup_logging, VFConfig

dotenv.load_dotenv()
stream_handler, _ = setup_logging(os.path.join('.log', 'selfbot.log'))

config = VFConfig('config.json')
bot = selfbot.Selfbot(config)
bot.forward_history_only = True
bot.forward_history_since = '{pull_since.isoformat()}'
bot.forward_history_before = '{pull_until.isoformat()}'
bot.run(token=config.self_token, log_handler=stream_handler)
"""


logger = logging.getLogger(__name__)

SELFBOT_READY_TIMEOUT = 15
PULL_ONLY_READY_TIMEOUT = 60*10 # 10 minutes


class ActionLayer:
    def __init__(self, client: KeepAliveBot):
        self._client = client
        
        self.selfbot_ready = False

        self._bot_process = None
        self._check_bot_readiness_thread = None
        self._kill_requested = False
        
        self._selfbot_start_time = None
        self._selfbot_timeout = False
        
        self._bot_script = RUN_SELF_BOT_SCRIPT
        self._bot_ready_string = "Selfbot ready"
        self._timeout = SELFBOT_READY_TIMEOUT
        
    def __del__(self):
        self.kill_bot()
        
    @property
    def selfbot_start_timeout(self) -> bool:
        if self.selfbot_ready:
            return False # bot is ready so not timeout, handover to handshake to check if still alive
        if not self._selfbot_start_time:
            return False # not started yet
        return time.perf_counter() - self._selfbot_start_time > self._timeout
        
    def start_bot(self):
        # run python3 start_selfbot.py
        self._kill_requested = False
        self._bot_process = subprocess.Popen(
            ['python3', '-u', '-c', self._bot_script],
            bufsize=1,
            stdout=subprocess.PIPE,
            universal_newlines=True
            )
        os.set_blocking(self._bot_process.stdout.fileno(), False)
        self._check_bot_readiness_thread = threading.Thread(target=self._check_bot_readiness)
        self._check_bot_readiness_thread.start()
        self._selfbot_start_time = time.perf_counter()
    
    def kill_bot(self):
        if not self._bot_process:
            return
        self._kill_requested = True
        if self._check_bot_readiness_thread and self._check_bot_readiness_thread.is_alive():
            self._check_bot_readiness_thread.join(timeout=1)
        try:
            self._bot_process.kill()
        except Exception as e:
            logger.error(f"Error killing bot: {e}", exc_info=True)
        self.selfbot_ready = False
        self._selfbot_start_time = None
        self._bot_process = None
    
    def restart_bot(self):
        self.kill_bot()
        self.start_bot()
        
    async def wait_for_selfbot_ready(self):
        while not self.selfbot_ready:
            await asyncio.sleep(0.1)
            
    def _check_bot_readiness(self):
        while not self._kill_requested:
            if self._bot_process is None:
                return
            try:
                output = self._bot_process.stdout.readline()
                if output:
                    if not self.selfbot_ready and self._bot_ready_string in output:
                        self.selfbot_ready = True
                        return
                time.sleep(1)
            except subprocess.TimeoutExpired:
                continue
            except Exception as e:
                logger.error(f"Error reading bot stdout: {e}", exc_info=True)
                continue
            time.sleep(0.1)


class PullOnlyActionLayer(ActionLayer):
    
    def __init__(self, client: KeepAliveBot):
        super().__init__(client)
        self._bot_ready_string = "Selfbot pull only completed"
        self._timeout = PULL_ONLY_READY_TIMEOUT
        
    def start_bot(self, pull_since: datetime):
        self._bot_script = get_pull_only_script(pull_since, datetime.now())
        super().start_bot()
    