from __future__ import annotations

from pathlib import Path

from src.common.docx_utils import write_sections_docx
from src.common.file_utils import save_json, write_text


class ReportBuilder:
    def __init__(self, context) -> None:
        self.context = context

    def summarize_result(self, result: dict) -> str:
        structure_score = result["structure"]["score"]
        language_score = result["language"]["score"]
        overall_similarity = result["similarity"]["overall_similarity"]
        copy_risk = result["similarity"]["template_copy_risk"]
        if structure_score >= 75 and language_score >= 75 and overall_similarity <= 0.30 and not copy_risk:
            return "通过：结构、语言与相似度都在可接受范围内。"
        if structure_score >= 65 and language_score >= 65 and overall_similarity <= 0.40:
            return "基本通过：文章可用，但仍有少量可优化段落。"
        return "未通过：结构或相似度风险偏高，已尝试修复，但仍建议人工复核。"

    def write(self, results: list[dict], run_root: Path) -> None:
        report_root = self.context.paths.check
        md_lines = self._build_md_lines(results, run_root)
        md_path = report_root / "quality_check_report.md"
        json_path = report_root / "quality_check_report.json"
        docx_path = report_root / "quality_check_report.docx"
        write_text(md_path, "\n".join(md_lines))
        save_json(json_path, {"results": results, "run_id": self.context.run_id, "output_dir": str(run_root)})
        self._write_docx(docx_path, results, run_root)
        self.context.record_file(md_path)
        self.context.record_file(json_path)
        self.context.record_file(docx_path)

    def _build_md_lines(self, results: list[dict], run_root: Path) -> list[str]:
        lines = [
            "# 质量检查报告",
            "",
            f"- 本次运行时间：{self.context.run_id}",
            f"- 本次输出目录：{run_root}",
            "",
            "## 评分说明",
            "",
            "- 结构评分：看文章有没有清楚的标题、小标题、过渡和结尾提醒，越高表示结构越像成熟科普文。",
            "- 语言评分：看文章读起来顺不顺、自然不自然、有没有过多生硬套话，越高表示越适合对外发布。",
            "- 整体相似度：把文章正文和模板正文做文本比较，范围 0 到 1，越低越不容易被认为是照搬模板。",
            "- 高相似段落数：文章里和模板特别接近的段落数量。",
            "- 高相似标题数：文章里和模板很像的小标题数量。",
            "- 模板复制风险：当相似度或连续重复字符过高时，会提示有直接借用模板的风险。",
            "- 结构过度雷同风险：当多个小标题与模板高度重合时，会提示结构太像。",
            "",
        ]
        for item in results:
            lines.extend(self._item_md(item))
        return lines

    def _item_md(self, item: dict) -> list[str]:
        lines = [
            f"## {item['title']}",
            "",
            f"- 主题：{item['topic']}",
            f"- 原文章路径：{item['article_path']}",
            f"- 最终文章路径：{item.get('final_article_path', '') or '无'}",
            f"- 文章字数：{item['word_count']}",
            f"- 模板路径：{', '.join(item['template_paths']) if item['template_paths'] else '无'}",
            f"- 结构评分：{item['structure']['score']}",
            f"- 语言评分：{item['language']['score']}",
            f"- 整体相似度：{item['similarity']['overall_similarity']}",
            f"- 高相似段落数：{item['similarity']['high_similarity_paragraphs']}",
            f"- 高相似标题数：{item['similarity']['high_similarity_headings']}",
            f"- 模板复制风险：{'是' if item['similarity']['template_copy_risk'] else '否'}",
            f"- 结构过度雷同风险：{'是' if item['similarity']['structure_risk'] else '否'}",
            f"- 是否存在夸大承诺表达：{'是' if item['compliance']['has_risk'] else '否'}",
            f"- 是否已自动修复：{'是' if item['rewritten'] else '否'}",
            f"- 最终检查结论：{item['final_conclusion']}",
            "",
        ]
        return lines

    def _write_docx(self, path: Path, results: list[dict], run_root: Path) -> None:
        sections: list[tuple[str, list[str]]] = [
            (
                "一、报告说明",
                [
                    f"本次运行时间：{self.context.run_id}",
                    f"本次输出目录：{run_root}",
                    "本报告说明结构匹配、语言风格、整体相似度等评分含义，并记录最终修复后的文章。",
                ],
            ),
            (
                "二、评分说明",
                [
                    "结构评分：看文章有没有清楚的标题、小标题、过渡和结尾提醒，越高表示结构越像成熟科普文。",
                    "语言评分：看文章读起来顺不顺、自然不自然、有没有过多生硬套话，越高表示越适合对外发布。",
                    "整体相似度：把文章正文和模板正文做文本比较，范围 0 到 1，越低越不容易被认为是照搬模板。",
                    "高相似段落数：文章里和模板特别接近的段落数量。",
                    "高相似标题数：文章里和模板很像的小标题数量。",
                    "模板复制风险：当相似度或连续重复字符过高时，会提示有直接借用模板的风险。",
                    "结构过度雷同风险：当多个小标题与模板高度重合时，会提示结构太像。",
                ],
            ),
        ]
        for item in results:
            sections.append((f"三、{item['title']}", self._item_doc_lines(item)))
        write_sections_docx(path, f"质量检查报告：{self.context.run_id}", sections)

    def _item_doc_lines(self, item: dict) -> list[str]:
        return [
            f"主题：{item['topic']}",
            f"原文章路径：{item['article_path']}",
            f"最终文章路径：{item.get('final_article_path', '') or '无'}",
            f"文章字数：{item['word_count']}",
            f"模板路径：{', '.join(item['template_paths']) if item['template_paths'] else '无'}",
            f"结构评分：{item['structure']['score']}",
            f"语言评分：{item['language']['score']}",
            f"整体相似度：{item['similarity']['overall_similarity']}",
            f"高相似段落数：{item['similarity']['high_similarity_paragraphs']}",
            f"高相似标题数：{item['similarity']['high_similarity_headings']}",
            f"模板复制风险：{'是' if item['similarity']['template_copy_risk'] else '否'}",
            f"结构过度雷同风险：{'是' if item['similarity']['structure_risk'] else '否'}",
            f"是否存在夸大承诺表达：{'是' if item['compliance']['has_risk'] else '否'}",
            f"是否已自动修复：{'是' if item['rewritten'] else '否'}",
            f"最终检查结论：{item['final_conclusion']}",
        ]
