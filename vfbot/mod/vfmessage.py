from __future__ import annotations
from typing import TYPE_CHECKING
import re
from datetime import datetime, timedelta, timezone
from collections import namedtuple

import selfcord

if TYPE_CHECKING:
    import discord
    from typing_extensions import Self

REFERENCE_CHAR_LIMIT = 100
MESSAGE_CHAR_LIMIT = 2000


JumpLinkDetails = namedtuple("JumpLinkDetails", ["url", "channel_id", "message_id"])


class WebhookConfig:
    def __init__(self, url: str, use_dynamic_avatar_name: bool = True):
        self.url = url
        self.use_dynamic_avatar_name = use_dynamic_avatar_name


class VFMessage:
    def __init__(self, content: str, config: dict, **kwargs):
        self._content = content
        self.config = config

        self.target_channel_ids = config.get("target_channel", [])
        if isinstance(self.target_channel_ids, int):
            self.target_channel_ids = [self.target_channel_ids]

        self.webhook_configs: list[WebhookConfig] = []
        for webhook_url in config.get("webhook", []):
            if isinstance(webhook_url, dict):
                self.webhook_configs.append(
                    WebhookConfig(
                        webhook_url.get("url", None), webhook_url.get("dynamic_avatar_name", True)
                    )
                )
            else:
                self.webhook_configs.append(WebhookConfig(webhook_url))
        self.is_webhook = len(self.webhook_configs) > 0
        self.show_author_name = config.get("show_author_name", False) and not self.is_webhook
        self.show_credit = config.get("show_credit", False)

        self.raw_msg_carrier: discord.Message = kwargs.get("raw_msg_carrier", None)
        self.author_name: str = kwargs.get("author_name", None)
        self.credit: str = kwargs.get("credit", None)
        self.embeds: list[dict] = kwargs.get("embeds", [])
        self.reference_msg: discord.Message = kwargs.get("reference_msg", None)
        self.dc_jump_links: list[JumpLinkDetails] = kwargs.get(
            "dc_jump_links", []
        )  # url, channel id and message id

        self.webhook_author_name: str = self.raw_msg_carrier.author.display_name

    @classmethod
    def from_dc_msg(cls, dc_msg: discord.Message, config: dict) -> Self:
        def get_embeds(embeds: list[discord.Embed]):
            embeds_list = []
            for embed in embeds:
                if embed.url and embed.url.startswith("https://discord.com"):
                    continue
                embeds_list.append(VFMessage.selfcord_embed_to_dict(embed))
            return embeds_list

        def get_dc_jump_links(content: str) -> list[int]:
            # url example: "https://discord.com/channels/1320356811441700954/1332897444530487358/1442530901266268223"
            matches = re.findall(r"(https://discord\.com/channels/(\d+)/(\d+)/(\d+))", content)
            if matches:
                return [
                    JumpLinkDetails(
                        url=match[0],
                        channel_id=int(match[2]),
                        message_id=int(match[3]),
                    )
                    for match in matches
                ]
            return []

        content = dc_msg.content

        if dc_msg.attachments:
            content += " " + " ".join([f.url for f in dc_msg.attachments])

        author_name = config.get(
            "author_name_override",
            config.get("author", {}).get("name_override", dc_msg.author.display_name),
        )

        msg = cls(
            content.strip(),
            config,
            raw_msg_carrier=dc_msg,
            author_name=author_name,
            credit=dc_msg.jump_url,
            embeds=get_embeds(dc_msg.embeds),
            reference_msg=dc_msg.reference.resolved if dc_msg.reference else None,
            dc_jump_links=get_dc_jump_links(content),
        )

        highlight_set = False
        if config.get("role_highlight", None):
            for role in dc_msg.author.roles:
                if role.id in config["role_highlight"]:
                    msg.webhook_author_name = "【🚨关注用户🚨】" + msg.webhook_author_name
                    highlight_set = True
                    break
        if (
            not highlight_set
            and config.get("author_highlight", None)
            and dc_msg.author.id in config["author_highlight"]
        ):
            msg.webhook_author_name = "【🚨关注用户🚨】" + msg.webhook_author_name
        return msg

    @property
    def cleaned_content(self) -> str:
        return self._content

    @property
    def content(self) -> str:
        _content = self.stylize()
        if self.raw_msg_carrier.channel.id == 856197997767163904:
            # replace <br/> with \n
            _content = _content.replace("<br/>", "\n")
            # replace <span ...>$1</span> with $1
            _content = re.sub(r"<span[^>]*>(.*?)</span>", r"\1", _content)
            # replace <b>$1</b> with **$1**
            _content = re.sub(r"<b>(.*?)</b>", r"**\1**", _content)
        if self.show_author_name:
            if self.is_emoji(self.author_name):
                _content = f"{self.author_name} {_content}"
            else:
                _content = f"【{self.author_name}】 {_content}"
        if self.reference_msg:
            try:
                # remove emojis in <> and normal emojis in ::
                referenced_content = re.sub(r"<\S+>|:\S+:", "", self.reference_msg.content).strip()
                # remove @, url, and line breaks
                referenced_content = re.sub(r"@|https?:|[\n\r]+", "", referenced_content)
                # limit the length of referenced_content to 20 characters
                if len(referenced_content) > REFERENCE_CHAR_LIMIT:
                    referenced_content = referenced_content[:REFERENCE_CHAR_LIMIT] + "..."
                if referenced_content:
                    resolved_content = f"[{referenced_content}]({self.reference_msg.jump_url})"
                else:
                    resolved_content = f"[Go to message]({self.reference_msg.jump_url})"
                _content = f"-# Reply to: {resolved_content}\n" + _content
            except AttributeError:
                _content = "-# Reply to a deleted message\n" + _content
        if self.raw_msg_carrier.message_snapshots:
            snapshot = self.raw_msg_carrier.message_snapshots[0]
            snapshot_content = "\n> ".join(snapshot.content.strip().split("\n"))
            snapshot_content += " " + " ".join([f.url for f in snapshot.attachments])
            created_at = int(snapshot.created_at.timestamp())
            _content = (
                f"> -# ╭ *Forwarded message* • <t:{created_at}>\n> {snapshot_content}\n{_content}"
            )
        if self.show_credit:
            _content = f"{_content} [ߺ ʟɪɴᴋ ߺ]({self.credit})"
        if time_str := self.get_date_str():
            _content = f"{time_str}\n{_content}"
        return _content.strip()

    def get_contents(self) -> list[str]:
        if len(self.content) < MESSAGE_CHAR_LIMIT:
            return [self.content]
        contents = []
        # split content into chunks of MESSAGE_CHAR_LIMIT characters at spaces
        content = self.content
        while len(content) > MESSAGE_CHAR_LIMIT:
            space_index = content.rfind(" ", 0, MESSAGE_CHAR_LIMIT - 2)
            if space_index == -1:
                space_index = MESSAGE_CHAR_LIMIT
            contents.append(content[:space_index] + " …")
            content = "… " + content[space_index + 1 :]
        contents.append(content)
        return contents

    def stylize(self) -> str:
        style = self.config.get("style", None)
        if not style:
            return self._content
        content = self._content
        for key, value in style.items():
            if key == "unbold":
                content = content.replace("**", "")
            elif key == "prefix":
                content = f"{value} {content}"
            elif key == "remove_mentions":
                content = content.replace("@here", "")
                content = content.replace("@everyone", "")
                content = content.replace("@unknown-role", "")
                content = re.sub(r"<@&\d+>", "", content)

        return content

    def get_date_str(self) -> str:
        if not isinstance(self.raw_msg_carrier, selfcord.Message):
            return ""
        t_delta = datetime.now(timezone.utc) - self.raw_msg_carrier.created_at
        if t_delta > timedelta(seconds=5):
            time_str = self.raw_msg_carrier.created_at.strftime(
                "-# :small_blue_diamond: Posted at %Y-%m-%d %H:%M:%S UTC"
            )
            totalMinute, second = divmod(t_delta.seconds, 60)
            hour, minute = divmod(totalMinute, 60)
            if t_delta >= timedelta(days=1):
                time_str = f"{time_str} ({t_delta.days} days {hour} hr {minute} min ago)"
            elif t_delta > timedelta(hours=1):
                time_str = f"{time_str} ({hour} hr {minute} min ago)"
            elif t_delta > timedelta(minutes=1):
                time_str = f"{time_str} ({minute} min ago)"
            else:
                time_str = f"{time_str} ({second} sec ago)"
            return time_str
        else:
            return ""

    @staticmethod
    def is_emoji(val: str) -> bool:
        return val and val.startswith("<:") and val.endswith(">")

    @staticmethod
    def selfcord_embed_to_dict(embed: selfcord.Embed) -> dict:
        if embed.fields:
            fields = [
                {"name": field.name, "value": field.value, "inline": field.inline}
                for field in embed.fields
            ]
        else:
            fields = []
        if embed.footer:
            footer = {"text": embed.footer.text, "icon_url": embed.footer.icon_url}
        else:
            footer = None
        if embed.image:
            image = {
                "url": embed.image.url,
                "width": embed.image.width,
                "height": embed.image.height,
            }
        else:
            image = None
        if embed.thumbnail:
            thumbnail = {
                "url": embed.thumbnail.url,
                "width": embed.thumbnail.width,
                "height": embed.thumbnail.height,
            }
        else:
            thumbnail = None
        if embed.author:
            author = {
                "name": embed.author.name,
                "url": embed.author.url,
                "icon_url": embed.author.icon_url,
            }
        else:
            author = None
        if embed.color:
            color = embed.color.value
        else:
            color = None
        if embed.timestamp:
            timestamp = embed.timestamp.isoformat()
        else:
            timestamp = None
        return {
            "title": embed.title,
            "description": embed.description,
            "fields": fields,
            "url": embed.url,
            "timestamp": timestamp,
            "footer": footer,
            "image": image,
            "thumbnail": thumbnail,
            "author": author,
            "color": color,
        }
