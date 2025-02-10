from openai import OpenAI
import requests
from dotenv import load_dotenv
import os

# .envファイルからAPIキーを読み込む
load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
BING_API_KEY = os.getenv('BING_API_KEY')

# OpenAIクライアントを初期化
client = OpenAI(api_key=OPENAI_API_KEY)

# プロンプトを解析して主題、サブテーマ、キーワードを抽出
def parse_prompt(prompt):
    response = client.chat.completions.create(
        model=os.getenv('GPT_MODEL'),
        messages=[
            {"role": "user", "content": "あなたはユーザーのプロンプトを分析し、主題、サブテーマ、関連キーワードを抽出するアシスタントです。"},
            {"role": "user", "content": f"以下のプロンプトを分析し、主題、サブテーマ、関連キーワードを抽出してください: {prompt}"}
        ]
    )
    if any(keyword in prompt for keyword in ["出典", "URL", "探してほしい", "検索", "最新", "具体的"]):
        return "Yes"
    else:
        likelihood = response.choices[0].message.content.lower()
        if "no" in likelihood and "search" not in likelihood:
            return "Yes" if "最新" in prompt or "具体的な回答" in prompt else likelihood
        return "Yes"

# 検索の必要性を判断
def should_search(prompt):
    response = client.chat.completions.create(
        model=os.getenv('GPT_MODEL'),
        messages=[
            {"role": "user", "content": "あなたはユーザーのクエリに基づき、ウェブ検索が必要かどうかを判断するツールです。"},
            {"role": "user", "content": f"以下のクエリについて、最新の情報や具体的な回答を得るためにウェブ検索が必要かどうかを判断してください: {prompt}"}
        ]
    )
    return response.choices[0].message.content

# キーワードを抽出
def extract_keywords(parsed_text):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": "あなたは解析されたプロンプト情報から簡潔な検索フレーズを抽出します。"},
            {"role": "user", "content": f"このテキストからBing検索に最適な検索フレーズを抽出してください。: {parsed_text}"}
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
    return search_data

# 検索結果を要約
def summarize_results(search_results):
    snippets = "\n".join([result['snippet'] for result in search_results['webPages']['value'][:5]])
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": "あなたは検索結果を要約し、簡潔な回答を作成します。"},
            {"role": "user", "content": f"以下の検索スニペットを要約してください: {snippets}"}
        ]
    )
    return response.choices[0].message.content

# プロンプト処理の統合関数
def process_prompt(prompt):
    # 1. プロンプトの解析
    parsed_result = parse_prompt(prompt)
    print("Parsed Result:", parsed_result)

    # 2. 検索の要否を判断
    if "Yes" in should_search(prompt):
        # 3. キーワード抽出
        keywords = extract_keywords(parsed_result)
        print("Keywords:", keywords)
        
        # 4. Web検索
        search_results = search_bing(keywords)
        
        # 5. 回答の生成
        summary = summarize_results(search_results)
        urls = search_results.get('urls', [])
        sources = "\n\n".join([f"Source: {url}" for url in urls])
        return f"{summary}\n\n{sources}"
    else:
        response = client.chat.completions.create(
            model=os.getenv('GPT_MODEL'),
            messages=[
                {"role": "user", "content": "あなたは内部知識を使用して回答を生成するアシスタントです。"},
                {"role": "user", "content": f"以下のプロンプトに基づき回答を生成してください: {prompt}"}
            ]
        )
        return response.choices[0].message.content

# 実行例
if __name__ == "__main__":
    while True:
        user_prompt = input("プロンプトを入力してください（終了するには 'exit' と入力）: ")
        if user_prompt.lower() == 'exit':
            print("終了します。")
            break
        final_response = process_prompt(user_prompt)
        print("Final Response:", final_response)

