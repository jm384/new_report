from __future__ import annotations


ABSOLUTE_RISK_MARKERS = [
    ("保证", "出现保证性承诺，需要改成条件化表述"),
    ("一定胜诉", "把诉讼结果写成必然发生，法律表述过于绝对"),
    ("一定赔", "把赔偿结果写成必然发生，保险表述过于绝对"),
    ("百分之百", "出现绝对化措辞，需要改成保守表述"),
    ("包赢", "出现结果承诺，法律科普文章不宜使用"),
]
SPECULATIVE_PHRASES = ("可能让人误解", "容易让人误以为", "容易误导读者", "读起来像是", "倾向于让人觉得")


class ComplianceChecker:
    def __init__(self, context, llm_client) -> None:
        self.context = context
        self.llm_client = llm_client

    def check(self, article: dict) -> dict:
        text = article.get("text", "")
        issues: list[str] = []

        for marker, issue in ABSOLUTE_RISK_MARKERS:
            if marker in text:
                issues.append(issue)

        if self.llm_client.is_configured and self.context.settings.llm.enable_check_and_rewrite:
            issues.extend(self._check_with_llm(article))

        issues = list(dict.fromkeys(issue for issue in issues if issue))
        suggestions = []
        if issues:
            suggestions.append("把相关表述改成结合事实、证据、保险条款和适用规则分别判断的写法。")

        return {
            "has_problem": bool(issues),
            "issues": issues,
            "suggestions": suggestions,
        }

    def _check_with_llm(self, article: dict) -> list[str]:
        prompt = f"""
请检查下面这篇中文法律科普文章，是否存在需要阻止发布的明确纽约法律或保险表述风险。

只允许识别这三类问题：
1. 把责任、赔偿、胜诉或保险结果写成必然发生。
2. 把某项纽约规则写成所有案件都自动适用。
3. 明显写错法律关系或保险关系，例如把不同救济路径说成固定冲突或固定替代关系。

不要因为“读者可能联想过度”“语气不够严谨”就报问题。
不要输出猜测，不要输出需要律师进一步研究的灰区。

输出必须是 JSON 数组：
- 没有明确风险时输出 []
- 有明确风险时输出精炼问题列表，例如
["把赔偿结果写成必然发生", "把某项规则写成所有案件都自动适用"]

文章：
{article.get('text', '')[:5000]}
""".strip()
        try:
            payload = self.llm_client.generate_json(
                phase="CHECK",
                purpose="纽约法与保险风险复核",
                prompt=prompt,
                system_prompt="你是纽约法律科普审稿助手，只输出合法 JSON 数组。",
                temperature=0.0,
            )
        except Exception as exc:
            self.context.logger.warning("CHECK", f"纽约法风险复核失败，改用规则结果：{exc}")
            return []

        if not isinstance(payload, list):
            return []

        filtered: list[str] = []
        for item in payload:
            issue = str(item).strip()
            if not issue:
                continue
            if any(phrase in issue for phrase in SPECULATIVE_PHRASES):
                continue
            filtered.append(issue)
        return filtered
