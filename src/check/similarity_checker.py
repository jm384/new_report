from __future__ import annotations

from pathlib import Path

from src.common.docx_utils import read_docx_text
from src.common.text_utils import (
    detect_headings,
    max_continuous_duplicate_chars,
    paragraph_similarities,
    similarity,
    split_paragraphs,
)


class SimilarityChecker:
    def __init__(self, context) -> None:
        self.context = context

    def check(self, article: dict, style_profile: dict) -> dict:
        article_text = article.get("text", "")
        article_paragraphs = split_paragraphs(article_text)
        article_headings = detect_headings([block["text"] for block in article.get("blocks", [])])

        template_texts = []
        for path_str in style_profile.get("template_paths", []):
            path = Path(path_str)
            if not path.exists():
                continue
            if path.suffix.lower() == ".docx":
                template_texts.append({"path": path_str, "text": read_docx_text(path)})
            else:
                template_texts.append({"path": path_str, "text": path.read_text(encoding="utf-8")})

        overall_similarity = 0.0
        high_similarity_paragraphs = 0
        high_similarity_headings = 0
        template_copy_risk = False
        structure_risk = False
        max_duplicate = 0

        for template in template_texts:
            template_text = template["text"]
            overall_similarity = max(overall_similarity, similarity(article_text, template_text))
            max_duplicate = max(max_duplicate, max_continuous_duplicate_chars(article_text, template_text))
            paragraph_scores = paragraph_similarities(article_paragraphs, split_paragraphs(template_text))
            high_similarity_paragraphs = max(
                high_similarity_paragraphs,
                sum(
                    1
                    for item in paragraph_scores
                    if item["similarity"] >= self.context.settings.check.max_template_paragraph_similarity
                ),
            )
            template_headings = detect_headings(split_paragraphs(template_text))
            overlap = set(article_headings) & set(template_headings)
            high_similarity_headings = max(high_similarity_headings, len(overlap))
            if len(overlap) >= 3:
                structure_risk = True

        if overall_similarity > 0.40 or max_duplicate > self.context.settings.check.max_continuous_duplicate_chars:
            template_copy_risk = True
        self.context.logger.info("CHECK", f"整体相似度：{overall_similarity:.2f}")
        self.context.logger.info("CHECK", f"高相似段落数量：{high_similarity_paragraphs}")
        self.context.logger.info("CHECK", f"高相似小标题数量：{high_similarity_headings}")
        self.context.logger.info(
            "CHECK",
            f"是否发现模板复制风险：{'是' if template_copy_risk else '否'}",
        )
        self.context.logger.info(
            "CHECK",
            f"是否发现结构过度雷同风险：{'是' if structure_risk else '否'}",
        )
        return {
            "overall_similarity": round(overall_similarity, 4),
            "high_similarity_paragraphs": high_similarity_paragraphs,
            "high_similarity_headings": high_similarity_headings,
            "template_copy_risk": template_copy_risk,
            "structure_risk": structure_risk,
            "max_continuous_duplicate_chars": max_duplicate,
        }
