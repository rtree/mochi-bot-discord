import discord
from dotenv import load_dotenv
import os
from openai import OpenAI
import asyncio
from collections import deque
import requests
from bs4 import BeautifulSoup
import lxml
from PyPDF2 import PdfReader
from io import BytesIO

# Load environment variables
load_dotenv()
DISCORD_BOT_TOKEN    = os.getenv('DISCORD_BOT_TOKEN')
OPENAI_API_KEY       = os.getenv('OPENAI_API_KEY')
BING_API_KEY         = os.getenv('BING_API_KEY')
RESPOND_CHANNEL_NAME = os.getenv('RESPOND_CHANNEL_NAME')
HISTORY_LENGTH       = 10
SEARCH_RESULTS       = 3
#GPT_MODEL            = 'gpt-4-turbo-preview'
GPT_MODEL            = os.getenv('GPT_MODEL')
AINAME               = "もちお"
#CHARACTER            = 'あなたは家族みんなのアシスタントの猫です。ちょっといたずらで賢くかわいい小さな男の子の猫としてお話してね。語尾は にゃ　とか　だよ　とか可愛らしくしてください'
#CHARACTER            = 'あなたは家族みんなのアシスタントの猫です。ただ、語尾ににゃをつけないでください。むしろソフトバンクCMにおける「お父さん」犬のようにしゃべってください。たまにもののけ姫のモロのようにしゃべってもよいです'
CHARACTER            = f'あなたは家族みんなのアシスタントの猫で、「{AINAME}」という名前です。ちょっといたずらで賢くかわいい小さな男の子の猫としてお話してね。語尾は だよ　とか可愛らしくしてください。語尾ににゃをつけないでください。数式はdiscordに表示できる形式がいいな'
client = OpenAI(api_key=OPENAI_API_KEY)

# Define the intents
intents = discord.Intents.all()
intents.messages = True
intents.guilds = True
intents.message_content = True

# -------------------------------- Search related ----------------------------

# プロンプトを解析して主題、サブテーマ、キーワードを抽出
def parse_prompt(discIn):
    p_src = f"あなたはユーザーのプロンプトを分析し、主題、サブテーマ、関連キーワードを抽出するアシスタントです。"
    p_src = f"{p_src} 会話履歴を分析し、この入力の一つ前のユーザ入力への回答を満たす主題、サブテーマ、関連キーワードを抽出してください"
    messages = []
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": f"{p_src}"})
    print("===================messages===================")
    for conv in messages:
        print(conv)
    response = client.chat.completions.create(
        model=GPT_MODEL,
        messages=messages
    )
    return response.choices[0].message.content

# 検索の必要性を判断
def should_search(discIn):
    #if any(keyword in msg for keyword in ["出典", "URL", "調べ", "検索", "最新", "具体的","実際","探","実情報","search","find"]):
    #    return "Yes"
    p_src = f"あなたはあなたは賢いアシスタントです。会話履歴を分析し、この入力の一つ前のユーザ入力への回答に、外部の最新情報が必要かどうかを判断してください。"
    p_src = f"{p_src} 判断の結果、外部の最新情報が必要なときは Yes の単語だけ返してください"
    messages = []
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": f"{p_src}"})
    response = client.chat.completions.create(
        model=GPT_MODEL,
        messages=messages
    )
    return response.choices[0].message.content

# キーワードを抽出
def extract_keywords(parsed_text):
    #response = client.chat.completions.create(
    #    model=GPT_MODEL,
    #    messages=[
    #        {"role": "user", "content": "あなたは解析されたプロンプト情報から簡潔な検索キーワードを抽出します。"},
    #        {"role": "user", "content": f"このテキストから簡潔な検索キーワードを抽出してください。抽出結果は検索キーワードだけを一つ一つ半角スペース区切りで出力してください。また抽出は英語でお願いします: {parsed_text}"}
    #    ]
    #)
    #return response.choices[0].message.content
    p_src = f"あなたは解析されたプロンプト情報から簡潔な検索キーワードを抽出します。"
    p_src = f"会話履歴を踏まえつつ、このテキストから会話の目的を最も達成する簡潔な検索キーワードを抽出してください。抽出結果は検索キーワードだけを一つ一つ半角スペース区切りで出力してください。:{parsed_text}"
    messages = []
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": f"{p_src}"})
    response = client.chat.completions.create(
        model=GPT_MODEL,
        messages=messages
    )
    return response.choices[0].message.content


