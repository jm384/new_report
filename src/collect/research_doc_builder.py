from __future__ import annotations

from src.common.docx_utils import write_sections_docx
from src.common.file_utils import sanitize_filename
from src.common.text_utils import normalize_whitespace


class ResearchDocBuilder:
    def __init__(self, context) -> None:
        self.context = context

    def build(self, topic: str, query_result: dict, articles: list[dict]):
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
        sections.append(("二、搜索词", query_lines or ["未记录到搜索词"]))

        source_lines: list[str] = []
        for article in articles:
            decision = article.get("filter_decision", {})
            title = self._display_title(article)
            summary = self._display_summary(article)
            search_query = self._display_search_query(article.get("search_query", ""))
            score = decision.get("relevance_score", "")

            source_lines.append(f"标题：{title}")
            source_lines.append(f"链接：{article.get('url', '')}")
            source_lines.append(f"简要概要：{summary}")
            source_lines.append(f"搜索词：{search_query}")
            if score != "":
                source_lines.append(f"相关性评分：{score}")
            source_lines.append("")

        sections.append(("三、采集链接", source_lines or ["未采集到可用链接"]))

        path = self.context.paths.topic_research_docs / f"{sanitize_filename(topic)}_主题采集文档.docx"
        title = f"主题采集文档：{topic}"
        write_sections_docx(path, title, sections)
        self.context.logger.info("COLLECT", f"主题采集文档保存路径：{path}")
        return path

    def _display_title(self, article: dict) -> str:
        title = normalize_whitespace(article.get("title", "") or "")
        url = (article.get("url", "") or "").strip()
        if not title or title == url:
            return url
        return title

    def _display_summary(self, article: dict) -> str:
        summary = normalize_whitespace(article.get("summary", "") or "")
        if summary and summary not in {"手动补充来源", "兜底来源"}:
            return summary
        return self._simple_summary(article.get("content", ""))

    def _display_search_query(self, value: str) -> str:
        cleaned = normalize_whitespace(value or "")
        if cleaned in {"MANUAL_URL", "FALLBACK_MANUAL_URL"}:
            return "手动补充来源"
        return cleaned or "未记录"

    def _simple_summary(self, content: str) -> str:
        compact = normalize_whitespace(" ".join((content or "").split()))
        if not compact:
            return "未提取到可用概要"
        return compact[:220] + ("..." if len(compact) > 220 else "")
