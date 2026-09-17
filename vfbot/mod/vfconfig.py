import json
import logging


logger = logging.getLogger(__name__)


def pop_from_checklist(checklist: list[str], item: str) -> None:
    try:
        checklist.pop(checklist.index(item))
    except ValueError:
        pass


TEST_CHANNEL_NAME = "vf_bot_test_dump"
TEST_WEBHOOK_NAME = "wh_bot_test_dump"


class KeepAliveConfig:
    def __init__(self, config: dict):
        if not config:
            self.enabled = False
            return
        self.status_message_channel_id = config.get("status_message_channel_id", None)
        self.status_message_webhook = config.get("status_message_webhook", None)
        self.status_message_id = config.get("status_message_id", None)
        self.down_time_require_pull_only_seconds = config.get(
            "down_time_require_pull_only_seconds", 15
        )

        _config_handshake = config.get("handshake", {})
        self.handshake_channel_id = _config_handshake.get("channel_id", None)
        self.handshake_interval = _config_handshake.get("interval", 30)
        self.handshake_timeout = _config_handshake.get("timeout", 65)
        self.handshake_response_webhook = _config_handshake.get("response_webhook", None)

        self.enabled = (
            self.handshake_channel_id is not None
            and self.handshake_response_webhook is not None
        )


class SelfbotProfile:
    def __init__(self, profile_id: str, section: dict, parent: "VFConfig"):
        self.id = profile_id
        self._section = section
        self._parent = parent
        self.self_token = section["self_token"]
        self.keepalive = KeepAliveConfig(section.get("keepalive", {}))
        self.repost_settings: dict = {}
        self.channel_list: list[int] = []
        self.llm_config = section.get("llm_config", None)
        self.llm_channel: list[int] = (
            [int(i) for i in self.llm_config.keys()] if self.llm_config else []
        )

    def read_config(self) -> None:
        self.repost_settings = self._parent.construct_repost_settings(
            self._section.get("repost_settings", {})
        )
        self.channel_list = list(self.repost_settings.keys())
        self.llm_config = self._section.get("llm_config", None)
        self.llm_channel = (
            [int(i) for i in self.llm_config.keys()] if self.llm_config else []
        )


