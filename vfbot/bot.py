import json
from concurrent.futures import ThreadPoolExecutor
import logging

from .utils import setup_logging
from .sender import MessageSender
from .receiver import MessageReceiver


VERSION: str = 'SMK-0.0.0'


class Bot:
    def __init__(self):
        setup_logging()
        self.logger = logging.getLogger(__name__)
        self.logger.info("Bot version: %s", VERSION)
    
        self.config = json.load(open('config.json'))
        self.config['channels'] = {int(k): v for k, v in self.config['channels'].items()}
        self.logger.info("Config loaded. %d channels to monitor.", len(self.config['channels']))

    def run(self):
        sender = MessageSender(config=self.config)
        receiver = MessageReceiver(config=self.config, sender=sender)
        executor = ThreadPoolExecutor(max_workers=2)
        
        sender_future = executor.submit(sender.run, self.config['bot_token'])
        receiver_future = executor.submit(receiver.run, self.config['self_token'])

        self.logger.info("Starting bot...")
        try:
            sender_future.result()
            receiver_future.result()
        except KeyboardInterrupt:
            self.logger.info("Ctrl+C again to shut down...")
