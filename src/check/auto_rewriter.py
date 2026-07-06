from __future__ import annotations

from src.common.docx_utils import write_article_docx
from src.common.text_utils import replace_phrases


class AutoRewriter:
    def __init__(self, context, llm_client) -> None:
        self.context = context
        self.llm_client = llm_client

    def rewrite_if_needed(self, article: dict, result: dict) -> dict | None:
        need_rewrite = False
        structure_score = result["structure"]["score"]
        language_score = result["language"]["score"]
        similarity_result = result["similarity"]
        compliance_result = result["compliance"]

        if compliance_result["has_risk"]:
            need_rewrite = True
        if structure_score < self.context.settings.check.structure_style_pass_score:
            need_rewrite = True
        if language_score < self.context.settings.check.language_style_pass_score:
            need_rewrite = True
        if similarity_result["template_copy_risk"] or similarity_result["structure_risk"]:
            need_rewrite = True

        self.context.logger.info("CHECK", f"是否执行自动修复：{'是' if need_rewrite else '否'}")
        if not need_rewrite:
            return None

        text = article["text"]
        updated_text = replace_phrases(text, self.context.settings.cautious_replacements)
        article = {**article, "text": updated_text}
        article["blocks"] = self._rebuild_blocks(article["blocks"], updated_text)

        remaining_need_llm = (
            structure_score < self.context.settings.check.structure_style_pass_score
            or language_score < self.context.settings.check.language_style_pass_score
            or similarity_result["template_copy_risk"]
            or similarity_result["structure_risk"]
        )
        if remaining_need_llm:
            if not self.llm_client.is_configured or not self.context.settings.llm.enable_check_and_rewrite:
                self.context.action_manager.require_and_raise(
                    phase="CHECK",
                    topic=article["topic"],
                    problem="文章需要进一步重写或降重，但当前没有可用的 LLM。",
                    attempted_actions=[
                        "执行规则替换，修正夸大承诺表达",
                        "评估结构、语言风格和模板相似度风险",
                    ],
                    cannot_continue_reason="高质量重写需要 LLM 支持。",
                    user_actions=[
                        "请在 .env 中补充 LLM_API_KEY 并重跑 check 阶段。",
                        "或者手动修改文章后再重新运行检查。",
                    ],
                    suggested_materials=[".env 配置", "待修改文章"],
                    generated_files=self.context.created_files_as_strings,
                )
            article = self._rewrite_with_llm(article)

        if article.get("output_path"):
            write_article_docx(article["output_path"], article["title"], article["blocks"])
        return article

    def _rewrite_with_llm(self, article: dict) -> dict:
        prompt = f"""
请在不改变主题的前提下，重写下面文章，使其：
1. 更自然、更顺畅
2. 降低与模板的相似表达
3. 避免夸大承诺
4. 保持稳重、亲切、专业

文章：
{article['text']}

输出格式：
标题：...
导语：...
小标题：...
正文：...
结尾提醒：...
""".strip()
        rewritten_text = self.llm_client.generate_text(
            phase="CHECK",
            purpose="文章自动重写",
            prompt=prompt,
            system_prompt="你是中文法律科普文章重写助手。",
            temperature=0.5,
        )
        article["text"] = rewritten_text
        article["blocks"] = self._parse_rewritten_blocks(rewritten_text)
        return article

    def _rebuild_blocks(self, old_blocks: list[dict], new_text: str) -> list[dict]:
        paragraphs = [line.strip() for line in new_text.splitlines() if line.strip()]
        blocks = []
        old_types = [block["type"] for block in old_blocks]
        for index, paragraph in enumerate(paragraphs):
            block_type = old_types[index] if index < len(old_types) else "paragraph"
            blocks.append({"type": block_type, "text": paragraph})
        return blocks

    def _parse_rewritten_blocks(self, article_text: str) -> list[dict]:
        blocks = []
        for raw_line in article_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("标题："):
                blocks.append({"type": "heading", "text": line.replace("标题：", "", 1).strip()})
            elif line.startswith("导语："):
                blocks.append({"type": "paragraph", "text": line.replace("导语：", "", 1).strip()})
            elif line.startswith("小标题："):
                blocks.append({"type": "subheading", "text": line.replace("小标题：", "", 1).strip()})
            elif line.startswith("正文："):
                blocks.append({"type": "paragraph", "text": line.replace("正文：", "", 1).strip()})
            elif line.startswith("结尾提醒："):
                blocks.append({"type": "subheading", "text": "温和提醒"})
                blocks.append({"type": "paragraph", "text": line.replace("结尾提醒：", "", 1).strip()})
            else:
                blocks.append({"type": "paragraph", "text": line})
        return blocks
