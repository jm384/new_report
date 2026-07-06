from __future__ import annotations

from src.common.text_utils import average_paragraph_length, detect_headings, split_paragraphs


class StructureChecker:
    def __init__(self, context) -> None:
        self.context = context

    def check(self, article: dict, style_profile: dict) -> dict:
        text = article.get("text", "")
        paragraphs = split_paragraphs(text)
        headings = detect_headings([block["text"] for block in article.get("blocks", [])])
        avg_para_len = average_paragraph_length(paragraphs)
        score = 100

        avg_heading_count = style_profile.get("avg_heading_count", 4) or 4
        if len(headings) < 3:
            score -= 18
        if abs(len(headings) - avg_heading_count) > 3:
            score -= 12
        if avg_para_len > 220:
            score -= 10
        if not paragraphs or len(paragraphs[0]) < 30:
            score -= 10
        if "温和提醒" not in [block["text"] for block in article.get("blocks", [])]:
            score -= 5

        score = max(0, int(score))
        self.context.logger.info("CHECK", f"小标题数量：{len(headings)}")
        self.context.logger.info("CHECK", f"平均段落长度：{avg_para_len:.1f}")
        self.context.logger.info("CHECK", f"结构匹配评分：{score}")
        return {
            "score": score,
            "heading_count": len(headings),
            "average_paragraph_length": round(avg_para_len, 1),
            "notes": "根据模板平均标题数、段落长度和结尾提醒等规则评分。",
        }
