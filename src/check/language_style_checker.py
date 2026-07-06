from __future__ import annotations


POSITIVE_HINTS = ["建议", "提醒", "可以", "通常", "一般", "如果", "需要结合", "尽早"]
NEGATIVE_HINTS = ["据记者", "突发", "震惊", "必须立刻", "稳赢", "最高赔偿"]


class LanguageStyleChecker:
    def __init__(self, context, llm_client) -> None:
        self.context = context
        self.llm_client = llm_client

    def check(self, article: dict, style_profile: dict) -> dict:
        text = article.get("text", "")
        score = 85
        hits = [hint for hint in POSITIVE_HINTS if hint in text]
        bad_hits = [hint for hint in NEGATIVE_HINTS if hint in text]
        if len(hits) < 3:
            score -= 10
        if bad_hits:
            score -= 18
        if "纽约" not in text:
            score -= 6
        if "法律" not in text and "责任" not in text and "保险" not in text:
            score -= 10
        if self.llm_client.is_configured and self.context.settings.llm.enable_check_and_rewrite:
            try:
                llm_score = self._llm_score(article, style_profile)
                score = round((score + llm_score) / 2)
            except Exception as exc:
                self.context.logger.warning("CHECK", f"LLM 语言风格评分失败，使用规则评分：{exc}")

        score = max(0, min(100, int(score)))
        self.context.logger.info("CHECK", f"语言风格评分：{score}")
        return {
            "score": score,
            "positive_hits": hits,
            "negative_hits": bad_hits,
            "notes": "根据稳重表达、纽约场景、法律解释和营销风险进行评分。",
        }

    def _llm_score(self, article: dict, style_profile: dict) -> int:
        prompt = f"""
请判断下面文章是否符合中文律师事务所科普博客的语言风格，并给出 0-100 分。
模板语气摘要：{style_profile.get('tone_summary', '')}
文章内容：
{article.get('text', '')[:3000]}

只输出 JSON：
{{"score": 88, "reason": "..."}}
""".strip()
        payload = self.llm_client.generate_json(
            phase="CHECK",
            purpose="语言风格评分",
            prompt=prompt,
            system_prompt="你是中文法律博客语言风格评分助手，只输出合法 JSON。",
        )
        return int(payload["score"])
