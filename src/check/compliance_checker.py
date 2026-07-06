from __future__ import annotations

from src.common.text_utils import contains_any


class ComplianceChecker:
    def __init__(self, context) -> None:
        self.context = context

    def check(self, article: dict) -> dict:
        text = article.get("text", "")
        hits = contains_any(text, self.context.settings.banned_marketing_phrases)
        self.context.logger.info(
            "CHECK",
            f"是否发现夸大承诺表达：{'是' if hits else '否'}",
        )
        return {
            "banned_hits": hits,
            "has_risk": bool(hits),
        }
