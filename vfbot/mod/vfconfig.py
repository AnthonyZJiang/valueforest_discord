import json
import logging


logger = logging.getLogger(__name__)


def pop_from_checklist(checklist: list[str], item: str) -> None:
    try:
        checklist.pop(checklist.index(item))
    except ValueError:
        pass


class KeepAliveConfig:
    def __init__(self, config: dict):
        self.status_message_channel_id = config.get("status_message_channel_id", None)
        self.status_message_id = config.get("status_message_id", None)
        self.down_time_require_pull_only_seconds = config.get("down_time_require_pull_only_seconds", 15)
        
        _config_handshake = config.get("handshake", {})
        self.handshake_name = _config_handshake.get("name", None)
        self.handshake_channel_id = _config_handshake.get("channel_id", None)
        self.handshake_interval = _config_handshake.get("interval", 30)
        self.handshake_timeout = _config_handshake.get("timeout", 65)
        self.handshake_response_webhook = _config_handshake.get("response_webhook", None)
        
class VFConfig:
    
    def __init__(self, config_path: str, debug: bool = False, keepalive_only = False):
        self.config_path = config_path
        with open(config_path, 'r') as f:
            self._config = json.load(f)
            
        self._test_mode = self._config.get('test_mode', {"enabled": False})
        if debug:
            self._test_mode['enabled'] = True
        self.self_token = self._config['self_token']
        self.bot_token = self._config['bot_token']
        self.keepalive = KeepAliveConfig(self._config.get("keepalive", {}))
        
        self.repost_settings = {}
        
        if keepalive_only:
            return
        self.construct_repost_settings()
        self.channel_list = list(self.repost_settings.keys())
        
        self.llm_config = self._config.get('llm_config', None)
        self.llm_channel = [int(i) for i in self.llm_config.keys()] if self.llm_config else []
        
    def construct_repost_settings(self):
        def set_author_config(channel_config: list[str], author_mapping: dict, author_names_checklist: list[str]) -> dict:
            if not (authors:=channel_config.get('author_filter', None)):
                return None
            authors_config = {}
            for author in authors:
                if not (author_config := author_mapping.get(author, None)):
                    logger.error(f"Author {author} not found in users list.")
                    continue
                authors_config[int(author_config['id'])] = author_config
                pop_from_checklist(author_names_checklist, author)
            channel_config['author_filter'] = authors_config

        def set_author_highlight_config(channel_config: list[str], author_mapping: dict, author_names_checklist: list[str]) -> dict:
            if not (authors:=channel_config.get('author_highlight', None)):
                return None
            authors_highlight_config = {}
            for author in authors:
                if not (author_config := author_mapping.get(author, None)):
                    logger.error(f"Author {author} not found in users list.")
                    continue
                authors_highlight_config[int(author_config['id'])] = author_config
                pop_from_checklist(author_names_checklist, author)
            channel_config['author_highlight'] = authors_highlight_config
            
        def set_role_highlight_config(channel_config: list[str]) -> dict:
            if not (roles:=channel_config.get('role_highlight', None)):
                return None
            channel_config['role_highlight'] = roles
        
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
                pop_from_checklist(channel_names_checklist, channel_name)
        
        def set_webhook_config(channel_config: list[str], webhook_mapping: dict, webhook_names_checklist: list[str]) -> dict:
            if self._test_mode['enabled']:
                channel_config['webhook'] = webhook_mapping.get(self._test_mode['webhook'], [])
                if isinstance(channel_config['webhook'], str):
                    channel_config['webhook'] = [channel_config['webhook']]
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
                pop_from_checklist(webhook_names_checklist, webhook_name)
        
        channel_mapping: dict[str, str] = self._config['channels']
        author_mapping: dict[str, dict] = self._config['users']
        webhook_mapping: dict[str, str] = self._config.get('webhooks', {})
        channel_names_checklist = list[str](channel_mapping.keys())
        author_names_checklist = list[str](author_mapping.keys())
        webhook_names_checklist = list[str](webhook_mapping.keys())
        
        for k, channel_configs in self._config['repost_settings'].items():
            if not (id := channel_mapping.get(k, None)):
                logger.error(f"Channel {k} not found in channels list, ignored")
                continue
            this_channel_configs = []
            for c_config in channel_configs:
                if not c_config.get('enabled', True):
                    continue
                if self._test_mode['enabled'] and self._test_mode['flagged_only'] and not c_config.get('flag_test_mode', False):
                    continue
                set_author_config(c_config, author_mapping, author_names_checklist)
                set_author_highlight_config(c_config, author_mapping, author_names_checklist)
                set_role_highlight_config(c_config)
                set_channel_config(c_config, channel_mapping, channel_names_checklist)
                set_webhook_config(c_config, webhook_mapping, webhook_names_checklist)
                this_channel_configs.append(c_config)
                
            if len(this_channel_configs) == 0:
                continue
            self.repost_settings[int(id)] = this_channel_configs
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
    
    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
            self._config[key] = value
        self.save()
        
    def save(self):
        with open(self.config_path, 'w') as f:
            json.dump(self._config, f, indent=4)