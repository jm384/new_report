from __future__ import annotations

from src.common.text_utils import estimate_word_count
from src.common.text_utils import replace_phrases


class AutoRewriter:
    def __init__(self, context, llm_client) -> None:
        self.context = context
        self.llm_client = llm_client

    def rewrite_if_needed(self, article: dict, result: dict) -> tuple[dict | None, list[str]]:
        issues = self._collect_issues(result)
        if not issues:
            self.context.logger.info("CHECK", "是否执行自动修复：否")
            return None, []

        self.context.logger.info("CHECK", "是否执行自动修复：是")
        actions = ["执行规则替换，先移除明显夸大或绝对化措辞。"]
        text = replace_phrases(article["text"], self.context.settings.cautious_replacements)
        article = {**article, "text": text}
        article["blocks"] = self._ensure_blocks(text)

        if self.llm_client.is_configured and self.context.settings.llm.enable_check_and_rewrite:
            article = self._rewrite_with_llm(article, issues)
            actions.append("调用 LLM 按问题清单重写正文，补足结构并清除说明腔。")

        return article, actions

    def _rewrite_with_llm(self, article: dict, issues: list[str]) -> dict:
        prompt = f"""
请把下面这篇中文法律科普文章直接改成可以发布的完整成稿，并重点修复这些问题：
{chr(10).join(f"- {issue}" for issue in issues)}

要求：
1. 直接输出完整文章，不要任何说明或前言。
2. 第一行必须是正式文章标题，不要用“温和提醒”“古灵王律师团寄语”做标题。
3. 必须有多个小标题，结构完整。
4. 语言自然、顺畅，不要像提纲、说明稿或指令。
5. 减少默认背景词的重复，不要过度重复“纽约”“华人”。
6. 涉及责任、保险、法律规则时要保守表述，不要绝对化。
7. 输出可直接用于 Word 的正文，不要 Markdown。

文章：
{article['text']}
""".strip()
        rewritten_text = self.llm_client.generate_text(
            phase="CHECK",
            purpose="文章自动修复",
            prompt=prompt,
            system_prompt="你是中文法律科普文章修订助手，只输出可发布的完整成稿。",
            temperature=0.35,
        )
        article["text"] = rewritten_text
        article["blocks"] = self._ensure_blocks(rewritten_text)
        title = article.get("title", "")
        if article["blocks"] and article["blocks"][0]["type"] == "heading":
            title = article["blocks"][0]["text"]
        article["title"] = title
        article["word_count"] = estimate_word_count(rewritten_text)
        return article

    def _ensure_blocks(self, text: str) -> list[dict]:
        parsed = []
        for index, line in enumerate([line.strip() for line in text.splitlines() if line.strip()]):
            if index == 0:
                parsed.append({"type": "heading", "text": line})
            elif self._looks_like_subheading(line):
                parsed.append({"type": "subheading", "text": line})
            else:
                parsed.append({"type": "paragraph", "text": line})
        return parsed

    def _looks_like_subheading(self, line: str) -> bool:
        import re

        if len(line) > 40:
            return False
        return bool(
            re.match(
                r"^(第[一二三四五六七八九十0-9]+(部分|点|步|章|节)?[：:、.]?|[一二三四五六七八九十0-9]+[、.．]|(首先|其次|再次|最后|另外|还有)[：:，,]?)",
                line,
            )
        )

    def _collect_issues(self, result: dict) -> list[str]:
        issues: list[str] = []
        for group in ("structure", "language", "compliance"):
            issues.extend(result.get(group, {}).get("issues", []))
        return list(dict.fromkeys(issues))
