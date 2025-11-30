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
from colleagues.auditor import Auditor

class Mochio(discord.Client):
    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self.context = deque(maxlen=self.config.HISTORY_LENGTH)  # チャンネル用の共通履歴
        self.dm_contexts = {}  # DM用のユーザーごとの履歴
        self.analyst = Analyst(self.config, self.context)
        self.researcher = Researcher(self.config, self.context)
        self.auditor = Auditor(config=self.config, discord_client=self)  # ログ記録・精神状態監視用
        self.last_message_time = None
        self.dm_last_message_times = {}  # DM用のユーザーごとの最終メッセージ時刻

    async def on_ready(self):
        print(f'Logged in as {self.user.name}({self.user.id})')

    async def on_message(self, message):
        # 自分自身のメッセージは無視
        if message.author.id == self.user.id:
            return

        # DMかどうかを判定
        is_dm = isinstance(message.channel, discord.DMChannel)

        if is_dm:
            # DMの場合：ボットと同じサーバーに所属しているユーザーのみ応答
            is_shared_guild = any(
                message.author in guild.members for guild in self.guilds
            )
            if not is_shared_guild:
                return
            
            # DM用のユーザーごとの履歴を取得または作成
            user_id = message.author.id
            if user_id not in self.dm_contexts:
                self.dm_contexts[user_id] = deque(maxlen=self.config.HISTORY_LENGTH)
            current_context = self.dm_contexts[user_id]
            
            # DM用の最終メッセージ時刻チェック
            if user_id in self.dm_last_message_times:
                elapsed = message.created_at - self.dm_last_message_times[user_id]
                if elapsed > timedelta(hours=1):
                    print(f"DM context cleared for user {user_id} due to inactivity over 1 hour.")
                    self.auditor.log_context_clear("dm", user_id, "inactivity over 1 hour")
                    current_context.clear()
            self.dm_last_message_times[user_id] = message.created_at
        else:
            # サーバーチャンネルの場合：設定されたチャンネル名のみ応答
            if message.channel.name not in self.config.RESPOND_CHANNEL_NAME.split(','):
                return
            
            current_context = self.context
            
            # チャンネル用の最終メッセージ時刻チェック
            if self.last_message_time:
                elapsed = message.created_at - self.last_message_time
                if elapsed > timedelta(hours=1):
                    print("Channel context cleared due to inactivity over 1 hour.")
                    self.auditor.log_context_clear("channel", reason="inactivity over 1 hour")
                    current_context.clear()
            self.last_message_time = message.created_at

        # 現在の会話用にanalystとresearcherのcontextを切り替え
        self.analyst.context = current_context
        self.researcher.context = current_context

        if message.content.startswith('!hello'):
            await message.channel.send('Hello!')
        else:
            async with message.channel.typing():
                # ソース種別を判定
                source = "dm" if is_dm else "channel"
                
                discIn, img_url = await self._process_message(message)
                
                # ユーザーメッセージをログに記録
                self.auditor.log_message(source, message.author.id, message.author.name, message.content)
                
                # 精神状態チェックをバックグラウンドで実行（メインの応答をブロックしない）
                asyncio.create_task(
                    self.auditor.audit_mental_state_async(
                        source, 
                        message.author.id, 
                        message.author.name,
                        message.content,
                        list(current_context)
                    )
                )

                try:
                    if img_url:
                        print("Skipping search and calling OpenAI directly.")
                        # APIコールをログに記録
                        api_messages = [{"role": "system", "content": self.config.CHARACTER}]
                        api_messages.extend(self.researcher.context)
                        self.auditor.log_api_call(source, message.author.id, message.author.name, api_messages)
                        response = self.researcher.just_call_openai(discIn)
                    else:
                        keywords = self.analyst.analyze(discIn)
                        if keywords:
                            response = await self.researcher.search_and_summarize(keywords)
                        else:
                            # APIコールをログに記録
                            api_messages = [{"role": "system", "content": self.config.CHARACTER}]
                            api_messages.extend(self.researcher.context)
                            self.auditor.log_api_call(source, message.author.id, message.author.name, api_messages)
                            response = self.researcher.just_call_openai(discIn)
                except Exception as e:
                    print(f"API Call Error: {str(e)}")
                    return f"Error: {str(e)}"

                # ボット応答をログに記録
                self.auditor.log_response(source, message.author.id, message.author.name, response)
                
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

        # 現在のcontextに追加（analyst/researcherで切り替え済みのcontextを使用）
        self.analyst.context.extend(discIn)
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

