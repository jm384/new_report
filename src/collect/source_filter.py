from __future__ import annotations

import re
from urllib.parse import urlparse

from src.common.text_utils import estimate_word_count


NEW_YORK_HINTS = [
    "new york",
    "nyc",
    "ny.gov",
    "nyc.gov",
    "纽约",
    "纽约州",
    "纽约市",
]

OFFICIAL_SOURCE_HINTS = [
    "nyc.gov",
    "ny.gov",
    "nycourts.gov",
    "dmv.ny.gov",
    "dfs.ny.gov",
    "osha.gov",
    "nycbar.org",
]


class SourceFilter:
    def __init__(self, context, llm_client) -> None:
        self.context = context
        self.llm_client = llm_client

    def filter_articles(self, *, topic: str, query_result: dict, articles: list[dict]) -> list[dict]:
        kept: list[dict] = []
        backup_candidates: list[dict] = []
        seen_titles: set[str] = set()
        seen_urls: set[str] = set()
        use_llm = (
            self.context.settings.llm.enable_source_filter and self.llm_client.is_configured
        )
        self.context.logger.info(
            "COLLECT",
            f"主题“{topic}”是否使用 LLM 过滤来源：{'是' if use_llm else '否'}",
        )

        for article in articles:
            url = article.get("url", "")
            title = (article.get("title") or "").strip()
            norm_title = title.lower()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            if norm_title and norm_title in seen_titles:
                self.context.logger.warning("COLLECT", f"过滤重复标题：{title}")
                continue
            if norm_title:
                seen_titles.add(norm_title)

            article["_prepared_for_filter"] = True

        ordered_articles = [article for article in articles if article.get("_prepared_for_filter")]
        decisions_by_url = {}
        if use_llm and ordered_articles:
            try:
                decisions_by_url = self._evaluate_batch_with_llm(topic, ordered_articles)
            except Exception as exc:
                self.context.logger.warning(
                    "COLLECT", f"LLM 来源过滤失败，改用规则模式：{exc}"
                )

        for article in ordered_articles:
            url = article.get("url", "")
            rule_decision = self._evaluate_with_rules(topic, article)
            if url in decisions_by_url:
                decision = decisions_by_url[url]
            else:
                decision = rule_decision

            article["filter_decision"] = decision
            if decision["keep_or_drop"] == "keep":
                kept.append(article)
                self.context.logger.info(
                    "COLLECT",
                    f"保留链接：{url}，原因：{decision['reason']}",
                )
            else:
                self.context.logger.warning(
                    "COLLECT",
                    f"过滤链接：{url}，原因：{decision['drop_reason'] or decision['reason']}",
                )
                if self._should_keep_as_backup(article, decision, rule_decision):
                    backup_article = dict(article)
                    backup_article["filter_decision"] = {
                        **rule_decision,
                        "reason": "作为补充素材保留：来源为手动维护或官方/准官方页面，正文可读。",
                        "keep_or_drop": "keep",
                        "drop_reason": "",
                    }
                    backup_candidates.append(backup_article)

        min_articles = self.context.settings.search.min_articles_per_topic
        if len(kept) < min_articles and backup_candidates:
            for article in backup_candidates:
                if len(kept) >= min_articles:
                    break
                if any(existing.get("url") == article.get("url") for existing in kept):
                    continue
                kept.append(article)
                self.context.logger.info(
                    "COLLECT",
                    f"补充保留链接：{article.get('url', '')}，原因：{article['filter_decision']['reason']}",
                )

        kept = kept[: self.context.settings.search.max_articles_per_topic]
        self.context.logger.info("COLLECT", f"主题“{topic}”保留高质量链接 {len(kept)} 条")
        return kept

    def _evaluate_with_rules(self, topic: str, article: dict) -> dict:
        title = (article.get("title") or "").strip()
        summary = (article.get("summary") or "").strip()
        content = (article.get("content") or "").strip()
        url = article.get("url", "")
        combined = f"{title}\n{summary}\n{content}".lower()
        word_count = estimate_word_count(content)
        topic_keywords = self._extract_topic_keywords(topic)
        topic_match = sum(1 for token in topic_keywords if token and token in combined)
        new_york_match = any(hint in combined or hint in url.lower() for hint in NEW_YORK_HINTS)
        domain = urlparse(url).netloc.lower()

        if article.get("status") != "ok":
            return {
                "url": url,
                "title": title,
                "is_relevant": False,
                "relevance_score": 5,
                "reason": "网页抓取失败",
                "keep_or_drop": "drop",
                "drop_reason": "fetch_failed",
            }
        if word_count < 180:
            return {
                "url": url,
                "title": title,
                "is_relevant": False,
                "relevance_score": 10,
                "reason": "正文过短，无法作为可靠素材",
                "keep_or_drop": "drop",
                "drop_reason": "content_too_short",
            }
        if not new_york_match:
            return {
                "url": url,
                "title": title,
                "is_relevant": False,
                "relevance_score": 20,
                "reason": "内容与纽约州/纽约市关联不足",
                "keep_or_drop": "drop",
                "drop_reason": "not_new_york_related",
            }
        if topic_match == 0 and not any(word in domain for word in ["ny", "newyork"]):
            return {
                "url": url,
                "title": title,
                "is_relevant": False,
                "relevance_score": 28,
                "reason": "内容与当前主题关联不足",
                "keep_or_drop": "drop",
                "drop_reason": "not_topic_related",
            }
        score = min(95, 50 + word_count // 40 + topic_match * 8)
        return {
            "url": url,
            "title": title,
            "is_relevant": True,
            "relevance_score": score,
            "reason": "内容与纽约州场景和当前主题相关，可用于科普写作参考",
            "keep_or_drop": "keep",
            "drop_reason": "",
        }

    def _extract_topic_keywords(self, topic: str) -> list[str]:
        parts = re.split(r"[与及、/\s]+", topic)
        keywords: list[str] = []
        for part in parts:
            cleaned = part.strip()
            if len(cleaned) >= 2:
                keywords.append(cleaned.lower())
        extra_pairs = re.findall(r"[\u4e00-\u9fff]{2,4}", topic)
        for item in extra_pairs:
            lowered = item.lower()
            if lowered not in keywords:
                keywords.append(lowered)
        return keywords

    def _should_keep_as_backup(
        self, article: dict, llm_decision: dict, rule_decision: dict
    ) -> bool:
        if article.get("status") != "ok":
            return False
        if estimate_word_count(article.get("content", "")) < 180:
            return False
        url = article.get("url", "").lower()
        domain = urlparse(url).netloc.lower()
        method = article.get("method", "")
        is_official_like = any(hint in domain for hint in OFFICIAL_SOURCE_HINTS) or domain.endswith(".gov")
        is_manual = method == "manual_url"
        if not (is_manual or is_official_like):
            return False
        if rule_decision.get("keep_or_drop") == "keep":
            return True
        return llm_decision.get("relevance_score", 0) >= 55 and is_official_like

    def _evaluate_with_llm(self, topic: str, article: dict) -> dict:
        prompt = f"""
请判断下面网页是否适合用作纽约州华人法律科普博客素材。
主题：{topic}
标题：{article.get('title', '')}
URL：{article.get('url', '')}
摘要：{article.get('summary', '')}
正文节选：{article.get('content', '')[:2500]}

请输出 JSON：
{{
  "url": "...",
  "title": "...",
  "is_relevant": true,
  "relevance_score": 86,
  "reason": "...",
  "keep_or_drop": "keep",
  "drop_reason": ""
}}
""".strip()
        payload = self.llm_client.generate_json(
            phase="COLLECT",
            purpose="来源过滤",
            prompt=prompt,
            system_prompt="你是纽约州法律资讯过滤助手，只输出合法 JSON。",
        )
        return payload

    def _evaluate_batch_with_llm(self, topic: str, articles: list[dict]) -> dict[str, dict]:
        items = []
        for article in articles:
            items.append(
                {
                    "url": article.get("url", ""),
                    "title": article.get("title", ""),
                    "summary": article.get("summary", ""),
                    "content_excerpt": article.get("content", "")[:1600],
                    "status": article.get("status", ""),
                }
            )
        prompt = f"""
请判断下面这些网页是否适合用作纽约州华人法律科普博客素材。
主题：{topic}

输入：
{items}

请输出 JSON 数组，每个元素格式如下：
[
  {{
    "url": "https://example.com/article",
    "title": "Example Title",
    "is_relevant": true,
    "relevance_score": 86,
    "reason": "内容与主题和纽约州场景相关",
    "keep_or_drop": "keep",
    "drop_reason": ""
  }}
]
""".strip()
        payload = self.llm_client.generate_json(
            phase="COLLECT",
            purpose="批量来源过滤",
            prompt=prompt,
            system_prompt="你是纽约州法律资讯过滤助手，只输出合法 JSON 数组。",
        )
        return {item["url"]: item for item in payload if item.get("url")}
