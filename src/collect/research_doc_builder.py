from __future__ import annotations

from src.common.docx_utils import write_sections_docx
from src.common.file_utils import sanitize_filename


class ResearchDocBuilder:
    def __init__(self, context) -> None:
        self.context = context

    def build(self, topic: str, query_result: dict, articles: list[dict]):
        sections: list[tuple[str, list[str]]] = []
        sections.append(
            (
                "一、当前主题说明",
                [
                    f"主题：{topic}",
                    f"主题类别：{self.context.current_topic_category or '未分类'}",
                    "本文件用于汇总当前主题的搜索词、采集来源、采集源数据摘录和写作参考。",
                ],
            )
        )

        query_lines = []
        for category, queries in query_result["queries"].items():
            query_lines.append(f"{category}：")
            query_lines.extend([f"1. {query}" for query in queries])
        sections.append(("二、搜索词记录", query_lines or ["未记录到搜索词。"]))

        article_lines: list[str] = []
        for index, article in enumerate(articles, start=1):
            decision = article.get("filter_decision", {})
            article_lines.extend(
                [
                    f"{index}. 标题：{article.get('title', '')}",
                    f"   来源站点：{article.get('source_site', '')}",
                    f"   采集方式：{article.get('method', '') or '未记录'}",
                    f"   搜索词：{article.get('search_query', '') or '未记录'}",
                    f"   抓取时间：{article.get('fetch_time', '') or '未记录'}",
                    f"   发布时间：{article.get('published_at', '') or '未提取到'}",
                    f"   URL：{article.get('url', '')}",
                    f"   相关性评分：{decision.get('relevance_score', '')}",
                    f"   保留原因：{decision.get('reason', '')}",
                ]
            )
        sections.append(("三、采集链接清单", article_lines or ["未保留有效采集链接。"]))

        summary_lines: list[str] = []
        for index, article in enumerate(articles, start=1):
            content = article.get("content", "")
            summary_lines.extend(
                [
                    f"{index}. {article.get('title', '')}",
                    f"   摘要：{article.get('summary', '') or '未生成摘要'}",
                    f"   写作要点：{self._build_takeaways(topic, content)}",
                    f"   术语提示：{self._extract_terms(content)}",
                ]
            )
        sections.append(("四、素材要点提炼", summary_lines or ["未提炼到素材要点。"]))

        source_lines: list[str] = []
        for index, article in enumerate(articles, start=1):
            source_lines.extend(self._build_source_excerpt_lines(index, article))
        sections.append(("五、采集源数据", source_lines or ["未采集到可展示的源数据。"]))

        path = self.context.paths.topic_research_docs / f"{sanitize_filename(topic)}_主题采集文档.docx"
        title = f"主题采集文档：{topic}"
        write_sections_docx(path, title, sections)
        self.context.logger.info("COLLECT", f"主题采集文档保存路径：{path}")
        return path

    def _build_source_excerpt_lines(self, index: int, article: dict) -> list[str]:
        content = (article.get("content") or "").strip()
        excerpt = self._truncate_text(content, limit=1200)
        if not excerpt:
            excerpt = "未采集到正文内容。"
        return [
            f"{index}. 源标题：{article.get('title', '')}",
            f"   源 URL：{article.get('url', '')}",
            f"   正文长度：{len(content)}",
            f"   正文摘录：{excerpt}",
        ]

    def _truncate_text(self, text: str, limit: int) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return compact[:limit].rstrip() + "..."

    def _build_takeaways(self, topic: str, content: str) -> str:
        points = []
        lowered = content.lower()
        if "insurance" in lowered or "保险" in content:
            points.append("可用于解释理赔流程或通知要求。")
        if "safety" in lowered or "安全" in content:
            points.append("可用于补充安全提醒。")
        if "court" in lowered or "责任" in content:
            points.append("可用于解释责任认定和证据保留。")
        if not points:
            points.append(f"可作为“{topic}”背景资料和风险提示的补充。")
        return " ".join(points)

    def _extract_terms(self, content: str) -> str:
        terms = []
        term_map = {
            "premises liability": "场所责任",
            "no-fault": "无过错保险",
            "negligence": "过失",
            "liability": "责任",
            "claim": "索赔",
        }
        lowered = content.lower()
        for en, zh in term_map.items():
            if en in lowered:
                terms.append(f"{en}（{zh}）")
        return "、".join(terms) if terms else "未提取到明显术语"
