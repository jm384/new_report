from __future__ import annotations

from src.common.docx_utils import write_sections_docx
from src.common.file_utils import sanitize_filename
from src.common.llm_client import LLMQuotaExceededError
from src.common.text_utils import contains_chinese, normalize_whitespace, split_paragraphs


PLACEHOLDER_SUMMARIES = {"手动补充来源", "兜底来源"}
INTERNAL_QUERY_MARKERS = {"MANUAL_URL", "FALLBACK_MANUAL_URL"}
FOREIGN_SUMMARY_FALLBACK = "该来源为外文页面，未完成中文概要，请参考第四部分正文。"
MISSING_SUMMARY_FALLBACK = "未提取到可用概要，请参考第四部分正文。"
MISSING_CONTENT_FALLBACK = "未提取到正文内容。"


class ResearchDocBuilder:
    def __init__(self, context, llm_client) -> None:
        self.context = context
        self.llm_client = llm_client

    def prepare_articles(self, topic: str, articles: list[dict]) -> list[dict]:
        if not articles:
            return articles

        pending_translations: list[dict] = []
        for index, article in enumerate(articles, start=1):
            existing_summary_zh = normalize_whitespace(article.get("summary_zh", "") or "")
            if contains_chinese(existing_summary_zh):
                article["summary_zh"] = existing_summary_zh
                continue

            base_summary = self._source_summary(article)
            if contains_chinese(base_summary):
                article["summary_zh"] = base_summary
                continue
            if not base_summary:
                article["summary_zh"] = MISSING_SUMMARY_FALLBACK
                continue
            pending_translations.append(
                {
                    "index": index,
                    "title": self._display_title(article),
                    "url": article.get("url", ""),
                    "summary": base_summary,
                    "content_excerpt": self._content_excerpt(article.get("content", "")),
                }
            )

        if not pending_translations:
            return articles

        translated_map = self._translate_summaries(topic, pending_translations)
        for item in pending_translations:
            article = articles[item["index"] - 1]
            summary_zh = normalize_whitespace(translated_map.get(item["index"], ""))
            article["summary_zh"] = summary_zh or FOREIGN_SUMMARY_FALLBACK

        return articles

    def build(self, topic: str, query_result: dict, articles: list[dict]):
        prepared_articles = self.prepare_articles(topic, articles)
        sections: list[tuple[str, list[str]]] = []
        sections.append(
            (
                "一、主题信息",
                [
                    f"主题：{topic}",
                    f"主题类别：{self.context.current_topic_category or '未分类'}",
                ],
            )
        )

        query_lines: list[str] = []
        for category, queries in query_result["queries"].items():
            query_lines.append(f"{category}：")
            query_lines.extend([f"- {query}" for query in queries])
        sections.append(("二、搜索词", query_lines or ["未记录到搜索词。"]))

        source_lines: list[str] = []
        fulltext_lines: list[str] = []
        for index, article in enumerate(prepared_articles, start=1):
            decision = article.get("filter_decision", {})
            title = self._display_title(article)
            summary = self._display_summary(article)
            search_query = self._display_search_query(article.get("search_query", ""))
            score = decision.get("relevance_score", "")

            source_lines.append(f"{index}. 标题：{title}")
            source_lines.append(f"链接：{article.get('url', '')}")
            source_lines.append(f"简要概要：{summary}")
            source_lines.append(f"搜索词：{search_query}")
            if score != "":
                source_lines.append(f"相关性评分：{score}")
            source_lines.append("")

            fulltext_lines.append(f"{index}. {title}")
            fulltext_lines.append("正文：")
            paragraphs = split_paragraphs(article.get("content", "")) or [MISSING_CONTENT_FALLBACK]
            fulltext_lines.extend(paragraphs)
            fulltext_lines.append("")

        sections.append(("三、采集链接", source_lines or ["未采集到可用链接。"]))
        sections.append(("四、网站正文归档", fulltext_lines or ["未采集到可归档的正文内容。"]))

        path = self.context.paths.topic_research_docs / f"{sanitize_filename(topic)}_主题采集文档.docx"
        title = f"主题采集文档：{topic}"
        write_sections_docx(path, title, sections)
        self.context.logger.info("COLLECT", f"主题采集文档保存路径：{path}")
        return path

    def _translate_summaries(self, topic: str, items: list[dict]) -> dict[int, str]:
        if not self.llm_client or not self.llm_client.is_configured:
            self.context.logger.warning(
                "COLLECT",
                "LLM 未配置，外文来源将使用中文兜底概要。",
            )
            return {}

        prompt = f"""
请将以下采集来源的外文概要改写为简洁、自然、准确的中文概要，用于法律科普主题采集文档。

要求：
1. 每条输出 1-3 句中文，长度控制在 60-180 字左右。
2. 只基于原始概要和正文节选概括，不要添加原文没有的新事实。
3. 机构名称、法规名称、时间、数字和专有名词尽量保留准确含义。
4. 不要输出 markdown，不要解释说明。
5. 只输出 JSON 数组，格式如下：
[
  {{"index": 1, "summary_zh": "中文概要"}}
]

主题：{topic}
输入：{items}
""".strip()
        try:
            payload = self.llm_client.generate_json(
                phase="COLLECT",
                purpose="主题采集文档中文概要生成",
                prompt=prompt,
                system_prompt="你是法律科普采集助手，只输出合法 JSON 数组。",
                temperature=0.2,
            )
        except LLMQuotaExceededError as exc:
            self.context.logger.warning(
                "COLLECT",
                f"中文概要生成因配额不足跳过：{exc}",
            )
            return {}
        except Exception as exc:
            self.context.logger.warning(
                "COLLECT",
                f"中文概要生成失败，改用中文兜底文案：{exc}",
            )
            return {}

        translated: dict[int, str] = {}
        if not isinstance(payload, list):
            return translated

        for item in payload:
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            summary_zh = normalize_whitespace(item.get("summary_zh", "") or "")
            if isinstance(index, int) and summary_zh:
                translated[index] = summary_zh
        return translated

    def _display_title(self, article: dict) -> str:
        title = normalize_whitespace(article.get("title", "") or "")
        url = (article.get("url", "") or "").strip()
        if not title or title == url:
            return url
        return title

    def _display_summary(self, article: dict) -> str:
        summary_zh = normalize_whitespace(article.get("summary_zh", "") or "")
        if summary_zh:
            return summary_zh
        fallback = self._source_summary(article)
        return fallback or MISSING_SUMMARY_FALLBACK

    def _source_summary(self, article: dict) -> str:
        summary = normalize_whitespace(article.get("summary", "") or "")
        if summary and summary not in PLACEHOLDER_SUMMARIES:
            return summary
        return self._simple_summary(article.get("content", ""))

    def _display_search_query(self, value: str) -> str:
        cleaned = normalize_whitespace(value or "")
        if cleaned in INTERNAL_QUERY_MARKERS:
            return "手动补充来源"
        return cleaned or "未记录"

    def _simple_summary(self, content: str) -> str:
        compact = normalize_whitespace(" ".join((content or "").split()))
        if not compact:
            return ""
        return compact[:220] + ("..." if len(compact) > 220 else "")

    def _content_excerpt(self, content: str) -> str:
        compact = normalize_whitespace(" ".join((content or "").split()))
        if not compact:
            return ""
        return compact[:900] + ("..." if len(compact) > 900 else "")
