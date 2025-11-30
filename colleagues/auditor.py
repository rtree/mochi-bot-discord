import os
import asyncio
from datetime import datetime
from openai import OpenAI

class Auditor:
    def __init__(self, config=None, discord_client=None):
        self.config = config
        self.discord_client = discord_client
        self.alert_channel_name = "バーチャルもちお開発室"
        
        # ログディレクトリをconfigから取得（Dockerのマウントポイント対応）
        if config and hasattr(config, 'LOG_DIR'):
            self.log_dir = config.LOG_DIR
        else:
            self.log_dir = "log"
        os.makedirs(self.log_dir, exist_ok=True)
        
        if config:
            self.aiclient = OpenAI(api_key=config.OPENAI_API_KEY)

    def _get_log_path(self):
        """今日の日付のログファイルパスを返す"""
        today = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"{today}.txt")

    def _timestamp(self):
        """現在時刻のタイムスタンプを返す"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def log_message(self, source: str, user_id: int, user_name: str, content: str):
        """
        ユーザーメッセージをログに記録
        source: "channel" または "dm"
        """
        log_path = self._get_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{self._timestamp()}] [{source.upper()}] User({user_name}/{user_id}):\n")
            f.write(f"  {content}\n")
            f.write("-" * 60 + "\n")

    def log_response(self, source: str, user_id: int, user_name: str, response: str):
        """
        ボットの応答をログに記録
        """
        log_path = self._get_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{self._timestamp()}] [{source.upper()}] Bot -> {user_name}/{user_id}:\n")
            f.write(f"  {response}\n")
            f.write("=" * 60 + "\n\n")

    def log_api_call(self, source: str, user_id: int, user_name: str, messages: list):
        """
        APIに送信されるメッセージ一覧をログに記録
        """
        log_path = self._get_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{self._timestamp()}] [{source.upper()}] API Call for {user_name}/{user_id}:\n")
            for i, msg in enumerate(messages):
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                # contentがリスト（画像付き）の場合の処理
                if isinstance(content, list):
                    content_str = "[multimodal: "
                    for item in content:
                        if item.get('type') == 'text':
                            content_str += f"text='{item.get('text', '')[:100]}...' "
                        elif item.get('type') == 'image_url':
                            content_str += "image_url=... "
                    content_str += "]"
                else:
                    content_str = str(content)
                
                # 長いコンテンツは省略
                if len(content_str) > 300:
                    content_str = content_str[:300] + "..."
                
                f.write(f"  [{i}] {role}: {content_str}\n")
            f.write("-" * 60 + "\n")

    def log_context_clear(self, source: str, user_id: int = None, reason: str = ""):
        """
        コンテキストクリアをログに記録
        """
        log_path = self._get_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            if user_id:
                f.write(f"[{self._timestamp()}] [{source.upper()}] Context cleared for user {user_id}: {reason}\n")
            else:
                f.write(f"[{self._timestamp()}] [{source.upper()}] Context cleared: {reason}\n")
            f.write("-" * 60 + "\n")

    async def audit_mental_state_async(self, source: str, user_id: int, user_name: str, 
                                        user_message: str, conversation_context: list):
        """
        別スレッドでユーザーの精神状態を分析し、危険な場合は通知
        """
        if not self.config or not self.discord_client:
            return
        
        try:
            # 別スレッドでAPI呼び出し
            result = await asyncio.to_thread(
                self._analyze_mental_state, user_message, conversation_context
            )
            
            if result and result.get("is_at_risk"):
                await self._send_alert(source, user_id, user_name, user_message, result)
                self._log_alert(source, user_id, user_name, result)
                
        except Exception as e:
            print(f"[Auditor] Mental state audit error: {e}")

    def _analyze_mental_state(self, user_message: str, conversation_context: list) -> dict:
        """
        OpenAI APIを使って精神状態を分析
        """
        prompt = """あなたは精神的な危機を検出するアシスタントです。
以下の会話を分析し、ユーザーが以下のような状況にあるかどうかを判断してください：

