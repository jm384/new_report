from __future__ import annotations


class ComplianceChecker:
    def __init__(self, context) -> None:
        self.context = context

    def check(self, article: dict) -> dict:
        text = article.get("text", "")
        issues = []
        if "绝对" in text and "保证" in text:
            issues.append("存在过强承诺")
        if "一定胜诉" in text or "必胜" in text:
            issues.append("存在夸大承诺")
        return {
            "has_problem": bool(issues),
            "issues": issues,
        }