class VFConfig:

    def __init__(
        self,
        config_path: str,
        debug: bool = False,
        keepalive_only: bool = False,
        selfbot_id: str | None = None,
    ):
        self.config_path = config_path
        with open(config_path, "r", encoding="utf-8") as f:
            self._config = json.load(f)

        logger.info("Config version: %s", self._config.get("config_version", "unknown"))

        if "selfbots" not in self._config:
            raise ValueError("Config must contain a 'selfbots' section")

        self._test_mode = self._config.get("test_mode", {"enabled": False})
        if debug:
            self._test_mode["enabled"] = True
        self.bot_token = self._config.get("bot_token", None)
        self._active: SelfbotProfile | None = None

        self._load_selfbots()

        if keepalive_only:
            for profile in self.selfbots.values():
                profile.keepalive.enabled = (
                    profile.keepalive.enabled and self.bot_token is not None
                )
            self.keepalive_enabled = any(
                profile.keepalive.enabled for profile in self.selfbots.values()
            )
            return

        if not selfbot_id:
            raise ValueError("selfbot_id is required when not in keepalive_only mode")

        self.read_selfbot_config(selfbot_id)

    def _load_selfbots(self) -> None:
        self.selfbots: dict[str, SelfbotProfile] = {}
        for profile_id, section in self._config["selfbots"].items():
            self.selfbots[profile_id] = SelfbotProfile(profile_id, section, self)

    @property
    def active(self) -> SelfbotProfile:
        if self._active is None:
            raise ValueError("No active selfbot profile")
        return self._active

    @property
    def selfbot_id(self) -> str:
        return self.active.id

    @property
    def self_token(self) -> str:
        return self.active.self_token

    @property
    def keepalive(self) -> KeepAliveConfig:
        return self.active.keepalive

    @property
    def repost_settings(self) -> dict:
        return self.active.repost_settings

    @property
    def channel_list(self) -> list[int]:
        return self.active.channel_list

    @property
    def llm_config(self):
        return self.active.llm_config

    @property
    def llm_channel(self) -> list[int]:
        return self.active.llm_channel

    def activate_selfbot(self, selfbot_id: str) -> SelfbotProfile:
        if selfbot_id not in self.selfbots:
            raise ValueError(f"Selfbot '{selfbot_id}' not found in config")
        self._active = self.selfbots[selfbot_id]
        return self._active

    def read_selfbot_config(self, selfbot_id: str | None = None) -> None:
        if selfbot_id is None:
            if self._active is None:
                raise ValueError("selfbot_id is required")
            self._active.read_config()
            return
        self.activate_selfbot(selfbot_id).read_config()

    def construct_repost_settings(self, repost_settings_source: dict) -> dict:
        repost_settings: dict = {}

        def set_author_config(
            channel_config: list[str], author_mapping: dict, author_names_checklist: list[str]
        ) -> dict:
            if not (authors := channel_config.get("author_filter", None)):
                return None
            if isinstance(authors, str):
                authors = [authors]
            authors_config = {}
            for author in authors:
                if not (author_config := author_mapping.get(author, None)):
                    logger.error("Author %s not found in users list.", author)
                    continue
                authors_config[int(author_config["id"])] = author_config
                pop_from_checklist(author_names_checklist, author)
            channel_config["author_filter"] = authors_config

        def set_author_highlight_config(
            channel_config: list[str], author_mapping: dict, author_names_checklist: list[str]
        ) -> dict:
            if not (authors := channel_config.get("author_highlight", None)):
                return None
            if isinstance(authors, str):
                authors = [authors]
            authors_highlight_config = {}
            for author in authors:
                if not (author_config := author_mapping.get(author, None)):
                    logger.error("Author %s not found in users list.", author)
                    continue
                authors_highlight_config[int(author_config["id"])] = author_config
                pop_from_checklist(author_names_checklist, author)
            channel_config["author_highlight"] = authors_highlight_config

        def set_role_highlight_config(channel_config: list[str]) -> dict:
            if not (roles := channel_config.get("role_highlight", None)):
                return None
            channel_config["role_highlight"] = roles

        def set_channel_config(
            channel_config: list[str], channel_mapping: dict, channel_names_checklist: list[str]
        ) -> dict:
            if self._test_mode["enabled"]:
                channel_config["target_channel"] = channel_mapping.get(
                    self._test_mode["target_channel"], []
                )
                return
            if not (target_channel_name := channel_config.get("target_channel", None)):
                return
            if not isinstance(target_channel_name, list):
                target_channel_name = [target_channel_name]
            channel_config["target_channel"] = []
            for channel_name in target_channel_name:
                channel_id = channel_mapping.get(channel_name, None)
                if not channel_id:
                    logger.error("Channel %s not found in channels list.", channel_name)
                    continue
                channel_config["target_channel"].append(channel_id)
                pop_from_checklist(channel_names_checklist, channel_name)

        def set_webhook_config(
            channel_config: list[str], webhook_mapping: dict, webhook_names_checklist: list[str]
        ) -> dict:
            if self._test_mode["enabled"]:
                channel_config["webhook"] = webhook_mapping.get(self._test_mode["webhook"], [])
                if isinstance(channel_config["webhook"], str):
                    channel_config["webhook"] = [channel_config["webhook"]]
                return
            if not (target_webhook_name := channel_config.get("webhook", None)):
                return
            if not isinstance(target_webhook_name, list):
                target_webhook_name = [target_webhook_name]
            channel_config["webhook"] = []
            for webhook_name in target_webhook_name:
                webhook_id = webhook_mapping.get(webhook_name, None)
                if not webhook_id:
                    logger.error("Webhook %s not found in webhooks list.", webhook_name)
                    continue
                channel_config["webhook"].append(webhook_id)
                pop_from_checklist(webhook_names_checklist, webhook_name)

        channel_mapping: dict[str, str] = self._config["channels"]
        author_mapping: dict[str, dict] = self._config["users"]
        webhook_mapping: dict[str, str] = self._config.get("webhooks", {})
        channel_names_checklist = list[str](channel_mapping.keys())
        author_names_checklist = list[str](author_mapping.keys())
        webhook_names_checklist = list[str](webhook_mapping.keys())

        for k, channel_configs in repost_settings_source.items():
            if not (channel_id := channel_mapping.get(k, None)):
                logger.error("Channel %s not found in channels list, ignored", k)
                continue
            this_channel_configs = []
            for c_config in channel_configs:
                if not c_config.get("enabled", True):
                    continue
                if (
                    self._test_mode["enabled"]
                    and self._test_mode["flagged_only"]
                    and not c_config.get("flag_test_mode", False)
                ):
                    continue
                set_author_config(c_config, author_mapping, author_names_checklist)
                set_author_highlight_config(c_config, author_mapping, author_names_checklist)
                set_role_highlight_config(c_config)
                set_channel_config(c_config, channel_mapping, channel_names_checklist)
                set_webhook_config(c_config, webhook_mapping, webhook_names_checklist)
                this_channel_configs.append(c_config)

            if len(this_channel_configs) == 0:
                continue
            repost_settings[int(channel_id)] = this_channel_configs
            pop_from_checklist(channel_names_checklist, k)

        if self._test_mode["enabled"]:
            return repost_settings
        pop_from_checklist(channel_names_checklist, TEST_CHANNEL_NAME)
        pop_from_checklist(webhook_names_checklist, TEST_WEBHOOK_NAME)
        if len(channel_names_checklist) > 0:
            logger.warning("The following channels are not used: %s", channel_names_checklist)
        if len(author_names_checklist) > 0:
            logger.warning("The following authors are not used: %s", author_names_checklist)
        if len(webhook_names_checklist) > 0:
            logger.warning("The following webhooks are not used: %s", webhook_names_checklist)
        return repost_settings

    def get(self, key, default=None):
        return self.repost_settings.get(key, default)

    def keys(self):
        return self.repost_settings.keys()

    def values(self):
        return self.repost_settings.values()

    def items(self):
        return self.repost_settings.items()

    def _sync_profile_from_section(self, selfbot_id: str, key: str, value) -> None:
        profile = self.selfbots.get(selfbot_id)
        if profile is None:
            return
        if key == "keepalive" and isinstance(value, dict):
            for field, field_value in value.items():
                if hasattr(profile.keepalive, field):
                    setattr(profile.keepalive, field, field_value)
        elif hasattr(profile, key):
            setattr(profile, key, value)

    def update(self, selfbot_id: str | None = None, **kwargs) -> None:
        if selfbot_id is not None:
            section = self._config["selfbots"][selfbot_id]
            for key, value in kwargs.items():
                if isinstance(value, dict) and isinstance(section.get(key), dict):
                    section[key].update(value)
                else:
                    section[key] = value
                self._sync_profile_from_section(selfbot_id, key, value)
        else:
            for key, value in kwargs.items():
                if isinstance(value, dict) and isinstance(self._config.get(key), dict):
                    self._config[key].update(value)
                else:
                    self._config[key] = value
        self.save()

    def save(self) -> None:
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=4)
