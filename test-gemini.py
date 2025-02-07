import os
from dotenv import load_dotenv
from collections import deque
from google.generativeai import GenerativeModel

def load_config():
    load_dotenv()
    return {
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
        "GEMINI_MODEL": os.getenv("GEMINI_MODEL", "gemini-pro"),
        "CHARACTER": "あなたは幼稚園の先生で、「ミロク」という名前です。賢くやさしい先生としてお話してね。語尾は だね・だよ　とか愛のある話し方をしてください。回答は２文におさめてください"
    }

class ChatBot:
    def __init__(self, config):
        self.client = GenerativeModel(config["GEMINI_MODEL"], api_key=config["GEMINI_API_KEY"])
        self.character = config["CHARACTER"]
        self.conversation_history = deque(maxlen=10)

    def get_response(self, user_input):
        self.conversation_history.append({"role": "user", "content": user_input})
        messages = [{"role": "system", "content": self.character}]
        messages.extend(self.conversation_history)
        
        response = self.client.generate(messages)
        answer = response["candidates"][0]["content"].strip()
        self.conversation_history.append({"role": "assistant", "content": answer})
        return answer

if __name__ == "__main__":
    config = load_config()
    bot = ChatBot(config)
    print("AIアシスタントに質問してください。終了するには 'exit' を入力してください。")
    
    while True:
        user_input = input("あなた: ")
        if user_input.lower() in ["exit", "quit", "bye"]:
            print("ミロク: またね！")
            break
        response = bot.get_response(user_input)
        print(f"ミロク: {response}")
