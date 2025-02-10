import discord
from dotenv import load_dotenv
import os
from openai import OpenAI
import asyncio
from collections import deque
import requests
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader
from io import BytesIO
import base64

# Load environment variables
load_dotenv()

class Config:
    def __init__(self):
        self.DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
        self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
        self.BING_API_KEY = os.getenv('BING_API_KEY')
        self.RESPOND_CHANNEL_NAME = os.getenv('RESPOND_CHANNEL_NAME')
        self.HISTORY_LENGTH = 5
        self.SEARCH_RESULTS = 8
        self.MAX_DISCORD_LENGTH = 10000
        self.MAX_DISCORD_POST_ATTACHMENTS = 3
        self.MAX_DISCORD_POST_URLS = 3
        self.MAX_DISCORD_REPLY_LENGTH = 2000
        self.MAX_CONTENT_LENGTH = 5000
        self.REPUTABLE_DOMAINS = []
        self.GPT_MODEL = os.getenv('GPT_MODEL')
        self.AINAME = "もちお"
        self.CHARACTER = f'あなたは家族みんなのアシスタントの猫で、「{self.AINAME}」という名前です。ちょっといたずらで賢くかわいい小さな男の子の猫としてお話してね。語尾は だよ　とか可愛らしくしてください。語尾に にゃ にゃん をつけないでください。数式・表・箇条書きなどのドキュメントフォーマッティングはdiscordに表示できる形式がいいな'


class Analyst:
    def __init__(self, config, context):
        self.config = config
        self.context = context
        self.aiclient = OpenAI(api_key=self.config.OPENAI_API_KEY)

    def _parse_prompt(self, discIn):
        p_src = f"あなたはユーザーのプロンプトを分析し、主題、サブテーマ、関連キーワードを抽出するアシスタントです。"
        p_src = f"{p_src} 会話履歴を分析し、直近のユーザ入力への回答を満たす主題、サブテーマ、関連キーワードを抽出してください"
        messages = []
        messages.extend(self.context)
        messages.append({"role": "user", "content": f"{p_src}"})
        response = self.aiclient.chat.completions.create(
            model=self.config.GPT_MODEL,
            messages=messages
        )

        print("= parse_prompt ============================================")
        print(f"response: {response.choices[0].message.content}")
        print("= End of parse_prompt =====================================")

        return response.choices[0].message.content

    def _should_search(self, discIn):
        p_src = f"あなたはあなたは賢いアシスタントです。会話履歴を分析し、直近のユーザ入力への回答に、外部の最新情報が必要かどうかを判断してください。"
        p_src = f"{p_src} 判断の結果、外部の最新情報が必要なときは Yes の単語だけ返してください"
        messages = []
        messages.extend(self.context)
        messages.append({"role": "user", "content": f"{p_src}"})
        response = self.aiclient.chat.completions.create(
            model=self.config.GPT_MODEL,
            messages=messages
        )

        print("= should_search ============================================")
        print(f"response: {response.choices[0].message.content}")
        print("= End of should_search =====================================")
        return response.choices[0].message.content

    def _extract_keywords(self, parsed_text):
        p_src = f"あなたは解析されたプロンプト情報から簡潔な検索キーワードを抽出します。"
        p_src = f"会話履歴を踏まえつつ、このテキストから会話の目的を最も達成する検索キーワードを抽出してください。結果は検索キーワードのみを半角スペースで区切って出力してください:{parsed_text}"
        messages = []
        messages.extend(self.context)
        messages.append({"role": "user", "content": f"{p_src}"})
        response = self.aiclient.chat.completions.create(
            model=self.config.GPT_MODEL,
            messages=messages
        )

        print("= extract_keywords ============================================")
        print(f"response: {response.choices[0].message.content}")
        print("= End of extract_keywords =====================================")

        return response.choices[0].message.content

    def analyze(self, discIn):
        if "Yes" in self._should_search(discIn):
            print("searching... ---------------------------------------------")
            parsed_result = self._parse_prompt(discIn)
            keywords = self._extract_keywords(parsed_result)
            print(f"keyword: {keywords}")
            return keywords
        else:
            print("generating... --------------------------------------------")
            return None

