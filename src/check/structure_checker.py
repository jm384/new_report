from __future__ import annotations

from src.common.text_utils import detect_headings, split_paragraphs


class StructureChecker:
    def __init__(self, context) -> None:
        self.context = context

    def check(self, article: dict, style_profile: dict) -> dict:
        paragraphs = split_paragraphs(article.get("text", ""))
        headings = detect_headings([block["text"] for block in article.get("blocks", [])])
        missing = []
        if not headings:
            missing.append("缺少标题或小标题")
        if len(headings) < 3:
            missing.append("小标题数量偏少")
        if not paragraphs:
            missing.append("缺少正文段落")
        if paragraphs and len(paragraphs[0]) < 40:
            missing.append("开头过短")
        return {
            "has_problem": bool(missing),
            "issues": missing,
            "heading_count": len(headings),
        }