# Bing Search APIを使用して検索
def search_bing(query, count=SEARCH_RESULTS):
    url = "https://api.bing.microsoft.com/v7.0/search"
    headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
    params = {"q": query, "count": count}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    search_data = response.json()
    # 検索結果に情報源のURLを追加
    search_data['urls'] = [result['url'] for result in search_data['webPages']['value'][:SEARCH_RESULTS]]

    print("Bing Search Results:")
    for result in search_data['webPages']['value'][:count]:
        print(f"Title: {result['name']}")
        print(f"URL: {result['url']}")
        print(f"Snippet: {result['snippet']}")
        print("---")

    return search_data


# ページ内容を取得する関数
def fetch_page_content(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', '')

        # PDFの場合
        if 'application/pdf' in content_type:
            pdf_reader = PdfReader(BytesIO(response.content))
            pdf_text = ""
            for page in pdf_reader.pages:
                pdf_text += page.extract_text()
            return pdf_text, "PDF"

        # HTMLの場合
        elif 'text/html' in content_type:
            soup = BeautifulSoup(response.content, 'lxml')
            return soup.get_text(separator='\n', strip=True), "HTML"

        # 対応していないコンテンツタイプ
        else:
            return None, "Unsupported"
    except Exception as e:
        print(f"Error fetching {url}: {str(e)}")
        return None, "Error"

# 検索結果を要約する関数（ページ内容も含む）
def summarize_results_with_pages(search_results):
    # すべてのコンテンツ（ページ内容またはスニペット）を格納するリスト
    content_list = []
    for result in search_results['webPages']['value'][:5]:
        title = result['name']
        snippet = result['snippet']
        url = result['url']
        # ページ内容を取得
        page_content, content_type = fetch_page_content(url)
        if content_type in ["HTML", "PDF"] and page_content:
            # HTMLまたはPDFから取得した内容を追加
            content_list.append(f"タイトル: {title}\nURL: {url}\n内容:\n{page_content}\n")
        else:
            # HTMLやPDF以外の場合はスニペットを追加
            content_list.append(f"タイトル: {title}\nURL: {url}\nスニペット:\n{snippet}\n")
    # すべてのコンテンツを結合
    combined_content = "\n".join(content_list)
    return combined_content


# 検索結果を要約
def summarize_results(search_results):
    #snippets = "\n".join([result['snippet'] for result in search_results['webPages']['value'][:5]])
    snippets = summarize_results_with_pages(search_results)

    p_src = f"あなたは検索結果を要約し、私の質問への回答を作成します。"
    p_src = f"{p_src} 会話履歴を踏まえつつ私が知りたいことの主旨を把握の上で、以下の検索結果を要約し回答を作ってください。仮に検索結果が英語でも回答は日本語でお願いします: {snippets}"
    messages = [{"role": "system", "content": f"{CHARACTER}"}]
    messages.extend(conversation_history)
    messages.append({"role": "user", "content": f"{p_src}"})
    response = client.chat.completions.create(
        model=GPT_MODEL,
        messages=messages
    )
    #return response.choices[0].message.content
    #response = client.chat.completions.create(
    #    model=GPT_MODEL,
    #    messages=[
    #        {"role": "user", "content": f"{CHARACTER} あなたは検索結果を要約し、簡潔な回答を作成します。"},
    #        {"role": "user", "content": f"以下の検索スニペットを要約してください。: {snippets}"}
    #    ]
    #)
    summary = response.choices[0].message.content
    urls = search_results.get('urls', [])
    sources = "\n".join([f"Source: {url}" for url in urls])
    return f"{summary}\n\n{sources}"

#------- End of search part ----------------------------------------

# Initialize a deque with a maximum length to store conversation history
conversation_history = deque(maxlen=HISTORY_LENGTH)  # Adjust the size as needed

def search_or_call_openai(discIn,img):
    if img:
        result         = just_call_openai(discIn)
    else:
        if "Yes" in should_search(discIn):
            print(f"searching... ---------------------------------------------")
            parsed_result  = parse_prompt(discIn)
            keywords       = extract_keywords(parsed_result)
            print(f"keyword: {keywords}")
            search_results = search_bing(keywords)
            result         = summarize_results(search_results)
        else:
            print(f"generating... --------------------------------------------")
            result         = just_call_openai(discIn)
    return result

def just_call_openai(discIn):
    #-- Call OpenAI --
    messages   = [{"role": "system", "content": f"{CHARACTER}"}]
    messages.extend(conversation_history)
    completion = client.chat.completions.create(
        model=GPT_MODEL,
        messages=messages
    )
    return completion.choices[0].message.content

#def create_message_stack(msg,img,prompt):
#    messages      = []
#    if img or msg or prompt:
#        messages.extend(conversation_history)
#        messages.extend(prompt)
#        if msg:
#            if len(msg) > 200:
#                msg = msg[:200]  # Truncate the request if it exceeds 200 characters
#        if img:
#            messages.append( {"role": "user", "content":
#                             [
#                                {"type"     : "text"     , "text"     : msg           },
#                                {"type"     : "image_url", "image_url": {"url": img } }
#                             ]
#                            })
#            # messages.append( {"role": "user", "content": f"{msg}\n（画像URL: {img}）"})
#        else:
#            if msg:
#                messages.append( {"role": "user", "content": msg})
#    return messages

async def ai_respond(discIn,img):
    try:
        #result = just_call_openai(discIn)
        result = search_or_call_openai(discIn,img)
        return result

    except Exception as e:
        print(f"API Call Error: {str(e)}")  # Debug print for API errors
        return f"Error: {str(e)}"

class MyClient(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user.name}({self.user.id})')

    async def on_message(self, message):
        # Don't respond to ourselves or messages outside the specified channel
        if message.author.id == self.user.id or message.channel.name not in RESPOND_CHANNEL_NAME.split(','):
            return

        if message.content.startswith('!hello'):
            await message.channel.send('Hello!')
        else:
            msg = message.content
            img = message.attachments[0] if message.attachments else None
            if img:
                img = img.url if img.content_type.startswith('image/')  else None
            print(f"-User input------------------------------------------------------------------")
            print(f"Message content: '{msg}'")  # Directly print the message content
            print(f"Image          : '{img}'")  # Directly print the message content

            # ------ Add user input to conversation history
            discIn = []
            if msg and len(msg) > 200:
                msg = msg[:200]
            if img:
                discIn.append({"role": "user", "content": f"{msg}\n(画像URL: {img})"})
            else:
                if msg:
                    discIn.append({"role": "user", "content": msg})
            conversation_history.extend(discIn)
            response = await ai_respond(discIn,img)
            await message.channel.send(response)

            # ------ Add assistant output to conversation history
            conversation_history.append({"role": "assistant", "content": response})

            #conversation_history.append(f"ユーザ（{message.author}): {msg}\n")
            #if img:
            #    conversation_history.append(f"ユーザ（{message.author}): Image_Url {img}\n")
            #conversation_history.append(f"AI({AINAME}): {response}\n")
            print("-Dump of conversation--------------------------------------------------------")
            for conv in conversation_history:
                print(conv) 

# Initialize the client with the specified intents
d_client = MyClient(intents=intents)
d_client.run(DISCORD_BOT_TOKEN)

