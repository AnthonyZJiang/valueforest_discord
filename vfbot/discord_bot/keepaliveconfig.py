import logging
import json
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KEEPALIVE_CONFIG_FILE = os.path.join(ROOT_DIR, "keepalive.config.json")

logger = logging.getLogger(__name__)


class KeepAliveConfig:
    def __init__(self):
        try:
            self.config = json.load(open(KEEPALIVE_CONFIG_FILE))
        except FileNotFoundError:
            logger.error(f'Handshake config file {KEEPALIVE_CONFIG_FILE} not found')
            raise FileNotFoundError(f'Handshake config file {KEEPALIVE_CONFIG_FILE} not found')

        self.monitor_interval = self.config.get('monitor_interval', 15)
        self.status_message_channel_id = self.config.get('status_message_channel_id', None)
        self.status_message_id = self.config.get('status_message_id', None)
        self.handshake_name=self.config.get('handshake', {}).get('name', None)
        self.handshake_channel_id=self.config.get('handshake', {}).get('channel_id', None)
        self.handshake_interval=self.config.get('handshake', {}).get('interval', 30)
        self.handshake_response_webhook=self.config.get('handshake', {}).get('response_webhook', None)

    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
            self.config[key] = value
        self.save()
        
    def save(self):
        with open(KEEPALIVE_CONFIG_FILE, 'w') as f:
            json.dump(self.__dict__, f, indent=4)

keep_alive_config = KeepAliveConfig()