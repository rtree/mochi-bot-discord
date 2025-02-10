from openai import OpenAI
import asyncio
import requests
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader
from io import BytesIO
import base64

class Researcher:
    def __init__(self, config, context):
        self.config = config
        self.context = context
        self.aiclient = OpenAI(api_key=self.config.OPENAI_API_KEY)

    def _search_bing(self, query, domains=None, count=None):
        if domains is None:
            domains = self.config.REPUTABLE_DOMAINS
        if count is None:
            count = self.config.SEARCH_RESULTS

        url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": self.config.BING_API_KEY}
        query = f"{query}"
        params = {"q": query, "count": count}
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        search_data = response.json()
        search_data['urls'] = [result['url'] for result in search_data.get('webPages', {}).get('value', [])[:count]]

        print("Bing Search Results:")
        for result in search_data.get('webPages', {}).get('value', [])[:count]:
            print(f"Title: {result['name']}")
            print(f"URL: {result['url']}")
            print(f"Snippet: {result['snippet']}")
            print("---")
        return search_data

    async def _fetch_page_content_async(self, url):
        def blocking_fetch():
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                content_type = response.headers.get('Content-Type', '')

                if 'application/pdf' in content_type:
                    pdf_reader = PdfReader(BytesIO(response.content))
                    pdf_text = "".join(page.extract_text() for page in pdf_reader.pages)
                    return pdf_text[:self.config.MAX_CONTENT_LENGTH], "PDF"
                elif 'text/html' in content_type:
                    soup = BeautifulSoup(response.content, 'lxml')
                    text = soup.get_text(separator='\n', strip=True)
                    return text[:self.config.MAX_CONTENT_LENGTH], "HTML"
                elif content_type.startswith('image/'):
                    base64_img = base64.b64encode(response.content).decode('utf-8')
                    data_url = f"data:{content_type};base64,{base64_img}"
                    return data_url, "Image"
                else:
                    return None, "Unsupported"

            except Exception as e:
                print(f"Error fetching {url}: {str(e)}")
                return None, "Error"

        content, ctype = await asyncio.to_thread(blocking_fetch)
        return content, ctype

    async def _summarize_results_with_pages_async(self, search_results):
        content_list = []
        web_results = search_results.get('webPages', {}).get('value', [])[:self.config.SEARCH_RESULTS]

        tasks = [self._fetch_page_content_async(r['url']) for r in web_results]
        pages = await asyncio.gather(*tasks, return_exceptions=True)

        for (r, page_result) in zip(web_results, pages):
            title = r['name']
            snippet = r['snippet']
            url = r['url']

            if isinstance(page_result, Exception):
                content_list.append(f"タイトル: {title}\nURL: {url}\nスニペット:\n{snippet}\n")
                continue

            page_content, content_type = page_result
            if content_type in ("HTML", "PDF") and page_content:
                content_list.append(
                    f"タイトル: {title}\nURL: {url}\n内容:\n{page_content}\n"
                )
            else:
                content_list.append(
                    f"タイトル: {title}\nURL: {url}\nスニペット:\n{snippet}\n"
                )

        return "\n".join(content_list)

    async def summarize_results_async(self, search_results):
        snippets = await self._summarize_results_with_pages_async(search_results)

        p_src = (
            f"{self.config.CHARACTER}。あなたは検索結果を要約し、私の質問への回答を作成します。"
            " 会話履歴を踏まえつつ私が知りたいことの主旨を把握の上で、以下の検索結果を要約し回答を作ってください。"
            " 仮に検索結果が英語でも回答は日本語でお願いします。"
            " なお、回答がより高品質になるのならば、あなたの内部知識を加味して回答を作っても構いません。"
            " ただし、要約元にあった Title, URL は必ず元の形式で末尾に記入してください。"
            " URLを書くときはDiscordのAutoEmbedを防ぎたいので<>などで囲んでください。: "
            f"{snippets}"
        )

        def blocking_chat_completion():
            messages = [{"role": "system", "content": self.config.CHARACTER}]
            messages.extend(self.context)
            messages.append({"role": "user", "content": p_src})

            return self.aiclient.chat.completions.create(
                model=self.config.GPT_MODEL,
                messages=messages
            )

        response = await asyncio.to_thread(blocking_chat_completion)
        summary = response.choices[0].message.content

        titles = search_results.get('titles', [])
        urls = search_results.get('urls', [])
        sources = "\n".join(
            f"Source: {t} - {u}"
            for t, u in zip(titles, urls)
        )

        return f"{summary}\n\n{sources}"

    async def search_and_summarize(self, keywords):
        search_results = self._search_bing(keywords)
        summary = await self.summarize_results_async(search_results)
        return summary

    def just_call_openai(self, discIn):
        messages = [{"role": "system", "content": f"{self.config.CHARACTER}"}]
        messages.extend(self.context)
        completion = self.aiclient.chat.completions.create(
            model=self.config.GPT_MODEL,
            messages=messages
        )
        return completion.choices[0].message.content