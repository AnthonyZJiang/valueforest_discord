from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    import selfcord

logger = logging.getLogger(__name__)

PUSHPLUS_SEND_URL = "https://www.pushplus.plus/send"
PUSHPLUS_CONTENT_LIMIT = 8000


class PushPlusPlugin:
    async def notify(
        self,
        message: selfcord.Message,
        channel_config: dict,
        *,
        is_forward: bool = False,
    ) -> None:
        if is_forward:
            return

        destinations = channel_config.get("pushplus") or []
        if isinstance(destinations, dict):
            destinations = [destinations]
        if not destinations:
            return

        content = _format_content(message)
        if not content:
            return

        title = message.author.display_name or "Discord"
        channel_name = getattr(message.channel, "name", None)
        if channel_name:
            title = f"{channel_name} · {title}"
        if message.edited_at is not None:
            title = f"[编辑] {title}"
        title = title[:100]

        for dest in destinations:
            token = dest.get("token") if isinstance(dest, dict) else None
            channel = dest.get("channel", "app") if isinstance(dest, dict) else "app"
            if not token:
                logger.warning("PushPlus destination is missing a token.")
                continue
            await _send(message.id, title, content, token, channel)


async def _send(message_id: int, title: str, content: str, token: str, channel: str) -> None:
    payload = {
        "token": token,
        "title": title,
        "content": content,
        "channel": channel,
        "template": "txt",
    }
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(PUSHPLUS_SEND_URL, json=payload) as res:
                body = await res.text()
                if res.status != 200:
                    logger.warning(
                        "PushPlus HTTP %s for message %s: %s",
                        res.status,
                        message_id,
                        body,
                    )
                    return
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    logger.warning("PushPlus returned non-JSON: %s", body)
                    return
                if data.get("code") != 200:
                    logger.warning("PushPlus rejected message %s: %s", message_id, data)
                    return
                logger.info("Sent PushPlus notification for message %s.", message_id)
    except aiohttp.ClientError as exc:
        logger.warning("PushPlus request failed for message %s: %s", message_id, exc)


def _format_content(message: selfcord.Message) -> str:
    parts: list[str] = []
    text = (message.content or "").strip()
    if text:
        parts.append(text)
    if message.attachments:
        parts.append("\n".join(attachment.url for attachment in message.attachments))
    for embed in message.embeds:
        embed_bits: list[str] = []
        if embed.title:
            embed_bits.append(embed.title)
        if embed.description:
            embed_bits.append(embed.description)
        for field in embed.fields:
            name = field.name or ""
            value = field.value or ""
            if name and value:
                embed_bits.append(f"{name}: {value}")
            elif name or value:
                embed_bits.append(name or value)
        if embed.url:
            embed_bits.append(embed.url)
        if embed.image and embed.image.url:
            embed_bits.append(embed.image.url)
        if embed_bits:
            parts.append("\n".join(embed_bits))
    body = "\n\n".join(part for part in parts if part).strip()
    if len(body) > PUSHPLUS_CONTENT_LIMIT:
        return body[: PUSHPLUS_CONTENT_LIMIT - 1] + "…"
    return body
