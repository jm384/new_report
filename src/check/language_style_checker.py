from __future__ import annotations

import re


META_OPENING_MARKERS = (
    "我先按你的要求",
    "我先把资料里的重点",
    "下面按",
    "以下按",
    "我会按",
    "本文将按",
)
BAD_TITLES = {"温和提醒", "古灵王律师团寄语"}
TAIL_SECTION_MARKERS = ("温和提醒", "古灵王律师团寄语")


class LanguageStyleChecker:
    def __init__(self, context, llm_client) -> None:
        self.context = context
        self.llm_client = llm_client

    def check(self, article: dict, style_profile: dict) -> dict:
        text = article.get("text", "")
        title = (article.get("title") or "").strip()
        issues: list[str] = []

        if title in BAD_TITLES:
            issues.append("文章标题被错误写成附属栏目标题")
        if any(text.startswith(marker) for marker in META_OPENING_MARKERS):
            issues.append("文章开头仍有说明性元话术")
        if self._has_meta_paragraph(article):
            issues.append("正文中混入说明性元话术")
        if "标题：" in text or "导语：" in text or "**" in text or "#" in text:
            issues.append("正文中仍有说明标签或 Markdown 痕迹")
        if any(marker in text for marker in TAIL_SECTION_MARKERS):
            issues.append("正文残留附属栏目措辞，影响成稿感")
        if text.count("纽约") > 18:
            issues.append("“纽约”重复偏多，读感略显僵硬")
        if text.count("华人") > 3:
            issues.append("“华人”表述重复偏多")
        if self._looks_stiff(text):
            issues.append("标题或正文语气偏硬，像提纲或说明稿")
        if self._style_gap(text, style_profile):
            issues.append("整体阅读节奏与模板风格不够接近")

        return {
            "has_problem": bool(issues),
            "issues": issues,
        }

    def _has_meta_paragraph(self, article: dict) -> bool:
        paragraphs = [block.get("text", "") for block in article.get("blocks", []) if block.get("type") == "paragraph"]
        for paragraph in paragraphs[:3]:
            if any(paragraph.startswith(marker) for marker in META_OPENING_MARKERS):
                return True
        return False

    def _looks_stiff(self, text: str) -> bool:
        stiff_markers = ["以下从", "分为以下", "本文主要从", "下面分几部分"]
        return any(marker in text for marker in stiff_markers)

    def _style_gap(self, text: str, style_profile: dict) -> bool:
        if not style_profile or style_profile.get("template_count", 0) < 3:
            return False
        paragraph_count = len([line for line in text.splitlines() if line.strip()])
        heading_like_count = len(re.findall(r"^[一二三四五六七八九十0-9]+[、.]", text, flags=re.M))
        return paragraph_count < 10 or heading_like_count < 3