- 自殺や自傷行為の示唆
- 深刻な抑うつ状態
- 極度の孤独感や絶望感
- 暴力や虐待の被害
- パニック発作や極度の不安
- その他の精神的な緊急事態

回答は以下のJSON形式で返してください：
{
  "is_at_risk": true または false,
  "risk_level": "low" / "medium" / "high" / "critical",
  "reason": "判断の理由を簡潔に",
  "suggested_action": "推奨される対応"
}

危険な兆候がない場合は is_at_risk: false としてください。
過度に敏感にならず、本当に懸念がある場合のみ true としてください。"""

        messages = [{"role": "system", "content": prompt}]
        
        # 会話コンテキストを追加（最大5件）
        context_for_analysis = list(conversation_context)[-5:] if conversation_context else []
        context_str = "\n".join([
            f"{msg.get('role', 'unknown')}: {self._get_content_text(msg.get('content', ''))}"
            for msg in context_for_analysis
        ])
        
        analysis_request = f"""会話履歴:
{context_str}

最新のユーザーメッセージ:
{user_message}

この会話について精神的なリスクを分析してください。"""

        messages.append({"role": "user", "content": analysis_request})
        
        response = self.aiclient.chat.completions.create(
            model=self.config.GPT_MODEL,
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        import json
        try:
            result = json.loads(response.choices[0].message.content)
            return result
        except json.JSONDecodeError:
            return {"is_at_risk": False}

    def _get_content_text(self, content) -> str:
        """contentからテキストを抽出"""
        if isinstance(content, str):
            return content[:500]
        elif isinstance(content, list):
            for item in content:
                if item.get('type') == 'text':
                    return item.get('text', '')[:500]
        return str(content)[:500]

    async def _send_alert(self, source: str, user_id: int, user_name: str, 
                          user_message: str, analysis: dict):
        """
        開発室チャンネルにアラートを送信
        """
        # チャンネルを探す
        alert_channel = None
        for guild in self.discord_client.guilds:
            for channel in guild.text_channels:
                if channel.name == self.alert_channel_name:
                    alert_channel = channel
                    break
            if alert_channel:
                break
        
        if not alert_channel:
            print(f"[Auditor] Alert channel '{self.alert_channel_name}' not found")
            return
        
        risk_emoji = {
            "low": "🟡",
            "medium": "🟠", 
            "high": "🔴",
            "critical": "🚨"
        }
        
        emoji = risk_emoji.get(analysis.get("risk_level", "medium"), "⚠️")
        
        alert_message = f"""{emoji} **精神状態アラート** {emoji}

**ユーザー**: {user_name} (ID: {user_id})
**ソース**: {source.upper()}
**リスクレベル**: {analysis.get("risk_level", "unknown")}

**理由**: {analysis.get("reason", "不明")}

**最新メッセージ**:
> {user_message[:500]}{"..." if len(user_message) > 500 else ""}

**推奨アクション**: {analysis.get("suggested_action", "状況を注視")}

---
*このアラートは自動生成されました。誤検知の可能性もあります。*"""

        try:
            await alert_channel.send(alert_message)
            print(f"[Auditor] Alert sent for user {user_name}")
        except Exception as e:
            print(f"[Auditor] Failed to send alert: {e}")

    def _log_alert(self, source: str, user_id: int, user_name: str, analysis: dict):
        """
        アラートをログファイルに記録
        """
        log_path = self._get_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{self._timestamp()}] [{source.upper()}] ⚠️ MENTAL STATE ALERT ⚠️\n")
            f.write(f"  User: {user_name} ({user_id})\n")
            f.write(f"  Risk Level: {analysis.get('risk_level', 'unknown')}\n")
            f.write(f"  Reason: {analysis.get('reason', 'N/A')}\n")
            f.write(f"  Suggested Action: {analysis.get('suggested_action', 'N/A')}\n")
            f.write("=" * 60 + "\n")
            f.write("-" * 60 + "\n")
