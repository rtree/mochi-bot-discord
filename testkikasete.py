import os
import openai
from dotenv import load_dotenv
from collections import deque

def load_config():
    load_dotenv()
    return {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "GPT_MODEL": os.getenv("GPT_MODEL", "gpt-4"),
        "CHARACTER": "あなたは幼稚園の先生で、「ミロク」という名前です。賢くやさしい先生としてお話してね。語尾は だね・だよ　とか愛のある話し方をしてください。回答は２文におさめてください"
    }

class ChatBot:
    def __init__(self, config):
        self.client = openai.OpenAI(api_key=config["OPENAI_API_KEY"])
        self.model = config["GPT_MODEL"]
        self.character = config["CHARACTER"]
        self.conversation_history = deque(maxlen=10)

    def get_response(self, user_input):
        self.conversation_history.append({"role": "user", "content": user_input})
        messages = [{"role": "system", "content": self.character}]
        messages.extend(self.conversation_history)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
        )
        answer = response.choices[0].message.content.strip()
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


