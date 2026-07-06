from __future__ import annotations

from statistics import mean

from src.common.llm_client import LLMQuotaExceededError
from src.common.text_utils import (
    average_paragraph_length,
    detect_headings,
    split_paragraphs,
    top_terms,
)


class TemplateStyleAnalyzer:
    def __init__(self, context, llm_client) -> None:
        self.context = context
        self.llm_client = llm_client

    def analyze(self, *, topic: str, template_payload: dict) -> dict:
        templates = template_payload["templates"]
        all_paragraphs = []
        heading_counts = []
        intro_lengths = []
        top_terms_sets = []

        for template in templates:
            paragraphs = split_paragraphs(template["text"])
            headings = detect_headings(paragraphs)
            all_paragraphs.extend(paragraphs)
            heading_counts.append(len(headings))
            intro_lengths.append(len(paragraphs[0]) if paragraphs else 0)
            top_terms_sets.append(template["top_terms"])

        profile = {
            "topic": topic,
            "topic_category": self.context.current_topic_category,
            "template_paths": [template["path"] for template in templates],
            "template_count": len(templates),
            "avg_heading_count": round(mean(heading_counts), 2) if heading_counts else 0,
            "avg_intro_length": round(mean(intro_lengths), 2) if intro_lengths else 0,
            "avg_paragraph_length": round(average_paragraph_length(all_paragraphs), 2),
            "common_terms": self._merge_terms(top_terms_sets),
            "tone_summary": "中文法律科普博客风格，偏生活化开头，段落中等长度，强调提醒与解释。",
            "structure_summary": "建议使用温和标题、生活场景导入、4-5 个小标题、结尾加入温和提醒。",
        }

        should_use_rule_mode = (
            not self.llm_client.is_configured
            or len(templates) <= self.context.settings.template_min_viable_count
            or template_payload.get("hit_quota_limit", False)
        )
        if should_use_rule_mode:
            if template_payload.get("hit_quota_limit", False):
                self.context.logger.info("COLLECT", "模板分析跳过 LLM：模板补齐阶段已遇到配额不足。")
            elif len(templates) <= self.context.settings.template_min_viable_count:
                self.context.logger.info("COLLECT", "模板数量仅达到最低可行阈值，使用规则方式分析风格。")
            else:
                self.context.logger.info("COLLECT", "当前未启用 LLM，使用规则方式处理模板风格分析。")
            self.context.logger.info("COLLECT", "模板风格分析是否成功：是（规则模式）")
            self.context.logger.info(
                "COLLECT",
                f"模板风格分析结果路径：{self.context.paths.data / 'template_style_profiles.json'}",
            )
            return profile

        try:
            profile.update(self._enhance_with_llm(topic, templates))
            self.context.logger.info("COLLECT", "模板风格分析是否成功：是（LLM 增强）")
        except LLMQuotaExceededError as exc:
            self.context.logger.warning("COLLECT", f"模板风格分析遇到配额不足，改用规则结果：{exc}")
            self.context.logger.info("COLLECT", "模板风格分析是否成功：是（规则模式）")
        except Exception as exc:
            self.context.logger.warning("COLLECT", f"模板风格 LLM 分析失败，使用规则结果：{exc}")
            self.context.logger.info("COLLECT", "模板风格分析是否成功：是（规则模式）")

        self.context.logger.info(
            "COLLECT",
            f"模板风格分析结果路径：{self.context.paths.data / 'template_style_profiles.json'}",
        )
        return profile

    def _merge_terms(self, terms_sets: list[list[str]]) -> list[str]:
        merged = []
        for terms in terms_sets:
            for term in terms:
                if term not in merged:
                    merged.append(term)
        return merged[:20]

    def _enhance_with_llm(self, topic: str, templates: list[dict]) -> dict:
        sample_text = "\n\n".join(template["text"][:1200] for template in templates[:4])
        prompt = f"""
请分析以下中文律师事务所博客模板的结构风格和语言风格。
主题：{topic}
模板内容节选：
{sample_text}

请输出 JSON：
{{
  "tone_summary": "...",
  "structure_summary": "...",
  "recommended_opening_style": "...",
  "recommended_ending_style": "..."
}}
""".strip()
        return self.llm_client.generate_json(
            phase="COLLECT",
            purpose="模板风格分析",
            prompt=prompt,
            system_prompt="你是中文法律科普博客风格分析助手，只输出合法 JSON。",
        )
