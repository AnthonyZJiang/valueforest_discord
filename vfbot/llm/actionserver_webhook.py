from discord_webhook import DiscordWebhook
import queue
import logging
import threading
from selfcord import Message as DiscordMessage
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class ActionChain:
    def __init__(self, command: str, dc_msg: DiscordMessage):
        self.dc_msg = dc_msg
        self.actions = [Action(part) for part in command.split(";")]
        self.is_valid = all(action.is_valid for action in self.actions)
        self.is_ign = all(action.is_ign for action in self.actions)
        self.error_message = ". ".join(action.error_message for action in self.actions if action.error_message)
        

class Action:
    ACTION_BTO = "Buy"
    ACTION_TP = "Sell"
    ACTION_SL = "Sell"
    ACTION_MS = "Set SL"
    
    def __init__(self, command: str):
        self.parts = command.split(",")
        self.ticker = None
        self.action = None
        self.price = None
        self.stop_loss = None
        self.error_message = None
        
        if command == "ign":
            self.is_ign, self.is_valid = True, True
            return
        
        self.is_ign, self.is_valid = False, False
        
        self._parse_action()
    
    def _parse_action(self):
        #$<股票代码>,BTO,O=<开仓价>,S=<止损价>
        #$<股票代码,TP
        #$<股票代码,SL
        #$<股票代码,MS,S=<止损价>
        #ign
        
        if len(self.parts) < 2:
            self.error_message = "At least 2 parts are required"
            return
        
        # ACTION PART 1: ticker
        if not self.parts[0].startswith("$") and len(self.parts[0]) < 2:
            self.error_message = f"Ticker must be at least 2 characters with $"
            return
        self.ticker = self.parts[0][1:]
        
        # ACTION PART 2: action
        if self.parts[1] == "BTO":
            self.action = self.ACTION_BTO
        elif self.parts[1] == "TP":
            self.action = self.ACTION_TP
        elif self.parts[1] == "SL":
            self.action = self.ACTION_SL
        elif self.parts[1] == "MS":
            self.action = self.ACTION_MS
        else:
            self.error_message = "Invalid action"
            return
        
        self.is_valid = True
        
        if len(self.parts) < 3:
            if self.action == self.ACTION_MS:
                self.is_valid = False
                self.error_message = "Move stop loss requires a stop loss price"
            return
        
        # ACTION PART 3 and beyond: price and stop loss
        for part in self.parts[2:]:
            if part.startswith("O="):
                self.price = part[2:]
            elif part.startswith("S="):
                self.stop_loss = part[2:]
            else:
                self.error_message = "Invalid action part, O or S is expected"
                return
        
    def to_str(self):
        if not self.is_valid:
            return self.error_message
        return "*%s*\n%s%s%s" %(
            self.ticker,
            self.action,
            f'@ ${self.price}' if self.price else '',
            f', SL: ${self.stop_loss}' if self.stop_loss else ''
        )
        
"""     
[
    {
        "webhook": "https://discord.com/api/webhooks/1395526838197026973/PZwMjJoP8YmZ07wjfwJgORicfuMcu0IjZUVDp008bs9SYiBdEmgiCd8775Dmm9roEiad",
        "ignore_ignored_posts": false,
        "ignored_posts_use_mention": false,
        "mention": ["everyone"]
    },
    {
        "webhook": "https://discord.com/api/webhooks/1427987391511134321/bt098ncSYB-PcYngW5bSaMk0MnaaEsG72O0sqadQ6kY2qJx6jDHwXlHcl9AaASOQamQE",
        "ignore_ignored_posts": false,
        "ignored_posts_use_mention": false,
        "mention": ["everyone"]
    }
]
"""

class ActionServer:
    def __init__(self):
        self.webhooks: dict[str, DiscordWebhook] = {}
        
        self.action_chains_queue = queue.Queue()
        self.execution_thread = threading.Thread(target=self._execute)
        self.execution_thread.start()
    
    def add_action(self, action_cmds: str, dc_msg: DiscordMessage, target_config: list[dict]):
        action_chain = ActionChain(action_cmds, dc_msg)
        if action_chain.is_valid:
            self.action_chains_queue.put((action_chain, target_config))
        else:
            logger.error(f"Invalid actions: {action_chain.error_message}")
        
    def _get_webhook(self, target_webhook_url: str):
        if target_webhook_url not in self.webhooks:
            self.webhooks[target_webhook_url] = DiscordWebhook(url=target_webhook_url)
        return self.webhooks[target_webhook_url]
            
    def _execute(self):
        while True:
            action_chain, target_config = self.action_chains_queue.get()
            self._execute_webhooks(action_chain, target_config)
        
    def _execute_webhooks(self, action_chain: ActionChain, target_config: list[str]):
        embeds = self._build_webhook_embeds(action_chain)
        for config in target_config:
            if config['ignore_ignored_posts'] and action_chain.is_ign:
                continue
            mentions = config.get('mention', [])
            if mentions and not action_chain.is_ign:
                mention_str = " @" + " @".join(mentions)
            else:
                mention_str = ""
                
            webhook = self._get_webhook(config['webhook'])
            webhook.embeds = embeds
            webhook.content = mention_str
            webhook.username = "ChatGPT"
            webhook.execute()
        
    def _build_webhook_embeds(self, action_chain: ActionChain):
        embeds = []
        embed = {
            "description": "",
            "fields": [
            ],
            "author": {
                "name": action_chain.dc_msg.author.display_name,
                "icon_url": action_chain.dc_msg.author.avatar.url
            },
            "url": action_chain.dc_msg.jump_url
        }
        titles =[]
        if action_chain.actions:
            _prev_ticker = None
            for action in action_chain.actions:
                if action.is_ign:
                    continue
                titles.append(f"{action.ticker}: {action.action}")
                _ticker = action.ticker
                action_str = f"- *Action:* {action.action}"
                price_str = f"\n- *Open price:* ${action.price}" if action.price else ""
                stop_loss_str = f"\n- *Stop loss:* ${action.stop_loss}" if action.stop_loss else ""
                if _ticker != _prev_ticker:
                    embed['fields'].append({
                        "name": f"{_ticker}",
                        "value": f"{action_str}{price_str}{stop_loss_str}",
                        "inline": False
                    })
                    _prev_ticker = _ticker
                else:
                    embed['fields'][-1]['value'] += f"\n{action_str}{price_str}{stop_loss_str}"
        else:
            embed["description"] = "No actions."
        embed['fields'].append({
            "name": "Original post",
            "value": action_chain.dc_msg.content
            })
        embed['fields'].append({
            "name": "Time reference",
            "value": f"Posted at <t:{int(action_chain.dc_msg.created_at.timestamp())}> ({action_chain.dc_msg.created_at.second}s)\nDelay since post: {(datetime.now(timezone.utc).timestamp() - action_chain.dc_msg.created_at.timestamp()):.2f}s"
            })
        embed['title'] = " | ".join(titles) if titles else "No actions"
        embeds.append(embed)
        return embeds