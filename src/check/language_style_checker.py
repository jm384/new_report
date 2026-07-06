from __future__ import annotations


class LanguageStyleChecker:
    def __init__(self, context, llm_client) -> None:
        self.context = context
        self.llm_client = llm_client

    def check(self, article: dict, style_profile: dict) -> dict:
        text = article.get("text", "")
        issues = []
        if text.count("纽约") > 12:
            issues.append("纽约出现过多")
        if text.count("华人") > 5:
            issues.append("华人表述过多")
        if "标题：" in text or "导语：" in text or "**" in text or "#" in text:
            issues.append("存在 Markdown 或说明性标签")
        if len(text) < 1800:
            issues.append("篇幅偏短")
        style_gap = self._style_gap(text, style_profile)
        if style_gap:
            issues.append(style_gap)
        return {
            "has_problem": bool(issues),
            "issues": issues,
        }

    def _style_gap(self, text: str, style_profile: dict) -> str:
        if not style_profile:
            return ""
        if style_profile.get("template_count", 0) < 3:
            return ""
        if len([line for line in text.splitlines() if line.strip()]) < 8:
            return "阅读节奏偏单薄，和模板风格不够接近"
        return ""
