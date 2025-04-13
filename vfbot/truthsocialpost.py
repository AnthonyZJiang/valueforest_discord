import logging
import requests
import io
from bs4 import BeautifulSoup
from quickimgurpy import ImgurClient
import discord
from .utils import azure_translate

logger = logging.getLogger(__name__)
DISCORD_FILE_LIMIT = 10 * 1024 * 1024  # 10MB in bytes


def add_line_prefix(text: str, prefix: str) -> str:
    lines = text.split('\n')
    if len(lines) == 1:
        return prefix + text
    result = []
    for line in lines:
        if line.strip():
            result.append(prefix + line)
        else:
            result.append(prefix + ' ᠎')  # do nothing for empty lines
    return '\n'.join(result)


def build_line(text: str, prefix='', line_break=True, single_line_break=False):
    if not text:
        return ''
    if prefix:
        text = add_line_prefix(text, prefix)
    if not line_break:
        return text
    if single_line_break:
        return text + '\n'
    return text + '\n\n'


def build_multi_line(text: str, prefix='', line_break=True, single_line_break=False):
    if not text:
        return ''
    text = text.split('\n')
    if not line_break:
        return ('\n'+prefix).join(text)
    if single_line_break:
        return ('\n'+prefix).join(text) + '\n'
    return ('\n'+prefix).join(text) + '\n\n'


def parse_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    for a in soup.find_all('a'):
        href = a.get('href', '')
        text = a.get_text().strip()
        if text.startswith('http'):
            text = 'external link'
        markdown_link = f'[{text}]({href})'
        a.replace_with(markdown_link)

    paragraphs = soup.find_all('p')
    paragraph_texts = []
    quote_in_line = None
    header_card = None
    for p in paragraphs:
        spans = p.find_all('span')
        for span in spans:
            if 'h-card' in span.get('class', []):
                if header_card:
                    logger.error(
                        f"Multiple header cards found in {html_content} Skipping...")
                else:
                    header_card = span.get_text()
                span.replace_with("")
            elif 'quote-inline' in span.get('class', []):
                if quote_in_line:
                    logger.error(
                        f"Multiple quote in lines found in {html_content}. Skipping...")
                else:
                    url = span.get_text()
                    url = url[url.find('http'):]
                    user = url[url.find('users/')+6:url.find('/statuses')]
                    quote_in_line = f'[{user}]({url})'
                span.replace_with("")
            else:
                span.unwrap()

        for br in p.find_all('br'):
            br.replace_with('\n')

        if not header_card:
            p_text = p.get_text()
            p_text = p_text.strip()
            if p_text:
                p_text = p_text.replace('â€™', '\'').replace('Â', '').replace(
                    "â€œ", "“").replace("â€", "”").replace("â€™", "'").replace("â€¦", "...")
                paragraph_texts.append(p_text)

    return {
        'paragraph_texts': paragraph_texts,
        'quote_in_line': quote_in_line,
        'header_card': header_card
    }


