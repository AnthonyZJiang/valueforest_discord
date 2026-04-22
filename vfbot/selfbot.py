from __future__ import annotations
from typing import TYPE_CHECKING, NamedTuple
import logging
from datetime import datetime, timedelta
import json
import re
import asyncio
from collections import namedtuple
from difflib import get_close_matches

import selfcord
from discord_webhook import DiscordWebhook

from .mod.keepalive.handshake import HandshakeResponder
from .mod.llm.gpt import LLMAnalyser
from .mod.vfmessage import VFMessage, JumpLinkDetails
from .mod.utils import FifoDict

if TYPE_CHECKING:
    from .mod.vfconfig import VFConfig
    from .mod.vfmessage import WebhookConfig


MAX_WORKERS = 5

logger = logging.getLogger(__name__)
sem = asyncio.Semaphore(MAX_WORKERS)


SearchRequestDetails = namedtuple("SearchRequestDetails", ["url", "channel_name", "content"])


SentWebhookDetails = NamedTuple("SentWebhookDetails", [("url", str), ("ids", list[int])])
SentWebhookResults = NamedTuple(
    "SentWebhookResults", [("channel_id", int), ("webhook_obj", DiscordWebhook)]
)


class Selfbot(selfcord.Client):

    def __init__(self, config: VFConfig):
        super().__init__(max_messages=100)
        self.config = config
        self._channel_configs = config.repost_settings

        self.forward_history_since = None
        self.forward_history_before = None
        self.forward_history_only = False
        self.forward_history_from_channels: list[str | int] = []
        self._handshake_responder = HandshakeResponder(client=self)
        self._sent_message_queue = FifoDict[int, list[SentWebhookDetails]](maxsize=500)

        if config.llm_config:
            self._llm_analyser = LLMAnalyser(config.llm_config)
        else:
            self._llm_analyser = None

    async def on_ready(self):
        logger.info(
            "Selfbot ready, logged on as %s%s",
            self.user,
            " , forward history only" if self.forward_history_only else "",
        )
        print("Selfbot ready")
        self._handshake_responder.set_ready()
        if self.forward_history_since:
            if isinstance(self.forward_history_since, str):
                self.forward_history_since = datetime.fromisoformat(self.forward_history_since)
            if isinstance(self.forward_history_before, str):
                self.forward_history_before = datetime.fromisoformat(self.forward_history_before)
            logger.info("Forwarding messages since %s", self.forward_history_since)
            await self._forward_history_messages(
                after=self.forward_history_since, before=self.forward_history_before
            )

    async def on_message(self, message: selfcord.Message, is_forward: bool = False) -> bool:
        # when in forwarding history only mode, ignore any new messages
        if self.forward_history_only and not is_forward:
            return False

        # handle handshake messages
        if (
            not self.forward_history_only
            and self._handshake_responder is not None
            and self._handshake_responder.is_valid_handshake_message(message)
        ):
            while not self._handshake_responder.ready:
                await asyncio.sleep(0.1)
            self._handshake_responder.respond(message)
            return False

        # ignore messages from channels not in the config
        if message.channel.id not in self.config.channel_list:
            return False
        sent = False

        for c in self._channel_configs[message.channel.id]:
            # when forwarding history, ignore channels configured to ignore forwarding history
            if is_forward and c.get("ignore_forward_history", False):
                continue
            # check whether the author is set to be included for forwarding
            is_author_valid, author_config = self._check_author(message, c)
            if not is_author_valid:
                continue
            if author_config:
                c["author"] = author_config
            sent = await self._construct_and_send_message(message, c)
        return sent

    async def on_message_edit(self, before: selfcord.Message, after: selfcord.Message) -> bool:
        if before.id not in self._sent_message_queue:
            return
        
        details: list[SentWebhookDetails] = self._sent_message_queue[before.id]
        if not details:
            return False

        for detail in details:
            webhook = DiscordWebhook(url=detail.url)
            for id_ in detail.ids:
                webhook.id = id_
                webhook.delete()
        self._sent_message_queue.pop(before.id)

        await self.on_message(after, is_forward=False)
        return True

    def _check_author(self, message: selfcord.Message, config: dict) -> tuple[bool, dict | None]:
        """Check if the message author is valid for the channel config.

        Parameters:
        -----------
        message: :class:`selfcord.Message`
            The message to check.
        config: :class:`dict`
            The channel config.

        Returns:
        --------
        :class:`tuple[bool, dict | None]`
            A tuple containing a boolean indicating if the message author is valid and the author
            configuration if valid, otherwise :class:`None`.
        """
        if author_ids := config.get("author_filter", {}).keys():
            if message.author.id not in author_ids:
                return False, None
            author_id_name = config["author_filter"][message.author.id].get(
                "display_name_filter", None
            )
            if author_id_name:
                if isinstance(author_id_name, list):
                    if message.author.display_name not in author_id_name:
                        return False, None
                else:
                    if message.author.display_name != author_id_name:
                        return False, None
            return True, config["author_filter"][message.author.id]
        return True, None

    async def _construct_and_send_message(self, message: selfcord.Message, config: dict) -> bool:
        """Construct and send a message to the webhooks.

        Parameters:
        -----------
        message: :class:`selfcord.Message`
            The message to construct and send.
        config: :class:`dict`
            The channel config.

        Returns:
        --------
        :class:`bool`
            :class:`True` if the message is sent successfully, otherwise :class:`False`.
        """
        logger.debug(
            "Received message %s from %s in %s.",
            message.id,
            message.author.display_name,
            message.channel.name,
        )
        msg = VFMessage.from_dc_msg(message, config)
        for webhook_config in msg.webhook_configs:
            results = await self._send_message_via_webhook(msg, webhook_config)
            if not results[0]:
                return False
            self._add_sent_message_details(message.id, results)
            if len(results) == 1 and msg.dc_jump_links:
                await self._handle_jump_links(msg, results[0])

        if self._llm_analyser and message.channel.id in self.config.llm_channel:
            self._llm_analyser.analyse(msg)

        return True

    def _add_sent_message_details(self, message_id: int, results: list[SentWebhookResults]):
        url = results[0].webhook_obj.url
        ids = [result.webhook_obj.id for result in results]
        if message_id not in self._sent_message_queue:
            self._sent_message_queue[message_id] = []
        self._sent_message_queue[message_id].append(SentWebhookDetails(url, ids))

    async def _handle_jump_links(self, msg: VFMessage, webhook_results: SentWebhookResults) -> None:
        logger.debug(
            "Handling %d jump link(s) for message %s",
            len(msg.dc_jump_links),
            msg.raw_msg_carrier.id,
        )
        sent_msg_guild_id = self._get_guild_id_from_channel_id(webhook_results.channel_id)
        guild_link = f"https://discord.com/channels/{sent_msg_guild_id}"
        details = await self._unpackage_jump_links(msg.dc_jump_links)
        matches = await self._search_linked_message(
            details, sent_msg_guild_id, msg.raw_msg_carrier.id
        )
        if not matches:
            return
        content = msg.content
        for match_details in matches:
            content = content.replace(
                match_details.url,
                f"{guild_link}/{match_details.channel_id}/{match_details.message_id}",
            )
        webhook_results.webhook_obj.content = content
        webhook_results.webhook_obj.edit()
        logger.info(
            "Replaced jump links in message %s sent to %s",
            msg.raw_msg_carrier.id,
            self.get_channel(webhook_results.channel_id).name,
        )

    async def _unpackage_jump_links(
        self, jump_links: list[JumpLinkDetails]
    ) -> list[SearchRequestDetails]:
        """Get jump link details

        Parameters
        ----------
        jump_links: :class: `list[JumpLinkDetails]`
            A list of packaged jump links

        Returns
        -------
        :class: `list[SearchRequestDetails]`
            The list of details of the search requests
        """
        details = []
        for link in jump_links:
            linked_channel = self.get_channel(link.channel_id)
            if not linked_channel:
                logger.error(
                    "Try to search for a linked message in a non-existent channel %s.",
                    link.channel_id,
                )
                continue
            linked_message = await linked_channel.fetch_message(link.message_id)
            if not linked_message:
                logger.error(
                    "Try to search for a linked message in a non-existent message %s.",
                    link.message_id,
                )
                continue
            # find the first 100 characters of the message content, cut at nearest space
            if len(linked_message.content) > 100:
                content = " ".join(linked_message.content[:100].split(" ")[:-1])
            else:
                content = linked_message.content
            # remove any trailing numbers and \n
            content = re.sub(r"\d+$|\n", "", content)
            details.append(
                SearchRequestDetails(
                    url=link.url,
                    channel_name=linked_channel.name,
                    content=content,
                )
            )
        return details

    async def _search_linked_message(
        self, details: list[SearchRequestDetails], sent_msg_guild_id: int, sent_msg_id: int
    ) -> list[JumpLinkDetails]:
        """Search for linked messages in the master guild.

        Some posts contains links to previous messages, and the forward content will also contain
        these links. Since these linked messages are not visible to non-vip users, the links in the
        forwarded content leads to nowhere for these users.

        However, most likely, the linked messages have been reposted in the master guild already, so
        we can search for the linked message contents in the master guild and replace the links in
        the forwarded content.

        Parameters:
        -----------
        details: :class:`list[SearchRequestDetails]`
            A list of the search request details.
        sent_msg_guild_id: :class:`int`
            The ID of the discord server to search for the linked message contents.
        sent_msg_id: :class:`int`
            The ID of the message that contains the jump links.

        Returns:
        --------
        :class:`list[JumpLinkDetails]`
            The list of original jump link url, matched_channel ID and matched_message ID of the
            linked messages.
        """
        results = []
        for detail in details:
            guild = self.get_guild(sent_msg_guild_id)
            search_results = guild.search(content=detail.content, limit=5, oldest_first=False)
            try:
                similar_messages = [message async for message in search_results]
            except StopAsyncIteration:
                logger.error('Search returns 0 results for: "%s"', detail.content)
                continue
            if len(similar_messages) > 1:
                if similar_messages[0].id == sent_msg_id:
                    similar_messages.pop(0)
            channel_names = [message.channel.name for message in similar_messages]
            matches = get_close_matches(detail.channel_name, channel_names, n=1)
            if matches:
                matched_message = similar_messages[channel_names.index(matches[0])]
                results.append(
                    JumpLinkDetails(
                        url=detail.url,
                        channel_id=matched_message.channel.id,
                        message_id=matched_message.id,
                    )
                )
                logger.debug(
                    "Search returned a match for content %s in server %s in %s.",
                    detail.content,
                    guild.name,
                    matched_message.channel.name,
                )
            else:
                logger.warning(
                    "Search returned 0 result for content %s in server %s.",
                    detail.content,
                    guild.name,
                )
        return results

    async def _send_message_via_webhook(
        self, message: VFMessage, webhook_config: WebhookConfig
    ) -> list[SentWebhookResults | None]:
        """Send a webhook message to the webhook URL.

        Parameters:
        -----------
        message: :class:`VFMessage`
            The message to send.

        Returns:
        --------
        :class:`list[SentWebhookResults | None]`
            The list of SentWebhookResults if the message is sent successfully, otherwise
            :class:`None`.
        """
        webhook = DiscordWebhook(url=webhook_config.url)
        if (
            isinstance(message.raw_msg_carrier, selfcord.Message)
            and webhook_config.use_dynamic_avatar_name
        ):
            webhook.username = message.webhook_author_name
            webhook.avatar_url = message.raw_msg_carrier.author.display_avatar.url
        contents = message.get_contents()
        results = []
        for i, content in enumerate(contents):
            webhook.content = content
            if i == len(contents) - 1:
                webhook.embeds = message.embeds
            results.append(await self._execute_webhook(webhook))
        return results

    async def _execute_webhook(self, webhook: DiscordWebhook) -> SentWebhookResults | None:
        res = webhook.execute()
        if res.status_code == 429:
            retry_after = json.loads(res.content).get("retry_after")
            if retry_after:
                await asyncio.sleep(retry_after)
                return await self._execute_webhook(webhook)
        elif res.status_code != 200:
            logger.warning("Sent webhook message but unknown status code: %s", res.status_code)

        try:
            content = json.loads(res.content)
        except json.JSONDecodeError:
            logger.error("Failed to parse webhook response content: %s", res.content)
            return None
        channel_id = content.get("channel_id")
        if not channel_id or not channel_id.isdigit():
            logger.error("Webhook response content does not contain a channel ID.")
            return None
        channel = self.get_channel(int(channel_id))
        logger.info(
            "Sent webhook message to %s. Status code: %s.",
            channel.name if channel else channel_id,
            res.status_code,
        )
        return SentWebhookResults(int(channel_id), webhook)

    async def _forward_history_messages_by_channel(
        self, from_channel_id: int, after: datetime, before: datetime = None, interval: float = 0.1
    ):
        channel = self.get_channel(from_channel_id)
        if not channel:
            logger.error(
                "Try to forward history messages from a non-existent channel %s.", from_channel_id
            )
            return
        logger.debug("Forwarding history messages from %s.", channel.name)
        sent, count = 0, 0
        while True:
            try:
                hist = [
                    msg
                    async for msg in channel.history(
                        limit=100, after=after, before=before, oldest_first=True
                    )
                ]
            except selfcord.Forbidden:
                logger.error(
                    "Try to forward history messages from a channel %s but got a Forbidden error.",
                    channel.name,
                )
                return
            if len(hist) == 0:
                await asyncio.sleep(1)  # avoid rate limit
                break
            for message in hist:
                if await self.on_message(message, is_forward=True):
                    sent += 1
                    await asyncio.sleep(interval)
                count += 1
            if sent == 0:
                await asyncio.sleep(1)  # avoid rate limit

            after = hist[-1].created_at + timedelta(microseconds=1)

        logger.info("Forwarded %d / %d messages from %s.", sent, count, channel.name)

    async def _forward_history_messages(
        self, after: datetime, before: datetime = None, interval: float = 0.1
    ):
        async def forward_with_limit(
            channel_id: int, after: datetime, before: datetime, interval: float
        ):
            async with sem:
                await self._forward_history_messages_by_channel(channel_id, after, before, interval)

        tasks = []
        if self.forward_history_from_channels:
            for id_ in self.forward_history_from_channels:
                if isinstance(id_, str):
                    if id_.isdigit():
                        id_ = int(id_)
                    else:
                        id_ = self.config.config["channels"].get(id_, None)
                        if not id_:
                            logger.error("Channel %s not found in config.", id_)
                            continue
                tasks.append(asyncio.create_task(forward_with_limit(id_, after, before, interval)))
        else:
            for id_ in self.config.channel_list:
                tasks.append(asyncio.create_task(forward_with_limit(id_, after, before, interval)))
        await asyncio.gather(*tasks)
        logger.info("All history messages forwarded.")
        if self.forward_history_only:
            await self.close()
            print("Selfbot pull only completed.")

    def _get_guild_id_from_channel_id(self, channel_id: int | str) -> int | None:
        channel = self.get_channel(int(channel_id))
        if not channel:
            logger.error("Try to get guild id from a non-existent channel %s.", channel_id)
            return None
        return channel.guild.id
