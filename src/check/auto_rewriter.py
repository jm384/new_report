from __future__ import annotations

from src.common.docx_utils import write_article_docx
from src.common.text_utils import replace_phrases


class AutoRewriter:
    def __init__(self, context, llm_client) -> None:
        self.context = context
        self.llm_client = llm_client

    def rewrite_if_needed(self, article: dict, result: dict) -> dict | None:
        issues = []
        issues.extend(result.get("structure", {}).get("issues", []))
        issues.extend(result.get("language", {}).get("issues", []))
        issues.extend(result.get("similarity", {}).get("issues", []))
        issues.extend(result.get("compliance", {}).get("issues", []))

        if not issues:
            self.context.logger.info("CHECK", "是否执行自动修复：否")
            return None

        self.context.logger.info("CHECK", "是否执行自动修复：是")
        text = replace_phrases(article["text"], self.context.settings.cautious_replacements)
        article = {**article, "text": text}
        article["blocks"] = self._ensure_blocks(article.get("blocks", []), text)

        if self.llm_client.is_configured and self.context.settings.llm.enable_check_and_rewrite:
            article = self._rewrite_with_llm(article, issues)

        if article.get("output_path"):
            write_article_docx(article["output_path"], article["title"], article["blocks"])
        return article

    def _rewrite_with_llm(self, article: dict, issues: list[str]) -> dict:
        prompt = f"""
请在不改变主题的前提下重写下面文章，重点修复这些问题：
{chr(10).join(f"- {issue}" for issue in issues)}

要求：
1. 语言更自然流畅。
2. 结构完整，补足缺失的小标题。
3. 减少重复的“纽约”“华人”表述。
4. 保持法律科普语气，避免夸大承诺。
5. 直接输出可用于 Word 的正文，不要 Markdown。

文章：
{article['text']}
""".strip()
        rewritten_text = self.llm_client.generate_text(
            phase="CHECK",
            purpose="文章自动修复",
            prompt=prompt,
            system_prompt="你是中文法律科普文章修订助手。",
            temperature=0.45,
        )
        article["text"] = rewritten_text
        article["blocks"] = self._ensure_blocks([], rewritten_text)
        return article

    def _ensure_blocks(self, blocks: list[dict], text: str) -> list[dict]:
        parsed = []
        for line in [line.strip() for line in text.splitlines() if line.strip()]:
            if line.startswith(("一、", "二、", "三、", "四、", "五、", "六、")):
                parsed.append({"type": "subheading", "text": line})
            elif len(line) <= 26 and "：" not in line:
                parsed.append({"type": "heading", "text": line})
            else:
                parsed.append({"type": "paragraph", "text": line})
        return parsed or blocks
