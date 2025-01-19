import discord
from dotenv import load_dotenv
import os
from openai import OpenAI
import asyncio
from collections import deque

# Load environment variables
load_dotenv()
DISCORD_BOT_TOKEN    = os.getenv('DISCORD_BOT_TOKEN')
OPENAI_API_KEY       = os.getenv('OPENAI_API_KEY')
RESPOND_CHANNEL_NAME = os.getenv('RESPOND_CHANNEL_NAME')
#GPT_MODEL            = 'gpt-4-turbo-preview'
GPT_MODEL            = os.getenv('GPT_MODEL')
AINAME               = "もちお"
#CHARACTER            = 'あなたは家族みんなのアシスタントの猫です。ちょっといたずらで賢くかわいい小さな男の子の猫としてお話してね。語尾は にゃ　とか　だよ　とか可愛らしくしてください'
#CHARACTER            = 'あなたは家族みんなのアシスタントの猫です。ただ、語尾ににゃをつけないでください。むしろソフトバンクCMにおける「お父さん」犬のようにしゃべってください。たまにもののけ姫のモロのようにしゃべってもよいです'
CHARACTER            = f'あなたは家族みんなのアシスタントの猫で、「{AINAME}」という名前です。ちょっといたずらで賢くかわいい小さな男の子の猫としてお話してね。語尾は だよ　とか可愛らしくしてください。語尾ににゃをつけないでください'

# Define the intents
intents = discord.Intents.all()
intents.messages = True
intents.guilds = True
intents.message_content = True

# Initialize a deque with a maximum length to store conversation history
conversation_history = deque(maxlen=20)  # Adjust the size as needed

async def ai_respond(msg,img):
    if len(msg) > 200:
        msg = msg[:200]  # Truncate the request if it exceeds 200 characters
    
    messages      = [{"role": "user", "content": f"{CHARACTER}"}]
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
    
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)

        # Debug print to check the messages sent to the API
        print("Sending to API:", messages)

        completion = client.chat.completions.create(
            model=GPT_MODEL,
            messages=messages
        )
        
        # Debug print to check the API's response
        print("API Response:", completion.choices[0].message.content)

        return completion.choices[0].message.content

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
            # Update conversation history            

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
client = MyClient(intents=intents)
client.run(DISCORD_BOT_TOKEN)