class TruthPostBuilder:
    def __init__(self):
        self.imgur = ImgurClient()

    def build_post(self, status: dict):
        discord_attachments, content_attachments = self.convert_attachments(
            status)
        status['content'] = self.build_post_content(
            status, content_attachments)
        status['discord_attachments'] = discord_attachments
        return status

    def build_post_content(self, status: dict, content_attachments: list):
        main_contents = parse_html(status['content'])

        header_text, header_text_en, footer_text, footer_text_en = '', '', '', ''
        if main_contents['header_card']:
            header_text = '转发自 ' + main_contents['header_card']
            header_text_en = 'Reposted from ' + main_contents['header_card']
        if main_contents['quote_in_line']:
            footer_text = '引用自 ' + main_contents['quote_in_line']
            footer_text_en = 'Quoted from ' + main_contents['quote_in_line']

        reblog_texts, quoted_texts = [], []
        if status['reblog']:
            reblog_texts = parse_html(status['reblog']['content'])[
                'paragraph_texts']
        if status['quote']:
            quoted_texts = parse_html(status['quote']['content'])[
                'paragraph_texts']

        attached_texts = '\n\n'.join(reblog_texts) or '\n\n'.join(quoted_texts)

        # No real contents
        if not main_contents['paragraph_texts'] and not reblog_texts and not quoted_texts:
            return (header_text or footer_text) + ' ｜ '.join(content_attachments)

        joined_main_text = '\n\n'.join(main_contents['paragraph_texts'])
        texts_to_translate = []
        texts_to_translate.append({'text': joined_main_text})
        texts_to_translate.append({'text': '\n\n'.join(reblog_texts)})
        texts_to_translate.append({'text': '\n\n'.join(quoted_texts)})

        try:
            translation = azure_translate(texts_to_translate)
        except Exception as e:
            logger.error(f"Error translating content: {e}")
            translation = None
        error_text = translation.get('error', '')
        # Translation failed, return original text
        if translation is None or error_text:
            return '\n-# :small_orange_diamond:Translation failed\n' + (
                build_line(error_text, ': ') +
                build_line(header_text, '-# ') +
                joined_main_text +
                build_line(footer_text, '-# ') +
                attached_texts +
                ' ｜ '.join(content_attachments)
            ).rstrip()

        main_text_translation = translation['main_text']
        reblog_translation = translation['reblog_text']
        quote_translation = translation['quoted_text']
        text = (
            build_line(header_text, '\n-# ', single_line_break=True) +
            build_line(main_text_translation) +
            build_line(footer_text, '-# ', single_line_break=True) +
            build_line(reblog_translation, '> ') +
            build_line(quote_translation, '> ')
        ).rstrip()
        original_text = (
            build_line(header_text_en, '-# ', single_line_break=True) +
            build_line("\n\n".join(main_contents['paragraph_texts']), '-# ') +
            build_line(footer_text_en, '-# ', single_line_break=True) +
            build_line("\n\n".join(reblog_texts), "> -# ", line_break=False) +
            build_line("\n\n".join(quoted_texts), "> -# ", line_break=False)
        ).rstrip()
        if original_text:
            text = text + '\n\n-# :small_blue_diamond:原文：\n' + original_text

        attachments_length = len(build_line(' ｜ '.join(content_attachments)))
        text_length_limit = 1800-attachments_length
        # limit character length to 1800
        if len(text) < text_length_limit:
            return text + build_line(' ｜ '.join(content_attachments), '\n\n').rstrip()
        else:
            return text[:text_length_limit] + '...\n\n' + build_line(' ｜ '.join(content_attachments)) + '-# :small_orange_diamond: Word limit reached'

    def convert_attachments(self, status: dict):
        if not status['media_attachments'] and not (
            status['reblog'] and status['reblog']['media_attachments']) and not (
            status['quote'] and status['quote']['media_attachments']
        ):
            return [], []

        def get_attachment_markup(attachment: dict):
            if attachment['type'] == 'video':
                return f':small_blue_diamond: [Click here to watch the video]({attachment["url"]})'
            else:
                return f':small_blue_diamond: [Click here to view the image]({attachment["url"]})'

        discord_attachments = []
        content_attachments = []
        media_attachments = status['media_attachments']
        if status['reblog']:
            media_attachments += status['reblog']['media_attachments']
        if status['quote']:
            media_attachments += status['quote']['media_attachments']

        for attachment in media_attachments:
            try:
                file_url = attachment['url']
                file_ext = file_url.split('.')[-1].lower()
                filename = f"media.{file_ext}"

                response = requests.get(file_url)
                response.raise_for_status()
                file_data = response.content

                imgur_url = None
                print(len(file_data)/1024/1024)
                if len(file_data) > DISCORD_FILE_LIMIT:
                    if attachment['type'] in ['image', 'video']:
                        imgur_url = self.upload_to_imgur(
                            file_data, attachment['type'])
                    content_attachments.append(
                        imgur_url or get_attachment_markup(attachment))
                else:
                    # File is small enough for Discord
                    discord_file = discord.File(
                        fp=io.BytesIO(file_data),
                        filename=filename
                    )
                    discord_attachments.append(discord_file)

            except Exception as e:
                logger.error(
                    f"Failed to handle attachment {file_url}: {str(e)}")
                content_attachments.append(get_attachment_markup(attachment))

        return discord_attachments, content_attachments

    def upload_to_imgur(self, file_data: bytes, file_type: str):
        try:
            if file_type == 'image':
                resp = self.imgur.upload_image(file_data, force_base64=True)
            elif file_type == 'video':
                resp = self.imgur.upload_video(file_data, force_base64=True)
            if resp['status'] == 200:
                return resp['data']['link']
        except Exception as e:
            logger.error(f"Error uploading to imgur: {e}")

        return None
