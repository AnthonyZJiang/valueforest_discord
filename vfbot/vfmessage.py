import discord
import re

from .utils import ASHLEY_ID, ANGELA_ID, ocr_image_from_message
from .optionposition import OptionPosition

class VFMessage:
    def __init__(self, message: discord.Message, config: dict):
        self.dc_msg = message
        self.config = config
        
        self._content = message.content
        self.target_channel_id = config['target_channel_id']
        self.author_name = self.config['author_name_override'] if self.config['author_name_override'] else self.dc_msg.author.display_name
        self.credit = self.dc_msg.jump_url
        
        self.option_position = None
        self.option_update = None
        self.last_price = None
        self.beautify()
        self.construct_option_position()
        
    @property
    def content(self) -> str:
        _content = self._content
        if self.dc_msg.attachments:
            if _content or len(self.dc_msg.attachments) > 1:
                _content += " " + " ".join([f.url for f in self.dc_msg.attachments])
            else:
                _content = self.dc_msg.attachments[0].url
        if self.config['show_name']:
            _content = f"【{self.author_name}】{_content}"
        if self.config['show_credit']:
            _content = f"{_content} | Credit: {self.credit}"
        return _content
    
    @property
    def embeds(self) -> discord.Embed:
        return self.dc_msg.embeds[0] if self.dc_msg.embeds else None
        
    def beautify(self):
        self._content = self._content.replace("@c2.ini", "")
        self._content = re.sub(r':9655_eyesshaking_new:|<a:9655_eyesshaking_new:\d+>', ":eyes:", self._content)
        self._content = self._content.replace(":pngwing:", ":red_circle:")
        self._content = self._content.replace(":verifyblue:", ":white_check_mark:")
        
        if self.dc_msg.author.id == ASHLEY_ID: # ashley
            self.beautify_ashley()
        elif self.dc_msg.author.id == ANGELA_ID: # angela
            self.beautify_angela()
            
    def construct_option_position(self):
        if self.dc_msg.author.id != ASHLEY_ID and self.dc_msg.author.id != ANGELA_ID:
            return
        loc = self._content.find(":new:")
        if loc > -1:
            self.option_position = OptionPosition.from_text(self._content[loc:], self.dc_msg.author.id)
        if loc > 5:
            self.option_update = self._content[:loc].split("||")[0].strip()
        if loc == -1:
            self.option_update = self._content.strip()
            
        if self.option_update:  
            if dollar_amounts := re.findall(r'\$(\d+\.\d+)', self.option_update):
                self.last_price = min(dollar_amounts)
            
        if ".jpg" in self._content:
            ocr_result = ocr_image_from_message(self.dc_msg, self.config['ocr_api_key'])
            if ocr_result:
                symbol, strike, option_type, open_price, last_price = ocr_result
                if not open_price:
                    open_price = last_price
                if not self.option_position:
                    self.option_position = OptionPosition(self.dc_msg.author.id, symbol, strike, option_type, open_price, self._content)
                elif self.option_position.open_price is None:
                    self.option_position.open_price = open_price
                self.option_update = self._content
                self.last_price = last_price
                
    def beautify_ashley(self) -> str:
        self._content = re.sub(r':RedAlert:|<a:RedAlert:\d+>', ":new:", self._content)
            
    def beautify_angela(self) -> str:
        self._content = re.sub(r':8375_siren_blue:|<a:8375_siren_blue:\d+>', ":new:", self._content)
        self._content = re.sub(r':RedAlert:|<a:RedAlert:\d+>', ":red_sqare:", self._content)
        self._content = re.sub(r':greensiren:|<a:greensiren:\d+>', ":green_square:", self._content)