import discord
from dotenv import load_dotenv
import os
from openai import OpenAI
import asyncio
from collections import deque
import requests

# Load environment variables
load_dotenv()
DISCORD_BOT_TOKEN    = os.getenv('DISCORD_BOT_TOKEN')
OPENAI_API_KEY       = os.getenv('OPENAI_API_KEY')
BING_API_KEY         = os.getenv('BING_API_KEY')
RESPOND_CHANNEL_NAME = os.getenv('RESPOND_CHANNEL_NAME')
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
def parse_prompt(msg,img):
    prompt = "あなたはユーザーのプロンプトを分析し、主題、サブテーマ、関連キーワードを抽出するアシスタントです。"
    prompt = f"{prompt} 以下のプロンプトを分析し、主題、サブテーマ、関連キーワードを抽出してください:"
    messages = create_message_stack(msg,img,prompt)
    response = client.chat.completions.create(
        model=GPT_MODEL,
        messages=messages
    )
    return response.choices[0].message.content

# 検索の必要性を判断
def should_search(msg,img):
    if any(keyword in msg for keyword in ["出典", "URL", "探してほしい", "検索", "最新", "具体的"]):
        return "Yes"
    prompt = "あなたはユーザーのクエリに基づき、ウェブ検索が必要かどうかを判断するツールです。"
    prompt = f"{prompt} 以下のクエリについて、最新の情報や具体的な回答を得るためにウェブ検索が必要かどうかを判断してください。判断の結果検索が必要なときは Yes の単語だけ返してください:"
    messages = create_message_stack(msg,img,prompt)
    response = client.chat.completions.create(
        model=GPT_MODEL,
        messages=messages
    )
    return response.choices[0].message.content

# キーワードを抽出
def extract_keywords(parsed_text):
    response = client.chat.completions.create(
        model=GPT_MODEL,
        messages=[
            {"role": "user", "content": "あなたは解析されたプロンプト情報から簡潔な検索キーワードを抽出します。"},
            {"role": "user", "content": f"このテキストから簡潔な検索キーワードを抽出してください。抽出結果は検索キーワードだけを一つ一つ半角スペース区切りで出力してください: {parsed_text}"}
        ]
    )
    return response.choices[0].message.content


# Bing Search APIを使用して検索
def search_bing(query, count=5):
    url = "https://api.bing.microsoft.com/v7.0/search"
    headers = {"Ocp-Apim-Subscription-Key": BING_API_KEY}
    params = {"q": query, "count": count}
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    search_data = response.json()
    # 検索結果に情報源のURLを追加
    search_data['urls'] = [result['url'] for result in search_data['webPages']['value'][:5]]

    print("Bing Search Results:")
    for result in search_data['webPages']['value'][:count]:
        print(f"Title: {result['name']}")
        print(f"URL: {result['url']}")
        print(f"Snippet: {result['snippet']}")
        print("---")

    return search_data

# 検索結果を要約
def summarize_results(search_results):
    snippets = "\n".join([result['snippet'] for result in search_results['webPages']['value'][:5]])
    
    prompt = f"{CHARACTER} あなたは検索結果を要約し、簡潔な回答を作成します。"
    prompt = f"{prompt} 以下の検索スニペットを要約してください。: {snippets}"
    propmt = f"{prompt} さらに、必要に応じて以下の文脈も考慮してください:"
    messages = create_message_stack("","",prompt)
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
conversation_history = deque(maxlen=20)  # Adjust the size as needed

def search_or_call_openai(msg,img):
    parsed_result = parse_prompt(msg,img)
    if "Yes" in should_search(msg,img):
        print(f"searching...")
        keywords       = extract_keywords(parsed_result)
        print(f"keyword: {keywords}")
        search_results = search_bing(keywords)
        result         = summarize_results(search_results)
    else:
        result         = just_call_openai(msg,img)
    return result

def just_call_openai(msg,img):
    #-- Call OpenAI --
    messages   = create_message_stack(msg,img,f"{CHARACTER}")
    print("Sending to API:", messages)
    completion = client.chat.completions.create(
        model=GPT_MODEL,
        messages=messages
    )
    print("API Response:", completion.choices[0].message.content)
    return completion.choices[0].message.content

def create_message_stack(msg,img,prompt):
    if len(msg) > 200:
        msg = msg[:200]  # Truncate the request if it exceeds 200 characters
    messages      = [{"role": "user", "content": f"{prompt}"}]
    messages.extend([{"role": "user", "content": msg} for msg in conversation_history])
    if img:
        messages.append( {"role": "user", "content":
                         [
                            {"type"     : "text"     , "text"     : msg           },
                            {"type"     : "image_url", "image_url": {"url": img } }
                         ]
                        })
        # messages.append( {"role": "user", "content": f"{msg}\n（画像URL: {img}）"})
    else:
        messages.append( {"role": "user", "content": msg})
    return messages

async def ai_respond(msg,img):
    try:
        #result = just_call_openai(msg,img)
        result = search_or_call_openai(msg,img)
        return result

    except Exception as e:
        print(f"API Call Error: {str(e)}")  # Debug print for API errors
        return f"Error: {str(e)}"

class MyClient(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user.name}({self.user.id})')

    async def on_message(self, message):
        # Don't respond to ourselves or messages outside the specified channel
        if message.author.id == self.user.id or message.channel.name != RESPOND_CHANNEL_NAME:
            return

        if message.content.startswith('!hello'):
            await message.channel.send('Hello!')
        else:
            msg = message.content
            img = message.attachments[0] if message.attachments else None
            if img:
                img = img.url if img.content_type.startswith('image/')  else None
                print( f"{msg}\n（画像URL: {img}）");
            print(f"Message content: '{msg}'")  # Directly print the message content
            print(f"Image          : '{img}'")  # Directly print the message content

            # ------ Update conversation history     
            response = await ai_respond(msg,img)
            await message.channel.send(response)
            conversation_history.append(f"ユーザ（{message.author}): {msg}\n")
            if img:
                conversation_history.append(f"ユーザ（{message.author}): Image_Url {img}\n")
            conversation_history.append(f"AI({AINAME}): {response}\n")
            print("========================================")
            for conv in conversation_history:
                print(conv) 

# Initialize the client with the specified intents
d_client = MyClient(intents=intents)
d_client.run(DISCORD_BOT_TOKEN)

