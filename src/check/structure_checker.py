from __future__ import annotations

from src.common.text_utils import detect_headings, split_paragraphs


class StructureChecker:
    def __init__(self, context) -> None:
        self.context = context

    def check(self, article: dict, style_profile: dict) -> dict:
        paragraphs = split_paragraphs(article.get("text", ""))
        heading_lines = [block.get("text", "") for block in article.get("blocks", [])]
        headings = detect_headings(heading_lines)
        issues: list[str] = []
        intro_text = "".join(paragraphs[:2]) if paragraphs else ""

        if not headings:
            issues.append("缺少标题或小标题")
        if len(headings) < 4:
            issues.append("文章结构层次不足，小标题数量偏少")
        if not paragraphs:
            issues.append("缺少正文段落")
        if paragraphs and len(intro_text) < 90:
            issues.append("开头内容过短，导入不完整")
        if len(paragraphs) < 7:
            issues.append("正文段落偏少，信息展开不足")

        return {
            "has_problem": bool(issues),
            "issues": issues,
            "heading_count": len(headings),
            "paragraph_count": len(paragraphs),
        }
