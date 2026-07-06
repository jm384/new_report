from __future__ import annotations

from pathlib import Path

from src.common.docx_utils import write_sections_docx


class ReportBuilder:
    def __init__(self, context) -> None:
        self.context = context

    def write(self, results: list[dict], run_root: Path) -> None:
        report_root = self.context.paths.check
        docx_path = report_root / "quality_check_report.docx"
        self._write_docx(docx_path, results, run_root)
        self.context.record_file(docx_path)

    def summarize_result(self, result: dict) -> str:
        issues = []
        issues.extend(result.get("structure", {}).get("issues", []))
        issues.extend(result.get("language", {}).get("issues", []))
        issues.extend(result.get("similarity", {}).get("issues", []))
        issues.extend(result.get("compliance", {}).get("issues", []))
        if not issues:
            return "已检查并修复，整体可发布。"
        return "已完成检查和修复，仍建议人工复核少量细节。"

    def _write_docx(self, path: Path, results: list[dict], run_root: Path) -> None:
        sections: list[tuple[str, list[str]]] = [
            (
                "一、报告说明",
                [
                    f"本次运行时间：{self.context.run_id}",
                    f"本次输出目录：{run_root}",
                    "本报告只检查四类问题：文章结构是否遗漏、标题和内容是否僵硬、阅读风格是否接近模板、法律与保险表述是否存在明显风险。",
                    "发现问题后，程序会先做规则修复，再按需调用 LLM 做二次修订，最终文章保存在 final_articles 中。",
                ],
            ),
        ]
        for item in results:
            sections.append((f"二、{item['title']}", self._item_doc_lines(item)))
        write_sections_docx(path, f"质量检查报告：{self.context.run_id}", sections)

    def _item_doc_lines(self, item: dict) -> list[str]:
        lines = [
            f"主题：{item['topic']}",
            f"原文路径：{item['article_path']}",
            f"最终文章路径：{item.get('final_article_path', '') or '无'}",
            "检查到的问题：",
        ]
        for group in ("structure", "language", "similarity", "compliance"):
            issues = item.get(group, {}).get("issues", [])
            if issues:
                lines.extend([f"- {issue}" for issue in issues])
        if item.get("rewritten"):
            lines.append("已修复：是")
        else:
            lines.append("已修复：否")
        lines.append(f"检查结论：{item.get('final_conclusion', '')}")
        return lines
