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
        # Google Search replacement using Gemini API
        import os
        from datetime import datetime
        from dotenv import load_dotenv
        from google import genai
        from google.genai import types
        # For resolving URL redirects
        import requests as _requests

        if domains is None:
            domains = self.config.REPUTABLE_DOMAINS
        if count is None:
            count = self.config.SEARCH_RESULTS

        # Load environment and set Google Cloud settings
        load_dotenv()
        os.environ["GOOGLE_CLOUD_PROJECT"]  = os.getenv("GOOGLE_CLOUD_PROJECT", self.config.GOOGLE_CLOUD_PROJECT)
        os.environ["GOOGLE_CLOUD_LOCATION"] = os.getenv("GOOGLE_CLOUD_LOCATION", self.config.GOOGLE_CLOUD_LOCATION)
        os.environ["GOOGLE_CLOUD_MODEL"]    = os.getenv("GOOGLE_CLOUD_MODEL",self.config.GOOGLE_CLOUD_MODEL)




        # Initialize Gemini client
        api_key = os.getenv("GOOGLE_CLOUD_API_GEMINI", getattr(self.config, "GOOGLE_CLOUD_API_GEMINI", None))
        client = genai.Client(vertexai=False, api_key=api_key)
        model  = os.getenv("GOOGLE_CLOUD_MODEL", self.config.GOOGLE_CLOUD_MODEL)
        #model = "gemini-2.0-flash"

        # Define the grounding tool for Google Search
        grounding_tool = types.Tool(
            google_search=types.GoogleSearch()
        )
        gen_config = types.GenerateContentConfig(
            tools=[grounding_tool]
        )

        # Compose query
        search_query = f"{query}"
        response = client.models.generate_content(
            model=model,
            contents=search_query,
            config=gen_config,
        )

        # Extract summary text
        summary = response.text
        # Extract grounding URLs and build Bing-like output
        webPages = []
        urls = []
        titles = []
        if getattr(response, "candidates", None):
            grounding_meta = response.candidates[0].grounding_metadata
            if grounding_meta and grounding_meta.grounding_chunks:
                print("Google Search Results:")
                for chunk in grounding_meta.grounding_chunks[:count]:
                    title = chunk.web.title
                    url = chunk.web.uri
                    snippet = getattr(chunk.web, "snippet", "") or getattr(chunk.web, "description", "") or ""
                    # Try to resolve final URL
                    try:
                        resp = _requests.get(url, allow_redirects=True, timeout=10)
                        final_url = resp.url
                    except Exception as e:
                        final_url = url
                        if hasattr(self.config, "logprint"):
                            self.config.logprint.error(f"Error resolving {url}: {e}")
                    print(f"Title: {title}")
                    print(f"URL: {final_url}")
                    print(f"Snippet: {snippet}")
                    print("---")
                    webPages.append({
                        "name": title,
                        "url": final_url,
                        "snippet": snippet
                    })
                    urls.append(final_url)
                    titles.append(title)

        # Compose output to match Bing's structure
        search_data = {
            "webPages": {"value": webPages},
            "urls": urls,
            "titles": titles,
            "summary": summary
        }
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