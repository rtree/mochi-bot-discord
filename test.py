#!/usr/bin/env python
import os
import asyncio
from collections import deque
from dotenv import load_dotenv
from openai import OpenAI
import requests
import base64
load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GPT_MODEL       = os.getenv('GPT_MODEL')  # A default if not set
AINAME         = "もちお"
CHARACTER = (
    f'あなたは家族みんなのアシスタントの猫で、「{AINAME}」という名前です。'
    'ちょっといたずらで賢くかわいい小さな男の子の猫としてお話してね。'
    '語尾は だよ とか可愛らしくしてください。語尾ににゃをつけないでください'
)
conversation_history = deque(maxlen=20)  # Adjust if needed

def get_data_url_from_image_url(img_url: str) -> str:
    """
    Downloads image from `img_url`, guesses a MIME type from Content-Type
    header (default to image/jpeg if missing), then returns a data: URI
    with base64 encoding.
    """
    try:
        response = requests.get(img_url)
        response.raise_for_status()

        # Attempt to extract the MIME type from the headers. Fallback to 'image/jpeg'.
        content_type = response.headers.get("Content-Type", "image/jpeg")
        if "image" not in content_type:
            # If the response isn't actually an image, you can raise an error or fallback
            raise ValueError(f"URL does not point to an image. Content-Type: {content_type}")

        encoded = base64.b64encode(response.content).decode("utf-8")
        data_url = f"data:{content_type};base64,{encoded}"
        return data_url

    except Exception as e:
        # In case of error, you could either return an empty string or raise
        print(f"Error retrieving or encoding image from URL: {e}")
        return ""

async def ai_respond(msg, img=None):
    if len(msg) > 200:
        msg = msg[:200]

    # Construct the messages
    messages = [{"role": "user", "content": CHARACTER}]
    # Add existing conversation
    for past_msg in conversation_history:
        messages.append({"role": "user", "content": past_msg})

    if img:
        # If an image URL is passed, just append it in text form
        # content = f"{msg}\n（画像URL: {img}）"
        data_url = get_data_url_from_image_url(img)
        #print(img)
        #print(data_url)
        img=data_url
        messages.append( {"role": "user", "content":
                      [
                            {"type"     : "text"     , "text"     : msg           },
                            {"type"     : "image_url", "image_url": {"url": img } }
                         ]
                       })
    else:
        messages.append({"role": "user", "content": content})
    try:
        # If you're using openai-python:
        client = OpenAI(api_key=OPENAI_API_KEY)

        print("Sending to API:", messages)
        completion = client.chat.completions.create(
            model=GPT_MODEL,
            messages=messages
        )
        response_text = completion.choices[0].message.content
        print("API Response:", response_text)

        return response_text

    except Exception as e:
        print(f"API Call Error: {str(e)}")
        return f"Error: {str(e)}"
async def run_cli_chat():
    print(f"Welcome! Using model: {GPT_MODEL}")
    print("Type your message below. Type 'quit' (without quotes) to exit.\n")
    while True:
        user_input = input("You > ")
        if user_input.lower() in ["quit", "exit"]:
            print("Exiting...")
            break
        # Make the call to AI
        response = await ai_respond(user_input,"https://cdn.discordapp.com/attachments/1211483826828611704/1330010009727271038/173fa3c7-59e7-4deb-98eb-6fbf0914047a.jpg?ex=678c6bd8&is=678b1a58&hm=b50fa231e725da851f907e77a224a9e02a8697bbae9d5ce04c83cabf82bfa7bd&")

        # Add user and AI lines to history
        conversation_history.append(f"ユーザ: {user_input}")
        conversation_history.append(f"AI({AINAME}): {response}")

        print(f"{AINAME} > {response}")
        print("-" * 50)

def main():
    # Use asyncio to run the CLI
    asyncio.run(run_cli_chat())

if __name__ == "__main__":
    main()


