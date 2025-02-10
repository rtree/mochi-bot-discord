from openai import OpenAI

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