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
        return {
            "topic": topic,
            "title": title,
            "word_count": word_count,
            "blocks": blocks,
            "text": "\n".join(block["text"] for block in blocks if block["text"].strip()),
            "style_profile": style_profile,
            "source_count": len(sources),
            "include_brand_message": include_brand,
            "include_phone_cta": include_phone,
        }

    def _parse_blocks(self, article_text: str) -> list[dict[str, str]]:
        blocks: list[dict[str, str]] = []
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
        if not blocks:
            raise PhaseHaltError("LLM 未生成可解析的文章内容。")
        return blocks

    def _extract_title(self, blocks: list[dict[str, str]], topic: str) -> str:
        for block in blocks:
            if block["type"] in {"heading", "subheading"}:
                return block["text"]
        return topic
