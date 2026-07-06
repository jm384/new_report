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
        issues.extend(result.get("compliance", {}).get("issues", []))
        if not issues:
            return "修复后通过检查，可作为最终文章使用。"
        return "修复后仍存在风险，建议人工复核。"

    def _write_docx(self, path: Path, results: list[dict], run_root: Path) -> None:
        sections: list[tuple[str, list[str]]] = [
            (
                "一、报告说明",
                [
                    f"本次运行时间：{self.context.run_id}",
                    f"本次输出目录：{run_root}",
                    "本报告只检查四类问题：结构是否遗漏、标题和语言是否僵硬、阅读风格是否接近模板、纽约法律与保险表述是否存在明显风险。",
                    "发现问题后，程序会先做规则修复，再按需调用 LLM 重写，最终文章保存在 final_articles 中。",
                ],
            ),
        ]
        for index, item in enumerate(results, start=1):
            sections.append((f"二.{index} {item['title']}", self._item_doc_lines(item)))
        write_sections_docx(path, f"质量检查报告：{self.context.run_id}", sections)

    def _item_doc_lines(self, item: dict) -> list[str]:
        lines = [
            f"检查文章：{item['title']}",
            f"主题：{item['topic']}",
            f"原文路径：{item['article_path']}",
            f"最终文章路径：{item.get('final_article_path', '') or '无'}",
            f"是否触发自动补采：{'是' if item.get('supplemental_source_count', 0) > 0 else '否'}",
            f"补采来源数量：{item.get('supplemental_source_count', 0)}",
            "发现的问题：",
        ]
        found_any = False
        for group in ("structure", "language", "compliance"):
            issues = item.get(group, {}).get("issues", [])
            if issues:
                found_any = True
                lines.extend([f"- {issue}" for issue in issues])
        if not found_any:
            lines.append("- 未发现需要修复的问题")

        lines.append("执行的修复：")
        repair_actions = item.get("repair_actions", [])
        if repair_actions:
            lines.extend([f"- {action}" for action in repair_actions])
        else:
            lines.append("- 未触发修复动作")

        lines.append(f"修复后结论：{item.get('final_conclusion', '')}")
        return lines
