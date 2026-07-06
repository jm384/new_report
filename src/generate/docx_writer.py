from __future__ import annotations

from pathlib import Path
import re

from src.common.docx_utils import DocxDependencyError, write_article_docx
from src.common.file_utils import ensure_dir, sanitize_filename


class BlogDocxWriter:
    def __init__(self, context, output_dir: Path | None = None) -> None:
        self.context = context
        self.output_dir = output_dir or self.context.paths.generated_blog_articles

    def write(self, article_payload: dict, file_suffix: str = "_中文法律科普博客") -> Path:
        ensure_dir(self.output_dir)
        title = article_payload["title"]
        path = self.output_dir / f"{sanitize_filename(title)}{file_suffix}.docx"
        try:
            styled_blocks = self._normalize_blocks(article_payload["blocks"], title)
            write_article_docx(path, title, styled_blocks)
        except DocxDependencyError as exc:
            self.context.action_manager.require_and_raise(
                phase="GENERATE",
                topic=article_payload["topic"],
                problem=str(exc),
                attempted_actions=["尝试使用 python-docx 写入博客文章 docx"],
                cannot_continue_reason="缺少 docx 写入依赖，无法输出必需的文章文件。",
                user_actions=["请执行 pip install -r requirements.txt 安装依赖。"],
                suggested_materials=["requirements.txt", "pip 安装日志"],
                generated_files=self.context.created_files_as_strings,
            )
        self.context.logger.info("GENERATE", f"文章保存路径：{path}")
        self.context.logger.info("GENERATE", "文章生成成功")
        return path

    def _normalize_blocks(self, blocks: list[dict[str, str]], title: str) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for block in blocks:
            text = self._cleanup_text(block.get("text", ""))
            if not text:
                continue
            kind = block.get("type", "paragraph")
            if kind == "heading" and text == title:
                continue
            if not normalized and text == title:
                continue
            if kind == "paragraph" and self._looks_like_list(text):
                kind = "list"
            normalized.append({"type": kind, "text": text})
        return normalized

    def _cleanup_text(self, text: str) -> str:
        cleaned = text.strip()
        cleaned = re.sub(r"^\s*#+\s*", "", cleaned)
        cleaned = re.sub(r"^\s*[-*]\s+", "", cleaned)
        cleaned = cleaned.replace("###", "").replace("##", "")
        return cleaned

    def _looks_like_list(self, text: str) -> bool:
        return bool(re.match(r"^\d+[.、)\s]", text))
