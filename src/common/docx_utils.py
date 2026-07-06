from __future__ import annotations

from pathlib import Path
import re


class DocxDependencyError(RuntimeError):
    """Raised when python-docx is required but unavailable."""


def _load_document_module():
    try:
        from docx import Document  # type: ignore
        from docx.shared import Pt  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise DocxDependencyError(
            "缺少 python-docx 依赖，无法读写 docx。请执行 pip install -r requirements.txt。"
        ) from exc
    return Document, Pt


def write_sections_docx(path: Path, title: str, sections: list[tuple[str, list[str]]]) -> None:
    Document, Pt = _load_document_module()
    doc = Document()
    doc.add_heading(title, level=0)
    normal_style = doc.styles["Normal"]
    normal_style.font.name = "Microsoft YaHei"
    normal_style.font.size = Pt(11)
    for heading, paragraphs in sections:
        doc.add_heading(heading, level=1)
        for paragraph in paragraphs:
            _write_paragraph(doc, paragraph)
    doc.save(path)


def write_article_docx(path: Path, title: str, blocks: list[dict[str, str]]) -> None:
    Document, Pt = _load_document_module()
    doc = Document()
    doc.add_heading(title, level=0)
    normal_style = doc.styles["Normal"]
    normal_style.font.name = "Microsoft YaHei"
    normal_style.font.size = Pt(11)
    for block in blocks:
        kind = block.get("type", "paragraph")
        text = block.get("text", "").strip()
        if not text:
            continue
        if kind == "heading":
            doc.add_heading(_strip_markdown(text), level=1)
        elif kind == "subheading":
            doc.add_heading(_strip_markdown(text), level=2)
        elif kind == "list":
            _add_list_item(doc, text)
        else:
            paragraph = doc.add_paragraph()
            _write_inline_text(paragraph, text)
    doc.save(path)


def read_docx_text(path: Path) -> str:
    Document, _ = _load_document_module()
    doc = Document(path)
    return "\n".join(paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip())


def _write_paragraph(doc, text: str) -> None:
    paragraph = doc.add_paragraph()
    _write_inline_text(paragraph, text)


def _add_list_item(doc, text: str) -> None:
    if re.match(r"^\d+[.、]\s*", text):
        paragraph = doc.add_paragraph(style="List Number")
    else:
        paragraph = doc.add_paragraph(style="List Bullet")
    _write_inline_text(paragraph, _strip_markdown(text))


def _write_inline_text(paragraph, text: str) -> None:
    parts = re.split(r"(\*\*.*?\*\*)", text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) >= 4:
            run = paragraph.add_run(part[2:-2])
            run.bold = True
        else:
            run = paragraph.add_run(_strip_markdown(part))
            run.bold = False


def _strip_markdown(text: str) -> str:
    text = re.sub(r"^\s*#+\s*", "", text)
    text = re.sub(r"^\s*[-*]\s*", "", text)
    return text
