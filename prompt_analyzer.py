# prompt_analyzer.py
import os
import re
import requests
from bs4 import BeautifulSoup
from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

class PromptAnalyzer:
    def __init__(self):
        self.client = TypeSafeClient()
        self.url_pattern = re.compile(
            r'https?://(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?::\d+)?(?:/[^\s<>"\'\`\{\}\|\\\^\~]*)?'
        )

    def extract_urls(self, text: str) -> list[str]:
        raw_urls = self.url_pattern.findall(text)
        cleaned_urls = []
        for url in raw_urls:
            clean_url = re.sub(r'[\.\,\;\:\?\!\)\］\>\」\』]+$', '', url)
            if clean_url and clean_url not in cleaned_urls:
                cleaned_urls.append(clean_url)
        return cleaned_urls

    def _fetch_web_content(self, url: str) -> str:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                for element in soup(["script", "style", "nav", "footer", "header"]):
                    element.decompose()
                text = soup.get_text(separator=' ', strip=True)
                return text[:2000]
        except Exception as e:
            return f"[Web情報の取得に失敗しました: {e}]"
        return "[Web情報を取得できませんでした]"

    def analyze(self, user_prompt: str) -> dict:
        detected_urls = self.extract_urls(user_prompt)
        has_url = len(detected_urls) > 0
        web_context = ""

        if has_url:
            target_url = detected_urls[0]
            print(f"🔗 URLを検出しました: {target_url} (Web情報を取得中...)")
            web_context = self._fetch_web_content(target_url)

        input_state = f"【ユーザープロンプト】\n{user_prompt}\n"
        if web_context:
            input_state += f"\n【参照URL先のコンテンツ（抜粋）】\n{web_context}\n"

        response = self.client.system_one(
            state=input_state,
            questions={
                "primary_goal": Choice(
                    instructions="""
                    ユーザーのプロンプトおよび参照Web情報（存在する場合）から判断して、
                    ユーザーが最終的に達成したい「真の目的（タスク）」を1つ選択すること。
                    単にWebページが引用されていること自体ではなく、「その情報を使って何を行いたいか」で分類すること。
                    """,
                    criteria={
                        "tech_discovery": "自社の課題解決に使える技術要素・アプローチの探索・特定・カテゴリ絞り込み",
                        "feasibility_eval": "参照した技術/サービスの実運用におけるメリット・デメリット・実現可能性・リスクの評価比較",
                        "market_competitive_intel": "参照先の事例・企業・論文等から、先進事例や他社動向・市場トレンドをベンチマーク調査",
                        "requirement_definition": "参照情報をベースに、開発や導入に向けた技術要件・仕様・制約条件を整理・定義",
                        "simple_summarization": "純粋に参照Webページの内容理解・翻訳・要約のみ（後続の技術検討や評価・比較を含まない）",
                        "general_consultation": "Web参照を伴わない一般的な技術相談・アイデア出し・プロンプト作成など",
                    },
                ),
                "has_format_spec": Noul(
                    instructions="表形式、JSON、文字数制限などの明確な出力フォーマット指定があるか",
                ),
                "has_negative_constraint": Noul(
                    instructions="「推測で書くな」「英語不可」などの明確な禁止・制約事項があるか",
                ),
                "technical_density": Score(
                    instructions="専門用語（材料名、物理/化学用語、アルゴリズム等）の密度",
                    criteria=[
                        "一般的（専門用語なし）",
                        "中程度（標準的なIT/技術用語）",
                        "極めて高度（深いドメイン専門用語が頻出）",
                    ],
                ),
            },
        )

        return {
            "url_detected": has_url,
            "urls": detected_urls,
            "web_context_fetched": bool(web_context and not web_context.startswith("[Web情報")),
            "primary_goal": response.answers["primary_goal"].choice,
            "meta_structure": {
                "has_format_spec": response.answers["has_format_spec"].noul,
                "has_negative_constraint": response.answers["has_negative_constraint"].noul,
            },
            "technical_density": response.answers["technical_density"].score,
        }