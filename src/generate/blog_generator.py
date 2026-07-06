from __future__ import annotations

import re

from src.common.action_required import PhaseHaltError
from src.common.llm_client import LLMQuotaExceededError
from src.common.text_utils import estimate_word_count
from src.generate.prompt_builder import PromptBuilder


META_OPENING_MARKERS = (
    "我先按你的要求",
    "我先把资料里的重点",
    "下面按",
    "以下按",
    "我会按",
    "本文将按",
)
META_LINE_MARKERS = (
    "标题：",
    "导语：",
    "正文：",
    "备注：",
)
BAD_TITLE_MARKERS = {"温和提醒", "古灵王律师团寄语"}
TAIL_SECTION_MARKERS = ("温和提醒", "古灵王律师团寄语")


class BlogGenerator:
    def __init__(self, context, llm_client) -> None:
        self.context = context
        self.llm_client = llm_client
        self.prompt_builder = PromptBuilder()

    def generate(
        self,
        *,
        topic: str,
        style_profile: dict,
        sources: list[dict],
        query_result: dict,
        searcher,
        scraper,
        source_filter,
        research_builder,
    ) -> tuple[dict, list[dict] | None]:
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

        attempts: list[dict] = []
        working_sources = list(sources)
        supplemental_source_count = 0

        for attempt_index in range(1, 3):
            payload = self._generate_once(topic, style_profile, working_sources, strict_retry=attempt_index > 1)
            failures = self._quality_gate_failures(payload, topic)
            attempts.append({"attempt": attempt_index, "mode": "generate", "failures": failures})
            if not failures:
                payload["generation_attempts"] = attempts
                payload["supplemental_source_count"] = supplemental_source_count
                payload["quality_gate_failures"] = []
                return payload, None

        supplement_result = self._supplement_sources(
            topic=topic,
            query_result=query_result,
            sources=working_sources,
            searcher=searcher,
            scraper=scraper,
            source_filter=source_filter,
            research_builder=research_builder,
        )
        if supplement_result is not None:
            working_sources = supplement_result
            supplemental_source_count = max(0, len(working_sources) - len(sources))
            payload = self._generate_once(topic, style_profile, working_sources, strict_retry=True)
            failures = self._quality_gate_failures(payload, topic)
            attempts.append({"attempt": 3, "mode": "supplemental_regenerate", "failures": failures})
            if not failures:
                payload["generation_attempts"] = attempts
                payload["supplemental_source_count"] = supplemental_source_count
                payload["quality_gate_failures"] = []
                return payload, working_sources

        final_failures = attempts[-1]["failures"] if attempts else ["未生成出可用正文"]
        self.context.action_manager.require_and_raise(
            phase="GENERATE",
            topic=topic,
            problem=f"文章生成多次尝试后仍未达标：{'；'.join(final_failures)}",
            attempted_actions=[
                "基于现有素材重试生成文章",
                "对当前主题补采更多来源后重新生成",
            ],
            cannot_continue_reason="当前生成结果仍包含说明性废话、结构不完整或信息量不足，不能作为可交付文章。",
            user_actions=[
                "请检查 collect 阶段素材质量，必要时补充更多权威来源。",
                "确认 LLM 输出是否稳定，再重新运行 generate。",
            ],
            suggested_materials=["1_collect/data/filtered_sources.json", "2_generate/data/generation_metadata.json"],
            generated_files=self.context.created_files_as_strings,
        )

    def _generate_once(
        self,
        topic: str,
        style_profile: dict,
        sources: list[dict],
        *,
        strict_retry: bool,
    ) -> dict:
        prompt = self.prompt_builder.build_blog_prompt(
            topic=topic,
            style_profile=style_profile,
            sources=sources,
            target_words=self.context.settings.generation.target_article_word_count,
        )
        if strict_retry:
            prompt += (
                "\n\n额外要求：\n"
                "1. 不要写任何类似“我先按你的要求重写”“下面按几个部分来写”的说明性句子。\n"
                "2. 不要把“温和提醒”或“古灵王律师团寄语”当作文章标题。\n"
                "3. 第一行必须是正式文章标题，后文必须有多个小标题。\n"
                "4. 必须输出完整成稿，不要只给提纲或开头。\n"
            )
        self.context.logger.info("GENERATE", "正在调用 LLM 生成文章")
        try:
            article_text = self.llm_client.generate_text(
                phase="GENERATE",
                purpose="中文法律科普博客生成",
                prompt=prompt,
                system_prompt="你是纽约州律师事务所的中文法律科普写作助手，只输出完整文章正文。",
                temperature=0.55 if strict_retry else 0.6,
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
        blocks = self._sanitize_blocks(blocks, topic)
        blocks = self._append_optional_tail(blocks)
        title = self._extract_title(blocks, topic)
        blocks = self._drop_leading_duplicate_title_blocks(blocks, title)
        text = "\n".join(block["text"] for block in blocks if block["text"].strip())
        word_count = estimate_word_count(text)
        return {
            "topic": topic,
            "title": title,
            "word_count": word_count,
            "blocks": blocks,
            "text": text,
            "style_profile": style_profile,
            "source_count": len(sources),
        }

    def _parse_blocks(self, article_text: str) -> list[dict[str, str]]:
        blocks: list[dict[str, str]] = []
        for raw_line in article_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if self._looks_like_meta_line(line):
                continue
            if not blocks:
                blocks.append({"type": "heading", "text": self._clean_heading(line)})
                continue
            if self._looks_like_subheading(line):
                blocks.append({"type": "subheading", "text": self._clean_heading(line)})
                continue
            if self._looks_like_list_item(line):
                blocks.append({"type": "list", "text": line})
                continue
            if self._looks_like_heading(line):
                blocks.append({"type": "heading", "text": self._clean_heading(line)})
                continue
            blocks.append({"type": "paragraph", "text": line})
        if not blocks:
            raise PhaseHaltError("LLM 未生成可解析的文章内容。")
        return blocks

    def _sanitize_blocks(self, blocks: list[dict[str, str]], topic: str) -> list[dict[str, str]]:
        sanitized: list[dict[str, str]] = []
        for index, block in enumerate(blocks):
            text = block["text"].strip()
            if not text:
                continue
            if index == 0 and self._looks_like_meta_opening(text):
                recovered_title = self._recover_title_from_meta_line(text, topic)
                if recovered_title:
                    sanitized.append({"type": "heading", "text": recovered_title})
                continue
            if text in BAD_TITLE_MARKERS and block["type"] == "heading":
                continue
            cleaned_text = self._strip_tail_section_text(text)
            if not cleaned_text:
                continue
            if self._looks_like_meta_opening(cleaned_text):
                continue
            sanitized.append({"type": block["type"], "text": cleaned_text})

        if not sanitized:
            sanitized = [{"type": "heading", "text": topic}]

        if sanitized[0]["type"] != "heading":
            sanitized.insert(0, {"type": "heading", "text": topic})

        sanitized = self._promote_better_title(sanitized, topic)

        title = sanitized[0]["text"]
        if title in BAD_TITLE_MARKERS or self._looks_like_meta_opening(title):
            sanitized[0]["text"] = topic

        if len(sanitized) > 1 and sanitized[1]["type"] == "heading":
            sanitized[1]["type"] = "subheading"

        return sanitized

    def _append_optional_tail(self, blocks: list[dict[str, str]]) -> list[dict[str, str]]:
        text = "\n".join(block["text"] for block in blocks if block["text"].strip())
        word_count = estimate_word_count(text)
        if word_count < self.context.settings.generation.min_article_word_count:
            return blocks

        include_brand = (
            self.context.rng.random()
            < self.context.settings.generation.include_brand_message_probability
        )
        include_phone = (
            self.context.rng.random()
            < self.context.settings.generation.include_phone_cta_probability
        )
        self.context.logger.info("GENERATE", f"是否加入律所寄语：{'是' if include_brand else '否'}")
        self.context.logger.info("GENERATE", f"是否加入电话咨询语：{'是' if include_phone else '否'}")

        updated = list(blocks)
        if include_brand:
            updated.append({"type": "subheading", "text": self.context.settings.generation.brand_message_title})
            updated.append({"type": "paragraph", "text": self.context.settings.generation.brand_message_body})
        if include_phone:
            updated.append({"type": "paragraph", "text": self.context.settings.generation.phone_cta_text})
        return updated

    def _quality_gate_failures(self, payload: dict, topic: str) -> list[str]:
        failures: list[str] = []
        title = (payload.get("title") or "").strip()
        text = payload.get("text", "")
        blocks = payload.get("blocks", [])
        word_count = payload.get("word_count", 0)
        subheading_count = sum(1 for block in blocks if block.get("type") == "subheading")
        paragraphs = [block.get("text", "") for block in blocks if block.get("type") == "paragraph"]

        if title in BAD_TITLE_MARKERS or not title or title == topic and subheading_count == 0:
            failures.append("主标题不合格")
        if any(text.startswith(marker) for marker in META_OPENING_MARKERS):
            failures.append("开头包含说明性废话")
        if paragraphs and any(paragraph.startswith(marker) for marker in META_OPENING_MARKERS for paragraph in paragraphs[:2]):
            failures.append("正文开头仍有说明性废话")
        if any(marker in text for marker in TAIL_SECTION_MARKERS):
            failures.append("正文残留附属栏目标记")
        if subheading_count < 3:
            failures.append("小标题数量不足")
        if word_count < self.context.settings.generation.min_article_word_count:
            failures.append("正文篇幅不足")
        if len(paragraphs) < 8:
            failures.append("正文信息量不足")
        return failures

    def _supplement_sources(
        self,
        *,
        topic: str,
        query_result: dict,
        sources: list[dict],
        searcher,
        scraper,
        source_filter,
        research_builder,
    ) -> list[dict] | None:
        self.context.logger.info("GENERATE", f"当前主题触发补采：{topic}")
        raw_candidates = searcher.search(topic, query_result.get("queries", {}))
        existing_urls = {item.get("url", "") for item in sources}
        fresh_candidates = [item for item in raw_candidates if item.get("url", "") not in existing_urls]
        if not fresh_candidates:
            self.context.logger.warning("GENERATE", "补采未获得新的候选链接")
            return None

        extracted = scraper.scrape_candidates(topic, fresh_candidates)
        filtered = source_filter.filter_articles(
            topic=topic,
            query_result=query_result,
            articles=extracted,
        )
        if not filtered:
            self.context.logger.warning("GENERATE", "补采抓取后未筛出新的可用来源")
            return None

        merged = list(sources)
        seen_urls = {item.get("url", "") for item in merged}
        for item in filtered:
            url = item.get("url", "")
            if url and url not in seen_urls:
                merged.append(item)
                seen_urls.add(url)

        research_builder.prepare_articles(topic, merged)
        self.context.logger.info("GENERATE", f"补采后可用来源数：{len(merged)}")
        return merged

    def _looks_like_heading(self, line: str) -> bool:
        if any(line.startswith(prefix) for prefix in META_LINE_MARKERS):
            return False
        if len(line) > 34:
            return False
        if line.endswith(("？", "？", "。", "；", "：")):
            return False
        if re.match(r"^[一二三四五六七八九十0-9]+[、.]", line):
            return False
        return True

    def _looks_like_subheading(self, line: str) -> bool:
        if len(line) > 40:
            return False
        return bool(
            re.match(
                r"^(第[一二三四五六七八九十0-9]+(部分|点|步|章|节)?[：:、.]?|[一二三四五六七八九十0-9]+[、.．]|(首先|其次|再次|最后|另外|还有)[：:，,]?)",
                line,
            )
        )

    def _looks_like_list_item(self, line: str) -> bool:
        return bool(re.match(r"^\d+[.)、]\s*", line))

    def _looks_like_meta_line(self, line: str) -> bool:
        return line.startswith(META_LINE_MARKERS)

    def _looks_like_meta_opening(self, line: str) -> bool:
        return any(line.startswith(marker) for marker in META_OPENING_MARKERS)

    def _clean_heading(self, line: str) -> str:
        cleaned = line.strip()
        for prefix in META_LINE_MARKERS + ("小标题：", "部分："):
            if cleaned.startswith(prefix):
                return cleaned[len(prefix) :].strip()
        return cleaned

    def _extract_title(self, blocks: list[dict[str, str]], topic: str) -> str:
        for block in blocks:
            text = block.get("text", "").strip()
            if block.get("type") == "heading" and text and text not in BAD_TITLE_MARKERS:
                return text
        return topic

    def _promote_better_title(self, blocks: list[dict[str, str]], topic: str) -> list[dict[str, str]]:
        if not blocks:
            return [{"type": "heading", "text": topic}]

        title = blocks[0]["text"].strip()
        candidate_index = None
        candidate_text = ""
        for index, block in enumerate(blocks[1:4], start=1):
            text = block.get("text", "").strip()
            if self._looks_like_title_candidate(text, title, topic):
                candidate_index = index
                candidate_text = text
                break

        if candidate_index is not None:
            blocks[0]["text"] = candidate_text
            del blocks[candidate_index]
        return blocks

    def _looks_like_title_candidate(self, text: str, current_title: str, topic: str) -> bool:
        if not text or len(text) > 48:
            return False
        if text.endswith(("。", "！", "？", "；")):
            return False
        if self._looks_like_subheading(text) or self._looks_like_meta_opening(text):
            return False
        if any(marker in text[:24] for marker in META_OPENING_MARKERS):
            return False
        if text in BAD_TITLE_MARKERS:
            return False
        if text == current_title:
            return False
        if current_title == topic and (text.startswith(topic) or "：" in text):
            return True
        if len(current_title) <= 14 and text.startswith(current_title):
            return True
        return False

    def _strip_tail_section_text(self, text: str) -> str:
        cleaned = text.strip()
        for marker in TAIL_SECTION_MARKERS:
            if cleaned == marker:
                return ""
            if cleaned.startswith(f"{marker}："):
                return ""
            marker_index = cleaned.find(marker)
            if marker_index > 0:
                cleaned = cleaned[:marker_index].rstrip("：: ;；，,。")
        return cleaned.strip()

    def _recover_title_from_meta_line(self, text: str, topic: str) -> str:
        parts = [part.strip() for part in re.split(r"[。！？]", text) if part.strip()]
        for part in reversed(parts):
            if part == text:
                continue
            if self._looks_like_title_candidate(part, topic, topic):
                return part
        return ""

    def _drop_leading_duplicate_title_blocks(self, blocks: list[dict[str, str]], title: str) -> list[dict[str, str]]:
        if not blocks or not title:
            return blocks
        cleaned: list[dict[str, str]] = []
        skipping = True
        for block in blocks:
            text = block.get("text", "").strip()
            if skipping and text == title:
                continue
            skipping = False
            cleaned.append(block)
        return cleaned if cleaned else blocks
