from __future__ import annotations

from src.common.action_required import PhaseHaltError
from src.common.llm_client import LLMQuotaExceededError
from src.common.text_utils import estimate_word_count
from src.generate.prompt_builder import PromptBuilder


class BlogGenerator:
    def __init__(self, context, llm_client) -> None:
        self.context = context
        self.llm_client = llm_client
        self.prompt_builder = PromptBuilder()

    def generate(self, *, topic: str, style_profile: dict, sources: list[dict]) -> dict:
        self.context.logger.info(
            "GENERATE",
            f"模板分析结果：{style_profile.get('template_count', 0)} 篇模板",
        )
        self.context.logger.info("GENERATE", f"当前生成主题：{topic}")
        self.context.logger.info(
            "GENERATE",
            f"目标字数：{self.context.settings.generation.target_article_word_count}",
        )

        if not self.llm_client.is_configured or not self.context.settings.llm.enable_blog_generation:
            self.context.action_manager.require_and_raise(
                phase="GENERATE",
                topic=topic,
                problem="博客文章生成需要 LLM，但当前未配置可用的 LLM。",
                attempted_actions=[
                    "检查 .env 中的 LLM_API_KEY",
                    "检查是否启用 LLM_ENABLE_BLOG_GENERATION",
                ],
                cannot_continue_reason="高质量中文法律科普文章生成依赖 LLM。",
                user_actions=[
                    "请在 .env 中补充 LLM_API_KEY。",
                    "确认 LLM_BASE_URL 和 LLM_MODEL 配置正确。",
                ],
                suggested_materials=[".env 配置", "LLM 服务连通信息"],
                generated_files=self.context.created_files_as_strings,
            )

        prompt = self.prompt_builder.build_blog_prompt(
            topic=topic,
            style_profile=style_profile,
            sources=sources,
            target_words=self.context.settings.generation.target_article_word_count,
        )
        self.context.logger.info("GENERATE", "正在调用 LLM 生成文章")
        try:
            article_text = self.llm_client.generate_text(
                phase="GENERATE",
                purpose="中文法律科普博客生成",
                prompt=prompt,
                system_prompt="你是纽约州华人律师事务所的中文法律科普写作助手。",
                temperature=0.6,
            )
        except LLMQuotaExceededError as exc:
            self.context.action_manager.require_and_raise(
                phase="GENERATE",
                topic=topic,
                problem=f"LLM 配额不足，无法继续生成文章：{exc}",
                attempted_actions=[
                    "读取 collect 阶段产出的主题、来源和模板风格数据",
                    "调用 LLM 生成中文法律科普博客文章",
                ],
                cannot_continue_reason="文章生成必须依赖 LLM，当前配额不足无法产出可靠结果。",
                user_actions=[
                    "请补充可用配额后重新运行 generate 阶段。",
                    "或者切换到仍有余额的 LLM 服务后重试。",
                ],
                suggested_materials=["LLM 账户配额信息", ".env 中的 LLM 配置"],
                generated_files=self.context.created_files_as_strings,
            )

        blocks = self._parse_blocks(article_text)
        word_count = estimate_word_count(article_text)
        include_brand = self.context.rng.random() < self.context.settings.generation.include_brand_message_probability
        include_phone = self.context.rng.random() < self.context.settings.generation.include_phone_cta_probability
        if include_brand:
            blocks.append({"type": "heading", "text": self.context.settings.generation.brand_message_title})
            blocks.append({"type": "paragraph", "text": self.context.settings.generation.brand_message_body})
        if include_phone:
            blocks.append({"type": "paragraph", "text": self.context.settings.generation.phone_cta_text})
        self.context.logger.info("GENERATE", f"是否加入律所寄语：{'是' if include_brand else '否'}")
        self.context.logger.info("GENERATE", f"是否加入电话咨询语：{'是' if include_phone else '否'}")

        title = self._extract_title(blocks, topic)
        blocks = self._ensure_structure(blocks, topic)
        text = "\n".join(block["text"] for block in blocks if block["text"].strip())
        return {
            "topic": topic,
            "title": title,
            "word_count": word_count,
            "blocks": blocks,
            "text": text,
            "style_profile": style_profile,
            "source_count": len(sources),
            "include_brand_message": include_brand,
            "include_phone_cta": include_phone,
        }

    def _parse_blocks(self, article_text: str) -> list[dict[str, str]]:
        blocks: list[dict[str, str]] = []
        current_heading = None
        for raw_line in article_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if self._looks_like_heading(line):
                current_heading = self._clean_heading(line)
                blocks.append({"type": "heading", "text": current_heading})
                continue
            if self._looks_like_subheading(line):
                blocks.append({"type": "subheading", "text": self._clean_heading(line)})
                continue
            if self._looks_like_list_item(line):
                blocks.append({"type": "list", "text": line})
                continue
            if self._looks_like_meta_line(line):
                continue
            blocks.append({"type": "paragraph", "text": line})
        if not blocks:
            raise PhaseHaltError("LLM 未生成可解析的文章内容。")
        return blocks

    def _looks_like_heading(self, line: str) -> bool:
        return line.startswith(("标题：", "题目：")) or (len(line) <= 28 and "：" not in line)

    def _looks_like_subheading(self, line: str) -> bool:
        return line.startswith(("小标题：", "部分：", "一、", "二、", "三、", "四、", "五、", "六、"))

    def _looks_like_list_item(self, line: str) -> bool:
        return bool(line[:3].isdigit() or line.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.")))

    def _looks_like_meta_line(self, line: str) -> bool:
        meta_prefixes = ("导语：", "正文：", "结尾提醒：", "备注：")
        return line.startswith(meta_prefixes)

    def _clean_heading(self, line: str) -> str:
        for prefix in ("标题：", "题目：", "小标题：", "部分："):
            if line.startswith(prefix):
                return line[len(prefix) :].strip()
        return line.strip()

    def _extract_title(self, blocks: list[dict[str, str]], topic: str) -> str:
        if blocks and blocks[0]["type"] == "heading":
            return blocks[0]["text"]
        for block in blocks:
            if block["type"] == "heading" and len(block["text"]) > 3:
                return block["text"]
        return topic

    def _ensure_structure(self, blocks: list[dict[str, str]], topic: str) -> list[dict[str, str]]:
        has_heading = any(block["type"] == "heading" for block in blocks)
        has_subheading = any(block["type"] == "subheading" for block in blocks)
        if not has_heading:
            blocks.insert(0, {"type": "heading", "text": topic})
        if not has_subheading:
            blocks.insert(1, {"type": "subheading", "text": "一、先把基本情况说清楚"})
            blocks.insert(2, {"type": "paragraph", "text": "在判断责任或理赔问题前，先把地点、经过、受伤情况和证据线索梳理清楚。"})
        if estimate_word_count("\n".join(block["text"] for block in blocks)) < self.context.settings.generation.min_article_word_count:
            blocks.extend(
                [
                    {"type": "subheading", "text": "二、补充说明"},
                    {
                        "type": "paragraph",
                        "text": "如果事实细节还不完整，建议继续补充现场照片、就医记录、沟通记录和保留凭证，以便更准确地判断后续处理方式。",
                    },
                    {"type": "subheading", "text": "三、温和提醒"},
                    {
                        "type": "paragraph",
                        "text": "遇到类似情况时，先把证据和时间线整理好，再决定下一步如何沟通、报案或咨询专业人士，会更稳妥。",
                    },
                ]
            )
        return blocks
