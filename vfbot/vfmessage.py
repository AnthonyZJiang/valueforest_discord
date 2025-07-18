import discord
import selfcord
import re
from datetime import datetime, timedelta, timezone
from typing_extensions import Self
from .utils import ASHLEY_ID, ANGELA_ID

CHAR_LIMIT = 100

class WebhookConfig:
    def __init__(self, url: str, use_dynamic_avatar_name: bool = True):
        self.url = url
        self.use_dynamic_avatar_name = use_dynamic_avatar_name

class VFMessage:
    def __init__(self, content: str, config: dict, raw_msg_carrier = None, author_name = None, credit = None, embeds = [], reference_msg = None):
        self._content = content
        self.config = config
        
        self.target_channel_ids = config.get('target_channel', [])
        if isinstance(self.target_channel_ids, int):
            self.target_channel_ids = [self.target_channel_ids]
            
        self.webhook_configs: list[WebhookConfig] = [] 
        for webhook_url in config.get('webhook', []):
            if isinstance(webhook_url, dict):
                self.webhook_configs.append(WebhookConfig(webhook_url.get('url', None), webhook_url.get('dynamic_avatar_name', True)))
            else:
                self.webhook_configs.append(WebhookConfig(webhook_url))
        self.is_webhook = len(self.webhook_configs) > 0
        self.show_author_name = config.get('show_author_name', False) and not self.is_webhook
        self.show_credit = config.get('show_credit', False)
            
        self.raw_msg_carrier: discord.Message = raw_msg_carrier
        self.author_name: str = author_name
        self.credit: str = credit
        self.embeds: list[dict] = embeds
        self.reference_msg: discord.Message = reference_msg
        self.webhook_author_name: str = self.raw_msg_carrier.author.display_name
        
    @classmethod
    def from_dc_msg(cls, dc_msg: discord.Message, config: dict) -> Self:
        def get_author_name(author_name: str):
            if author_name == '$cathy-whale$':
                return '巨鲸分析'
            elif author_name == '$cathy-swing$':
                return '短线分析'
            elif author_name == '$cathy-view$':
                return '观点分享'
            elif author_name == '$cathy-invest$':
                return '长线布局'
            elif author_name == '$cathy-strategy$':
                return '交易心得'
            else:
                return author_name
        
        def get_embeds(embeds: list[discord.Embed]):
            embeds_list = []
            for embed in embeds:
                if not embed.url:
                    embeds_list.append(VFMessage.selfcord_embed_to_dict(embed))
            return embeds_list
            
        content = dc_msg.content

        if dc_msg.author.id == ASHLEY_ID: # ashley
            content = content.replace("@c2.ini", "")
            content = re.sub(r':9655_eyesshaking_new:|<a:9655_eyesshaking_new:\d+>', ":eyes:", content)
            content = content.replace(":pngwing:", ":red_circle:")
            content = content.replace(":verifyblue:", ":white_check_mark:")
            content = re.sub(r':RedAlert:|<a:RedAlert:\d+>', ":new:", content)
            
        elif dc_msg.author.id == ANGELA_ID: # angela
            content = content.replace("@c2.ini", "")
            content = re.sub(r':9655_eyesshaking_new:|<a:9655_eyesshaking_new:\d+>', ":eyes:", content)
            content = content.replace(":pngwing:", ":red_circle:")
            content = content.replace(":verifyblue:", ":white_check_mark:")
            content = re.sub(r':8375_siren_blue:|<a:8375_siren_blue:\d+>', ":new:", content)
            content = re.sub(r':RedAlert:|<a:RedAlert:\d+>', ":red_sqare:", content)
            content = re.sub(r':greensiren:|<a:greensiren:\d+>', ":green_square:", content)
            
        if dc_msg.attachments:
            content += " " + " ".join([f.url for f in dc_msg.attachments])

        author_name = config.get('author_name_override', 
                                 config.get('author', {}).get('name_override', dc_msg.author.display_name))

        msg = cls(content.strip(), 
                  config, 
                  raw_msg_carrier = dc_msg, 
                  author_name = get_author_name(author_name),
                  credit = dc_msg.jump_url, 
                  embeds = get_embeds(dc_msg.embeds),
                  reference_msg = dc_msg.reference.resolved if dc_msg.reference else None)
        
        if config.get('author_highlight', None) and dc_msg.author.id in config['author_highlight']:
                msg.webhook_author_name = "【🚨关注用户🚨】" + msg.webhook_author_name
        return msg
        
    @property
    def content(self) -> str:
        _content = self._content
        if self.show_author_name:
            if self.is_emoji(self.author_name):
                _content = f"{self.author_name} {_content}"
            else:
                _content = f"【{self.author_name}】 {_content}"
        if self.reference_msg:
            try:
                # remove emojis in <> and normal emojis in ::
                referenced_content = re.sub(r'<\S+>|:\S+:', '', self.reference_msg.content).strip()
                # remove @, url, and line breaks
                referenced_content = re.sub(r'@|https?:|[\n\r]+', '', referenced_content)
                # limit the length of referenced_content to 20 characters
                if len(referenced_content) > CHAR_LIMIT:
                    referenced_content = referenced_content[:CHAR_LIMIT] + "..."
                if referenced_content:
                    resolved_content = f"[{referenced_content}]({self.reference_msg.jump_url})"
                else:
                    resolved_content = f"[Go to message]({self.reference_msg.jump_url})"
                _content = f"-# Reply to: {resolved_content}\n" + _content
            except AttributeError:
                _content = f"-# Reply to a deleted message\n" + _content
        if self.show_credit:
            _content = f"{_content} [ߺ ʟɪɴᴋ ߺ]({self.credit})"
        if time_str := self.get_date_str():
            _content = f"{time_str}\n{_content}"
        return _content.strip()
    
    def get_date_str(self) -> str:
        if not isinstance(self.raw_msg_carrier, selfcord.Message):
            return ""
        t_delta = datetime.now(timezone.utc) - self.raw_msg_carrier.created_at
        if t_delta > timedelta(seconds=5):
            time_str = self.raw_msg_carrier.created_at.strftime("-# :small_blue_diamond: Posted at %Y-%m-%d %H:%M:%S UTC")
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
            fields = [{
                "name": field.name,
                "value": field.value,
                "inline": field.inline
            } for field in embed.fields]
        else:
            fields = []
        if embed.footer:
            footer = {
                "text": embed.footer.text,
                "icon_url": embed.footer.icon_url
            }
        else:
            footer = None
        if embed.image:
            image = {
                "url": embed.image.url,
                "width": embed.image.width,
                "height": embed.image.height
            }
        else:
            image = None
        if embed.thumbnail:
            thumbnail = {
                "url": embed.thumbnail.url,
                "width": embed.thumbnail.width,
                "height": embed.thumbnail.height
            }
        else:
            thumbnail = None
        if embed.author:
            author = {
                "name": embed.author.name,
                "url": embed.author.url,
                "icon_url": embed.author.icon_url
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
            "color": color
        }