class Researcher:
    def __init__(self, config, context):
        self.config = config
        self.context = context
        self.aiclient = OpenAI(api_key=self.config.OPENAI_API_KEY)

    def _search_bing(self, query, domains=None, count=None):
        if domains is None:
            domains = self.config.REPUTABLE_DOMAINS
        if count is None:
            count = self.config.SEARCH_RESULTS

        url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": self.config.BING_API_KEY}
        query = f"{query}"
        params = {"q": query, "count": count}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        search_data = response.json()
        search_data['urls'] = [result['url'] for result in search_data.get('webPages', {}).get('value', [])[:count]]

        print("Bing Search Results:")
        for result in search_data.get('webPages', {}).get('value', [])[:count]:
            print(f"Title: {result['name']}")
            print(f"URL: {result['url']}")
            print(f"Snippet: {result['snippet']}")
            print("---")
        return search_data

    async def _fetch_page_content_async(self, url):
        def blocking_fetch():
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                content_type = response.headers.get('Content-Type', '')

                if 'application/pdf' in content_type:
                    pdf_reader = PdfReader(BytesIO(response.content))
                    pdf_text = "".join(page.extract_text() for page in pdf_reader.pages)
                    return pdf_text[:self.config.MAX_CONTENT_LENGTH], "PDF"
                elif 'text/html' in content_type:
                    soup = BeautifulSoup(response.content, 'lxml')
                    text = soup.get_text(separator='\n', strip=True)
                    return text[:self.config.MAX_CONTENT_LENGTH], "HTML"
                elif content_type.startswith('image/'):
                    base64_img = base64.b64encode(response.content).decode('utf-8')
                    data_url = f"data:{content_type};base64,{base64_img}"
                    return data_url, "Image"
                else:
                    return None, "Unsupported"

            except Exception as e:
                print(f"Error fetching {url}: {str(e)}")
                return None, "Error"

        content, ctype = await asyncio.to_thread(blocking_fetch)
        return content, ctype

    async def _summarize_results_with_pages_async(self, search_results):
        content_list = []
        web_results = search_results.get('webPages', {}).get('value', [])[:self.config.SEARCH_RESULTS]

        tasks = [self._fetch_page_content_async(r['url']) for r in web_results]
        pages = await asyncio.gather(*tasks, return_exceptions=True)

        for (r, page_result) in zip(web_results, pages):
            title = r['name']
            snippet = r['snippet']
            url = r['url']

            if isinstance(page_result, Exception):
                content_list.append(f"タイトル: {title}\nURL: {url}\nスニペット:\n{snippet}\n")
                continue

            page_content, content_type = page_result
            if content_type in ("HTML", "PDF") and page_content:
                content_list.append(
                    f"タイトル: {title}\nURL: {url}\n内容:\n{page_content}\n"
                )
            else:
                content_list.append(
                    f"タイトル: {title}\nURL: {url}\nスニペット:\n{snippet}\n"
                )

        return "\n".join(content_list)

    async def summarize_results_async(self, search_results):
        snippets = await self._summarize_results_with_pages_async(search_results)

        p_src = (
            f"{self.config.CHARACTER}。あなたは検索結果を要約し、私の質問への回答を作成します。"
            " 会話履歴を踏まえつつ私が知りたいことの主旨を把握の上で、以下の検索結果を要約し回答を作ってください。"
            " 仮に検索結果が英語でも回答は日本語でお願いします。"
            " なお、回答がより高品質になるのならば、あなたの内部知識を加味して回答を作っても構いません。"
            " ただし、要約元にあった Title, URL は必ず元の形式で末尾に記入してください。"
            " URLを書くときはDiscordのAutoEmbedを防ぎたいので<>などで囲んでください。: "
            f"{snippets}"
        )

        def blocking_chat_completion():
            messages = [{"role": "system", "content": self.config.CHARACTER}]
            messages.extend(self.context)
            messages.append({"role": "user", "content": p_src})

            return self.aiclient.chat.completions.create(
                model=self.config.GPT_MODEL,
                messages=messages
            )

        response = await asyncio.to_thread(blocking_chat_completion)
        summary = response.choices[0].message.content

        titles = search_results.get('titles', [])
        urls = search_results.get('urls', [])
        sources = "\n".join(
            f"Source: {t} - {u}"
            for t, u in zip(titles, urls)
        )

        return f"{summary}\n\n{sources}"

    async def search_and_summarize(self, keywords):
        search_results = self._search_bing(keywords)
        summary = await self.summarize_results_async(search_results)
        return summary

    def just_call_openai(self, discIn):
        messages = [{"role": "system", "content": f"{self.config.CHARACTER}"}]
        messages.extend(self.context)
        completion = self.aiclient.chat.completions.create(
            model=self.config.GPT_MODEL,
            messages=messages
        )
        return completion.choices[0].message.content


class Mochio(discord.Client):
    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config
        self.context = deque(maxlen=self.config.HISTORY_LENGTH)
        self.analyst = Analyst(self.config, self.context)
        self.researcher = Researcher(self.config, self.context)

    async def on_ready(self):
        print(f'Logged in as {self.user.name}({self.user.id})')

    async def on_message(self, message):
        if (message.author.id == self.user.id
                or message.channel.name not in self.config.RESPOND_CHANNEL_NAME.split(',')):
            return

        if message.content.startswith('!hello'):
            await message.channel.send('Hello!')
        else:
            async with message.channel.typing():
                discIn, img_url = await self._process_message(message)
                response = await self._ai_respond(discIn, img_url)
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
        if img_url:
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
            if msg:
                discIn.append({"role": "user", "content": msg})

        self.context.extend(discIn)
        return discIn, img_url

    async def _ai_respond(self, discIn, img):
        try:
            if img:
                print("Skipping search and calling OpenAI directly.")
                result = self.researcher.just_call_openai(discIn)
            else:
                keywords = self.analyst.analyze(discIn)
                if keywords:
                    result = await self.researcher.search_and_summarize(keywords)
                else:
                    result = self.researcher.just_call_openai(discIn)
            return result
        except Exception as e:
            print(f"API Call Error: {str(e)}")
            return f"Error: {str(e)}"

    async def _send_long_message(self, channel: discord.TextChannel, content: str):
        for i in range(0, len(content), self.config.MAX_DISCORD_REPLY_LENGTH):
            await channel.send(content[i: i + self.config.MAX_DISCORD_REPLY_LENGTH])

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

