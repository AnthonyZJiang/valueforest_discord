import json
import logging
logger = logging.getLogger(__name__)


def pop_from_checklist(checklist: list[str], item: str) -> None:
    try:
        checklist.pop(checklist.index(item))
    except ValueError:
        pass


class VFConfig:
    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self._test_mode = self.config.get('test_mode', {"enabled": False})
        self.self_token = self.config['self_token']
        self.bot_token = self.config['bot_token']
        self.repost_settings = {}
        self.construct_repost_settings()
        self.channel_list = list(self.repost_settings.keys())
        
    def construct_repost_settings(self):
        def set_author_config(channel_config: list[str], author_mapping: dict, author_names_checklist: list[str]) -> dict:
            if not (authors:=channel_config.get('authors', None)):
                return None
            authors_config = {}
            for author in authors:
                if not (author_config := author_mapping.get(author, None)):
                    logger.error(f"Author {author} not found in users list.")
                    continue
                authors_config[int(author_config['id'])] = author_config
                pop_from_checklist(author_names_checklist, author)
            channel_config['authors'] = authors_config
        
        def set_channel_config(channel_config: list[str], channel_mapping: dict, channel_names_checklist: list[str]) -> dict:
            if self._test_mode['enabled']:
                channel_config['target_channel'] = channel_mapping.get(self._test_mode['target_channel'], [])
                return
            if not (target_channel_name:=channel_config.get('target_channel', None)):
                return
            if not isinstance(target_channel_name, list):
                target_channel_name = [target_channel_name]
            channel_config['target_channel'] = []
            for channel_name in target_channel_name:
                channel_id = channel_mapping.get(channel_name, None)
                if not channel_id:
                    logger.error(f"Channel {channel_name} not found in channels list.")
                    continue
                channel_config['target_channel'].append(channel_id)
            pop_from_checklist(channel_names_checklist, target_channel_name)
        
        def set_webhook_config(channel_config: list[str], webhook_mapping: dict, webhook_names_checklist: list[str]) -> dict:
            if self._test_mode['enabled']:
                channel_config['webhook'] = webhook_mapping.get(self._test_mode['webhook'], [])
                return
            if not (target_webhook_name:=channel_config.get('webhook', None)):
                return
            if not isinstance(target_webhook_name, list):
                target_webhook_name = [target_webhook_name]
            channel_config['webhook'] = []
            for webhook_name in target_webhook_name:
                webhook_id = webhook_mapping.get(webhook_name, None)
                if not webhook_id:
                    logger.error(f"Webhook {webhook_name} not found in webhooks list.")
                    continue
                channel_config['webhook'].append(webhook_id)
            pop_from_checklist(webhook_names_checklist, target_webhook_name)
        
        channel_mapping = self.config['channels'] # type: dict[str, str]
        author_mapping = self.config['users'] # type: dict[str, dict]
        webhook_mapping = self.config.get('webhooks', {}) # type: dict[str, str]
        channel_names_checklist = list(channel_mapping.keys())
        author_names_checklist = list(author_mapping.keys())
        webhook_names_checklist = list(webhook_mapping.keys())
        
        for k, channel_configs in self.config['repost_settings'].items():
            if not (id := channel_mapping.get(k, None)):
                logger.error(f"Channel {k} not found in channels list, ignored")
                continue
            for c_config in channel_configs:
                set_author_config(c_config, author_mapping, author_names_checklist)
                set_channel_config(c_config, channel_mapping, channel_names_checklist)
                set_webhook_config(c_config, webhook_mapping, webhook_names_checklist)

            self.repost_settings[int(id)] = channel_configs
            pop_from_checklist(channel_names_checklist, k)
        
        if self._test_mode['enabled']:
            return
        if len(channel_names_checklist) > 0:
            logger.warning(f"The following channels are not used: {channel_names_checklist}")
        if len(author_names_checklist) > 0:
            logger.warning(f"The following authors are not used: {author_names_checklist}")
        if len(webhook_names_checklist) > 0:
            logger.warning(f"The following webhooks are not used: {webhook_names_checklist}")

    def get(self, key, default=None):
        return self.repost_settings.get(key, default)
    
    def keys(self):
        return self.repost_settings.keys()
    
    def values(self):
        return self.repost_settings.values()
    
    def items(self):
        return self.repost_settings.items()
