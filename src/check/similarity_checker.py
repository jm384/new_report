from __future__ import annotations

from pathlib import Path

from src.common.docx_utils import read_docx_text
from src.common.text_utils import detect_headings, split_paragraphs, similarity


class SimilarityChecker:
    def __init__(self, context) -> None:
        self.context = context

    def check(self, article: dict, style_profile: dict) -> dict:
        article_text = article.get("text", "")
        template_texts = []
        for path_str in style_profile.get("template_paths", []):
            path = Path(path_str)
            if not path.exists():
                continue
            template_texts.append(read_docx_text(path) if path.suffix.lower() == ".docx" else path.read_text(encoding="utf-8"))

        max_similarity = 0.0
        for template_text in template_texts:
            max_similarity = max(max_similarity, similarity(article_text, template_text))

        article_headings = detect_headings([block["text"] for block in article.get("blocks", [])])
        template_headings = []
        for template_text in template_texts:
            template_headings.extend(detect_headings(split_paragraphs(template_text)))

        overlap = len(set(article_headings) & set(template_headings))
        issues = []
        if max_similarity > 0.72:
            issues.append("与模板文字相似度偏高")
        if overlap >= 3:
            issues.append("结构与模板过于接近")
        return {
            "has_problem": bool(issues),
            "issues": issues,
            "style_similarity": round(max_similarity, 4),
            "heading_overlap": overlap,
        }
