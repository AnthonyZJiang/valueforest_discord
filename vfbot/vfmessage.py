import discord
import re

from .utils import ASHLEY_ID, ANGELA_ID

class VFMessage:
    def __init__(self, message: discord.Message, config: dict):
        self.dc_msg = message
        self.config = config
        
        self._content = message.content
        self.target_channel_id = config['target_channel_id']
        
        self.author_name = self.config.get('author_name_override', '')
        if not self.author_name:
            self.author_name = self.dc_msg.author.display_name
            
        self.credit = self.dc_msg.jump_url
        
        self.last_price = None
        self.beautify()
        
    @property
    def content(self) -> str:
        _content = self._content
        if self.dc_msg.attachments:
            if _content or len(self.dc_msg.attachments) > 1:
                _content += " " + " ".join([f.url for f in self.dc_msg.attachments])
            else:
                _content = self.dc_msg.attachments[0].url
        if self.config.get('show_name', False):
            _content = f"【{self.author_name}】{_content}"
        if self.config.get('show_credit', False):
            _content = f"{_content} | 👉{self.credit}"
        return _content
    
    @property
    def embeds(self) -> list[discord.Embed]:
        return self.dc_msg.embeds
        
    def beautify(self):
        self._content = self._content.replace("@c2.ini", "")
        self._content = re.sub(r':9655_eyesshaking_new:|<a:9655_eyesshaking_new:\d+>', ":eyes:", self._content)
        self._content = self._content.replace(":pngwing:", ":red_circle:")
        self._content = self._content.replace(":verifyblue:", ":white_check_mark:")
        
        if self.dc_msg.author.id == ASHLEY_ID: # ashley
            self.beautify_ashley()
        elif self.dc_msg.author.id == ANGELA_ID: # angela
            self.beautify_angela()
                
    def beautify_ashley(self) -> str:
        self._content = re.sub(r':RedAlert:|<a:RedAlert:\d+>', ":new:", self._content)
            
    def beautify_angela(self) -> str:
        self._content = re.sub(r':8375_siren_blue:|<a:8375_siren_blue:\d+>', ":new:", self._content)
        self._content = re.sub(r':RedAlert:|<a:RedAlert:\d+>', ":red_sqare:", self._content)
        self._content = re.sub(r':greensiren:|<a:greensiren:\d+>', ":green_square:", self._content)