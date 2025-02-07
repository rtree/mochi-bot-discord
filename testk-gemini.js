import dotenv from 'dotenv';
import { GoogleGenerativeAI } from '@google/generative-ai';
import readline from 'readline';

dotenv.config();

const config = {
    GEMINI_API_KEY: process.env.GEMINI_API_KEY,
    GEMINI_MODEL: process.env.GEMINI_MODEL || "gemini-pro",
    CHARACTER: "あなたは幼稚園の先生で、「ミロク」という名前です。賢くやさしい先生としてお話してね。語尾は だね・だよ　とか愛のある話し方をしてください。回答は２文におさめてください"
};

class ChatBot {
    constructor(config) {
        this.client = new GoogleGenerativeAI(config.GEMINI_API_KEY);
        this.model = this.client.getGenerativeModel({ model: config.GEMINI_MODEL });
        this.character = config.CHARACTER;
        this.conversationHistory = [];
    }

    async getResponse(userInput) {
        this.conversationHistory.push({ role: "user", content: userInput });
        const messages = [{ role: "system", content: this.character }, ...this.conversationHistory];
        
        const response = await this.model.generateContent({ contents: messages });
        const answer = response.response.candidates[0].content.text.trim();
        this.conversationHistory.push({ role: "assistant", content: answer });
        return answer;
    }
}

const bot = new ChatBot(config);
console.log("AIアシスタントに質問してください。終了するには 'exit' を入力してください。");

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

const askQuestion = () => {
    rl.question("あなた: ", async (userInput) => {
        if (["exit", "quit", "bye"].includes(userInput.toLowerCase())) {
            console.log("ミロク: またね！");
            rl.close();
            return;
        }
        const response = await bot.getResponse(userInput);
        console.log(`ミロク: ${response}`);
        askQuestion();
    });
};

askQuestion();
