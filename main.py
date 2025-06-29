import discord
import asyncio
from collections import deque
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader
from io import BytesIO
import requests
from config import Config
from colleagues.analyst import Analyst
#from colleagues.researcher import Researcher
from colleagues.researcherG import Researcher

class Mochio(discord.Client):
    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self.context = deque(maxlen=self.config.HISTORY_LENGTH)
        self.analyst = Analyst(self.config, self.context)
        self.researcher = Researcher(self.config, self.context)
        self.last_message_time = None

    async def on_ready(self):
        print(f'Logged in as {self.user.name}({self.user.id})')

    async def on_message(self, message):
        if (message.author.id == self.user.id
                or message.channel.name not in self.config.RESPOND_CHANNEL_NAME.split(',')):
            return

        if self.last_message_time:
            elapsed = message.created_at - self.last_message_time
            if elapsed > timedelta(hours=1):
                print("Context cleared due to inactivity over 1 hour.")
                self.context.clear()

        self.last_message_time = message.created_at

        if message.content.startswith('!hello'):
            await message.channel.send('Hello!')
        else:
            async with message.channel.typing():
                discIn, img_url = await self._process_message(message)

                try:
                    if img_url:
                        print("Skipping search and calling OpenAI directly.")
                        response = self.researcher.just_call_openai(discIn)
                    else:
                        keywords = self.analyst.analyze(discIn)
                        if keywords:
                            response = await self.researcher.search_and_summarize(keywords)
                        else:
                            response = self.researcher.just_call_openai(discIn)
                except Exception as e:
                    print(f"API Call Error: {str(e)}")
                    return f"Error: {str(e)}"

                await self._send_long_message(message.channel, response)

    async def _process_message(self, message):
        msg = message.content
        img_url = None

        attached_text_list = []
        for attachment in message.attachments[:self.config.MAX_DISCORD_POST_ATTACHMENTS]:
            if (attachment.content_type and attachment.content_type.startswith('image/')):
                img_url = attachment.url
            elif attachment.content_type and (
                    attachment.content_type.startswith('application/pdf')
                    or attachment.content_type.startswith('text/html')):
                parsed_content, ctype = await self._parse_discord_attachment(attachment)
                if parsed_content:
                    attached_text_list.append(
                        f"\n[Content from attached {ctype} file '{attachment.filename}']:\n{parsed_content}\n"
                    )

        urls = [word for word in msg.split() if word.startswith('http')]
        if len(urls) > self.config.MAX_DISCORD_POST_URLS + 1:
            msg += f"\n[Note: {len(urls) - self.config.MAX_DISCORD_POST_ATTACHMENTS} URLs truncated]"
            urls = urls[:self.config.MAX_DISCORD_POST_ATTACHMENTS]

        extracted_content = []
        tasks = [self.researcher._fetch_page_content_async(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for url, res in zip(urls, results):
            if isinstance(res, Exception):
                continue
            content, content_type = res

            if content and (content_type in ["PDF", "HTML"]):
                extracted_content.append(
                    f"\n[Content from {url} ({content_type})]: {content[:self.config.MAX_CONTENT_LENGTH]}..."
                )
            elif content and (content_type in ["Image"]):
                img_url = url

        msg = msg[:self.config.MAX_DISCORD_LENGTH]
        msg += ''.join(extracted_content)
        msg += ''.join(attached_text_list)

        print("-User input------------------------------------------------------------------")
        print(f"  Message content: '{msg}'")
        print(f"  Image          : '{img_url}'")

        discIn = []
        if not msg:
            msg = ""
        if img_url and await self._validate_image_url(img_url):
            discIn.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"{msg}"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"{img_url}",
                            },
                        }
                    ],
                },
            )
        else:
            if img_url:
                print(f"Discarding inaccessible image URL: {img_url}")
            if msg:
                discIn.append({"role": "user", "content": msg})

        self.context.extend(discIn)
        return discIn, img_url

    async def _send_long_message(self, channel: discord.TextChannel, content: str):
        for i in range(0, len(content), self.config.MAX_DISCORD_REPLY_LENGTH):
            await channel.send(content[i: i + self.config.MAX_DISCORD_REPLY_LENGTH])

    async def _validate_image_url(self, url: str) -> bool:
        """Check whether the image URL is accessible."""
        def blocking_check():
            try:
                resp = requests.get(url, timeout=5)
                resp.raise_for_status()
                return resp.headers.get("Content-Type", "").startswith("image/")
            except Exception as e:
                print(f"Image URL validation failed for {url}: {e}")
                return False

        return await asyncio.to_thread(blocking_check)

    async def _parse_discord_attachment(self, attachment: discord.Attachment):
        if not attachment.content_type:
            return None, None

        file_bytes = await attachment.read()

        if attachment.content_type.startswith("application/pdf"):
            try:
                pdf_reader = PdfReader(BytesIO(file_bytes))
                pdf_text = "".join(page.extract_text() for page in pdf_reader.pages)
                return pdf_text[:self.config.MAX_CONTENT_LENGTH], "PDF"
            except Exception as e:
                print(f"Error reading PDF: {e}")
                return None, None

        elif attachment.content_type.startswith("text/html"):
            try:
                soup = BeautifulSoup(file_bytes, "lxml")
                text = soup.get_text(separator='\n', strip=True)
                return text[:self.config.MAX_CONTENT_LENGTH], "HTML"
            except Exception as e:
                print(f"Error reading HTML: {e}")
                return None, None

        return None, None

# --------------------------------- Main ---------------------------------
config = Config()
intents = discord.Intents.all()
intents.messages = True
intents.guilds = True
intents.message_content = True
d_client = Mochio(config=config, intents=intents)
d_client.run(config.DISCORD_BOT_TOKEN)

