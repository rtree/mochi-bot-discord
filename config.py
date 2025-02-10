import os
from dotenv import load_dotenv

class Config:
    def __init__(self):
        load_dotenv()
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

